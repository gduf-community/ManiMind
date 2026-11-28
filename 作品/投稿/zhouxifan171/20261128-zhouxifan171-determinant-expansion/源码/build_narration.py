"""为《行列式按行（列）展开》生成中文配音、字幕时间轴与合轨音轨。

流程：
  1. 用 edge-tts（zh-CN-XiaoxuanNeural，晓萱）逐段合成旁白到 audio/bXX.mp3；
  2. 量出每段语音时长，加上前导/收尾留白，乘以节奏倍率得到「镜头节拍」时长；
  3. 写 timings.json / timings_slow.json（场景读取它把每个节拍补足到统一时间点）；
  4. 生成等长的静音补齐 wav 并拼接成整轨配音；
  5. 输出 subtitles.srt / subtitles_slow.srt。

用法（在项目根目录）：
    python build_narration.py                     # 正常节奏（约 1 分钟）
    python build_narration.py --scale 1.3 --tag _slow   # 更慢的一版
    python build_narration.py --force             # 改稿后强制重合成
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AUDIO = ROOT / "audio"
# 晓萱：温润知性，比晓晓（新闻播报感）更柔和；语速再放慢一点、音调微降更显轻柔
VOICE = "zh-CN-XiaoxuanNeural"
RATE = "-10%"
PITCH = "-2Hz"
LEAD = 0.30
TAIL = 0.80

# 旁白里「行」都取「排」义，应读 háng，但中文 TTS 常误读成 xíng。
# edge-tts 7.x 会把文本做 XML 转义，无法用 SSML <phoneme> 标注读音，
# 因此用同音字「航」（唯一读音 háng）强制纠正发音——只影响音频，字幕仍用「行」。
PRONOUNCE_FIX = {"行": "航"}


def speech_of(text: str) -> str:
    """把旁白文本转成「喂给 TTS 的读音稿」。"""
    for src, dst in PRONOUNCE_FIX.items():
        text = text.replace(src, dst)
    return text

# (旁白文本, 字幕行（支持 <sub>/<sup> 富文本）, 最短节拍秒数)
BEATS = [
    (
        "看一个三阶行列式，怎么算更快？可以按行，也可以按列展开。",
        ["怎么算更快？", "关键是按行（列）展开"],
        6.0,
    ),
    (
        "核心是：元素乘以它的代数余子式，再把所有项加起来。",
        ["核心：元素 × 代数余子式，再求和",
         "A<sub>ij</sub> = (−1)<sup>i+j</sup>M<sub>ij</sub>"],
        6.0,
    ),
    (
        "这里选第二行，因为它含有一个零。",
        ["这里选第二行——它含有一个 0"],
        3.6,
    ),
    (
        "四乘以A二一，等于负的M二一。划去第二行第一列，余子式是零。",
        ["4 × A<sub>21</sub> = −4 × M<sub>21</sub>：划去第 2 行、第 1 列",
         "M<sub>21</sub> = 1×6 − 3×2 = 0"],
        6.4,
    ),
    (
        "零乘以A二二，这一项还是零。",
        ["0 × A<sub>22</sub> = 0，这一项直接省掉"],
        3.8,
    ),
    (
        "五乘以A二三，余子式等于三，代数余子式是负三，这一项就是负十五。",
        ["5 × A<sub>23</sub> = −5 × M<sub>23</sub>",
         "M<sub>23</sub> = 2×2 − 1×1 = 3，这一项 = −15"],
        6.4,
    ),
    (
        "三项相加，结果等于负十五。",
        ["三项相加：0 + 0 − 15 = −15"],
        4.0,
    ),
    (
        "换成第三列：三乘八，五乘负三，六乘负四，还是负十五。",
        ["换第三列：3×8 + 5×(−3) + 6×(−4) = −15"],
        6.4,
    ),
    (
        "所以，任一行、任一列都能展开；含零越多，越省力。",
        ["任一行（列）都能展开", "含 0 越多，计算越省力"],
        6.0,
    ),
]


def ffmpeg_exe() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def wav_duration(path: Path) -> float:
    """读取 PCM wav 时长（本机无 ffprobe，用标准库 wave 头信息）。"""
    import wave

    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def synth(text: str, out: Path, tries: int = 4) -> None:
    """edge-tts 走网络，偶发失败时重试若干次。"""
    cmd = [
        sys.executable, "-m", "edge_tts",
        "--voice", VOICE,
        f"--rate={RATE}",
        f"--pitch={PITCH}",
        "--text", text,
        "--write-media", str(out),
    ]
    last = ""
    for attempt in range(1, tries + 1):
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0 and out.exists() and out.stat().st_size > 1000:
            return
        last = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:]
        print(f"    retry {attempt}/{tries}: {last}")
        time.sleep(1.5 * attempt)
    raise RuntimeError(f"edge-tts 合成失败：{text}")


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main() -> None:
    argv = sys.argv[1:]
    force = "--force" in argv
    scale = 1.0
    tag = ""
    if "--scale" in argv:
        scale = float(argv[argv.index("--scale") + 1])
    if "--tag" in argv:
        tag = argv[argv.index("--tag") + 1]

    AUDIO.mkdir(exist_ok=True)
    ff = ffmpeg_exe()

    # 音色/语速/音调一变，旧 mp3 就不能复用（否则会拿到旧音色的音频）
    stamp = AUDIO / "_voice.txt"
    signature = f"{VOICE}|{RATE}|{PITCH}|{json.dumps(PRONOUNCE_FIX, ensure_ascii=False)}"
    if not force and stamp.exists() and stamp.read_text(encoding="utf-8").strip() != signature:
        force = True
        print("[voice] 音色或参数已变更，强制重新合成全部旁白")
    stamp.write_text(signature, encoding="utf-8")

    beats: list[dict] = []
    cum: list[float] = []
    clock = 0.0
    concat_lines: list[str] = []

    for i, (text, subs, min_dur) in enumerate(BEATS):
        mp3 = AUDIO / f"b{i:02d}.mp3"
        say = speech_of(text)
        if force or not mp3.exists():
            print(f"[tts] {i:02d} {say}")
            synth(say, mp3)
        raw = AUDIO / f"b{i:02d}_raw.wav"
        subprocess.run(
            [ff, "-y", "-v", "error", "-i", str(mp3),
             "-ar", "44100", "-ac", "1", "-c:a", "pcm_s16le", str(raw)],
            check=True,
        )
        speech = wav_duration(raw)
        dur = max(min_dur, LEAD + speech + TAIL) * scale

        wav = AUDIO / f"b{i:02d}{tag}.wav"
        # 前置 LEAD 静音，尾部补齐到节拍时长
        subprocess.run(
            [
                ff, "-y", "-v", "error", "-i", str(raw),
                "-af",
                f"adelay={int(LEAD * 1000)}|{int(LEAD * 1000)},"
                f"apad=whole_dur={dur:.3f}",
                "-ar", "44100", "-ac", "1", "-c:a", "pcm_s16le", str(wav),
            ],
            check=True,
        )
        concat_lines.append(f"file '{wav.as_posix()}'")

        beats.append(
            {"i": i, "text": text, "say": say, "sub": subs,
             "speech": round(speech, 3),
             "dur": round(dur, 3), "start": round(clock, 3)}
        )
        clock += dur
        cum.append(round(clock, 3))

    list_file = AUDIO / f"concat{tag}.txt"
    list_file.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
    narration = AUDIO / f"narration{tag}.wav"
    subprocess.run(
        [ff, "-y", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", str(list_file), "-c", "copy", str(narration)],
        check=True,
    )

    (ROOT / f"timings{tag}.json").write_text(
        json.dumps({"lead": LEAD, "scale": scale, "voice": VOICE,
                    "rate": RATE, "pitch": PITCH,
                    "beats": beats, "cum": cum},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    srt = []
    for b in beats:
        srt.append(str(b["i"] + 1))
        srt.append(f"{srt_time(b['start'])} --> {srt_time(b['start'] + b['dur'])}")
        srt.append("\n".join(b["sub"]))
        srt.append("")
    (AUDIO / f"subtitles{tag}.srt").write_text("\n".join(srt), encoding="utf-8")

    print(f"\n{'#':>2} {'speech':>7} {'beat':>7} {'start':>7}")
    for b in beats:
        print(f"{b['i']:>2} {b['speech']:>7.2f} {b['dur']:>7.2f} {b['start']:>7.2f}")
    print(f"\n总时长 {clock:.2f}s -> {narration}")
    print(f"音频总长 {wav_duration(narration):.2f}s")


if __name__ == "__main__":
    main()
