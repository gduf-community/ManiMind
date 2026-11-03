"""Quality review module — Gemini vision analysis + iterative improvement.

Workflow:
1. Extract frames from generated video
2. Gemini compares against 3Blue1Brown reference frames
3. Returns specific, actionable Manim code improvement suggestions
4. Kimi applies the suggestions to improve the code
5. Re-render → compare again
"""

import base64, json, os, subprocess
from dataclasses import dataclass, field
from typing import Optional

from ..bootstrap import resolve_tool


@dataclass
class ReviewResult:
    """Result of a quality review pass."""
    overall_score: int = 0          # 0-10
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    code_suggestions: list[str] = field(default_factory=list)
    color_fixes: list[str] = field(default_factory=list)
    layout_fixes: list[str] = field(default_factory=list)
    next_action: str = ""           # "pass" or "retry"


def extract_frames(video_path: str, output_dir: str, timestamps: list[int] = None) -> list[str]:
    """Extract key frames from a video for analysis."""
    if timestamps is None:
        timestamps = [10, 30, 60, 90, 120]

    os.makedirs(output_dir, exist_ok=True)
    ffmpeg = os.environ.get("FFMPEG") or resolve_tool("ffmpeg")
    if not ffmpeg:
        raise FileNotFoundError("ffmpeg is required to extract review frames")
    files = []

    for t in timestamps:
        out = os.path.join(output_dir, f'frame_{t:03d}s.jpg')
        subprocess.run([ffmpeg, '-y', '-ss', str(t), '-i', video_path,
                       '-frames:v', '1', out], capture_output=True)
        if os.path.exists(out):
            files.append(out)
    return files


def analyze_with_gemini(
    generated_video_path: str,
    reference_video_path: str = None,
    reference_frame_dir: str = None,
    api_key: str = None,
    base_url: str = None,
) -> ReviewResult:
    """Have Gemini compare our video against a reference and give suggestions.

    Args:
        generated_video_path: Path to our generated MP4
        reference_video_path: Path to 3B1B reference MP4 (optional)
        reference_frame_dir: Directory with pre-extracted reference frames
        api_key: Gemini API key
        base_url: Gemini API base URL

    Returns:
        ReviewResult with scores and actionable suggestions
    """
    from openai import OpenAI

    if api_key is None:
        api_key = os.environ.get('CODE_LLM_API_KEY', os.environ.get('OPENAI_API_KEY', ''))
    if base_url is None:
        base_url = os.environ.get('CODE_LLM_BASE_URL', os.environ.get('OPENAI_BASE_URL', 'https://api.moonshot.cn/v1'))

    client = OpenAI(api_key=api_key, base_url=base_url)

    # Extract frames
    tmp_dir = os.path.join(os.path.dirname(generated_video_path), 'review_frames')
    gen_frames = extract_frames(generated_video_path, tmp_dir)

    # Load reference frames if available
    ref_frames = []
    if reference_frame_dir and os.path.exists(reference_frame_dir):
        ref_files = sorted([f for f in os.listdir(reference_frame_dir) if f.endswith('.jpg')])
        for f in ref_files[:5]:
            path = os.path.join(reference_frame_dir, f)
            with open(path, 'rb') as fh:
                ref_frames.append(base64.b64encode(fh.read()).decode())

    # Build message
    content = [
        {'type': 'text', 'text': '''你是数学科普视频质量审查员。请对比分析以下两组的视频帧：

第一组(参考): 3Blue1Brown 专业制作的微积分动画
第二组(生成): AI自动生成的动画

请按以下维度评分(1-10)并给出具体的Manim代码修改建议:

1. 配色方案: 黑色背景？白色文字？蓝色曲线？
2. 布局: 标题位置？公式排版？信息密度？
3. 动画流畅度: 元素渐入？过渡时间？
4. 视觉引导: 箭头/高亮标注？
5. 字体可读性: 大小？颜色对比度？

输出格式(JSON):
{
  "overall_score": 7,
  "strengths": ["..."],
  "weaknesses": ["代码背景不是纯黑", "标题字体太小"],
  "code_suggestions": ["self.camera.background_color = BLACK", "Text(..., font_size=48)"],
  "color_fixes": ["坐标轴从GRAY改为#888888", "切线从RED改为GREEN"],
  "layout_fixes": ["标题移到to_edge(UP)", "公式用to_corner(DL)"],
  "next_action": "pass"
}
''',
        }
    ]

    # Attach frames
    for img in ref_frames:
        content.append({'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{img}'}})

    for f in gen_frames[:5]:
        with open(f, 'rb') as fh:
            b64 = base64.b64encode(fh.read()).decode()
        content.append({'type': 'text', 'text': '--- 生成的视频帧 ---'})
        content.append({'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{b64}'}})

    review_model = os.environ.get('VISION_MODEL', 'moonshot-v1-8k-vision-preview')
    resp = client.chat.completions.create(
        model=review_model,
        messages=[{'role': 'user', 'content': content}],
        max_tokens=1500,
    )

    try:
        # Try parsing JSON response
        result_text = resp.choices[0].message.content
        # Extract JSON if wrapped in markdown
        if '```json' in result_text:
            result_text = result_text.split('```json')[1].split('```')[0]
        elif '```' in result_text:
            result_text = result_text.split('```')[1].split('```')[0]

        data = json.loads(result_text)
        return ReviewResult(
            overall_score=data.get('overall_score', 0),
            strengths=data.get('strengths', []),
            weaknesses=data.get('weaknesses', []),
            code_suggestions=data.get('code_suggestions', []),
            color_fixes=data.get('color_fixes', []),
            layout_fixes=data.get('layout_fixes', []),
            next_action=data.get('next_action', 'retry'),
        )
    except (json.JSONDecodeError, KeyError):
        # Fallback: return raw text as suggestions
        return ReviewResult(
            overall_score=5,
            code_suggestions=[resp.choices[0].message.content],
            next_action='retry',
        )


def apply_suggestions(code: str, suggestions: list[str]) -> str:
    """Apply review suggestions to Manim code using Kimi."""
    from openai import OpenAI

    client = OpenAI(
        api_key=os.environ.get('OPENAI_API_KEY', ''),
        base_url=os.environ.get('OPENAI_BASE_URL', '')
    )

    prompt = '''改进下面的Manim代码，应用以下具体修改建议:

原代码:
```python
{code}
```

修改建议:
{suggestions}

要求: 只输出修复后的完整代码，不解释。保持原有逻辑不变。'''.format(
        code=code[:3000],
        suggestions='\n'.join('- ' + s for s in suggestions)
    )

    resp = client.chat.completions.create(
        model=os.environ.get('MANIMIND_MODEL', 'moonshot-v1-128k'),
        messages=[{'role': 'user', 'content': prompt}],
        max_tokens=3000,
    )

    result = resp.choices[0].message.content
    return result.replace('```python', '').replace('```', '').strip()


def quality_loop(
    code_path: str,
    output_video: str,
    reference_dir: str,
    max_iterations: int = 3,
    target_score: int = 8,
) -> dict:
    """Run iterative quality improvement loop.

    Returns dict with final score and iteration history.
    """
    history = []

    for i in range(max_iterations):
        print(f'\n=== Quality Review Round {i+1} ===')

        # Review
        result = analyze_with_gemini(
            generated_video_path=output_video,
            reference_frame_dir=reference_dir,
        )
        history.append(result)
        print(f'Score: {result.overall_score}/10')

        if result.next_action == 'pass' or result.overall_score >= target_score:
            print('Quality target reached!')
            break

        # Apply suggestions
        with open(code_path, 'r', encoding='utf-8') as f:
            code = f.read()

        improved = apply_suggestions(code, result.code_suggestions)
        with open(code_path, 'w', encoding='utf-8') as f:
            f.write(improved)

        print(f'Applied {len(result.code_suggestions)} suggestions, re-rendering...')

        # Re-render (caller should handle this)
        # This function just saves the improved code

    return {
        'final_score': history[-1].overall_score,
        'iterations': len(history),
        'history': history,
    }
