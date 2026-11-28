"""行列式按行（列）展开：教学动画（配音 + 字幕版）。

记号与课本一致：A_ij 表示代数余子式，M_ij 表示余子式，
A_ij = (-1)^(i+j) M_ij。下标/上标用 Pango 富文本（MarkupText 的
<sub>/<sup>）排成真下标，无需 LaTeX。

画面节奏由 timings*.json 驱动（build_narration.py 生成）：每个「节拍」
对应一句旁白，场景在该节拍末尾把时间补齐到累计时间点，旁白与画面同步。

渲染（在 manimtopo 环境中）：
    manim -qh --media_dir %TEMP%/manimtopo_media scenes/determinant_expansion.py DetExpansion
    manim -qh --media_dir %TEMP%/manimtopo_media scenes/determinant_expansion.py DetExpansionSlow

内容：D = |2 1 3; 4 0 5; 1 2 6| 按第二行展开（逐项划行列 + 2 阶余子式），
符号板 (-1)^(i+j) 联动，第三列交叉验证，均得 -15。

逐项展开的表达（按徐鹏程老师意见修改）：
  不做「放大再缩小」的强调，也不把被划去的系数直接盖掉；而是让该元素从行列式里
  变红高亮、沿弧线「取出来」落到右侧算式的系数位，随后才淡入遮罩划去整行整列。
  元素撤遮罩后淡回原位并转灰，表示「已被取用」，行列式始终完整可读。
"""

from __future__ import annotations

import json
from pathlib import Path

from manim import *

BG = "#0E1117"
INK = "#E9EEF7"
MUTED = "#8B96A8"
DIM = "#5B6675"
CYAN = "#5FD3F3"
PINK = "#FF7A90"
GOLD = "#FFC857"
CN = "Microsoft YaHei"

ENTRIES = [["2", "1", "3"], ["4", "0", "5"], ["1", "2", "6"]]
SIGNS = [["+", "-", "+"], ["-", "+", "-"], ["+", "-", "+"]]

ROOT = Path(__file__).resolve().parent.parent

# timings.json 缺失时的兜底节拍（秒），与旁白稿一一对应
DEFAULT_BEATS = [7.4, 7.4, 4.6, 7.6, 4.8, 7.6, 5.0, 7.6, 7.4]


def cn(text: str, size: float = 32, color: str = INK, weight: str = NORMAL) -> Text:
    return Text(text, font=CN, font_size=size, color=color, weight=weight)


def fm(text: str, size: float = 28, color: str = INK) -> MarkupText:
    """带 <sub>/<sup> 富文本的数学文本（真下标、真上标）。"""
    return MarkupText(text, font=CN, font_size=size, color=color)


def load_cum(name: str) -> list[float]:
    path = ROOT / name
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return [round(float(x), 3) for x in data["cum"]]
    cum, t = [], 0.0
    for d in DEFAULT_BEATS:
        t += d
        cum.append(round(t, 3))
    return cum


def make_sub(lines: list[str]) -> VGroup:
    txt = VGroup(*[fm(line, 22, INK) for line in lines]).arrange(DOWN, buff=0.08)
    plate = BackgroundRectangle(
        txt, color="#05070B", fill_opacity=0.72, buff=0.15, stroke_width=0
    )
    return VGroup(plate, txt).move_to([0, -3.42, 0])


class DetExpansionBase(Scene):
    TIMING = "timings.json"
    SPEED = 1.0

    # ---------------------------------------------------------------- 节拍工具
    def rt(self, t: float) -> float:
        """动画时长按节奏倍率缩放（慢版整体放慢）。"""
        return t * self.SPEED

    def show_sub(self, lines: list[str]) -> None:
        grp = make_sub(lines)
        if getattr(self, "cur_sub", None) is None:
            self.play(FadeIn(grp, shift=UP * 0.08), run_time=self.rt(0.4))
        else:
            self.play(
                FadeOut(self.cur_sub, run_time=self.rt(0.25)),
                FadeIn(grp, shift=UP * 0.08, run_time=self.rt(0.4)),
            )
        self.cur_sub = grp

    def end_beat(self) -> None:
        gap = self.cum[self.bi] - self.time
        if gap > 0.03:
            self.wait(gap)
        self.bi += 1

    # ---------------------------------------------------------------- 主体
    def construct(self):
        self.camera.background_color = BG
        self.cum = load_cum(self.TIMING)
        self.bi = 0
        self.cur_sub = None
        self.speed = self.SPEED

        cx, cy, sp = -3.4, 0.3, 0.9

        def pos(r: int, c: int):
            return [cx + (c - 1) * sp, cy + (1 - r) * sp, 0]

        # ============================================== 01 标题 + 三阶行列式
        self.show_sub(["怎么算更快？", "关键是按行（列）展开"])

        title = cn("行列式按行（列）展开", 38, INK, BOLD).to_edge(UP, buff=0.38)
        heading = cn("任取一行（列）：元素 × 代数余子式，再求和", 21, MUTED)
        heading.next_to(title, DOWN, buff=0.14)
        self.play(FadeIn(title, shift=DOWN * 0.25), run_time=self.rt(0.9))
        self.play(FadeIn(heading, shift=DOWN * 0.1), run_time=self.rt(0.6))

        grid = VGroup()
        for r in range(3):
            for c in range(3):
                t = Text(ENTRIES[r][c], font=CN, font_size=40, color=INK)
                t.move_to(pos(r, c))
                grid.add(t)

        bar_h = sp + 0.42
        bars = VGroup(
            Line(
                [cx - sp - 0.42, cy + bar_h, 0],
                [cx - sp - 0.42, cy - bar_h, 0],
                color=INK,
                stroke_width=4,
            ),
            Line(
                [cx + sp + 0.42, cy + bar_h, 0],
                [cx + sp + 0.42, cy - bar_h, 0],
                color=INK,
                stroke_width=4,
            ),
        )
        det = VGroup(grid, bars)
        lab_d = cn("D =", 30, INK).move_to([cx - 2.1, cy, 0])

        self.play(Create(bars), run_time=self.rt(1.0))
        self.play(
            LaggedStart(*[FadeIn(t, scale=0.9) for t in grid], lag_ratio=0.07),
            run_time=self.rt(1.6),
        )
        self.play(FadeIn(lab_d), run_time=self.rt(0.5))
        self.end_beat()

        # ============================================== 02 符号板 + 记号约定
        self.show_sub(["核心：元素 × 代数余子式，再求和",
                       "A<sub>ij</sub> = (−1)<sup>i+j</sup>M<sub>ij</sub>"])

        sx, sy, sp2 = -0.9, 0.3, 0.46
        board = VGroup()
        for r in range(3):
            for c in range(3):
                s = Text(SIGNS[r][c], font=CN, font_size=22, color=DIM)
                s.move_to([sx + (c - 1) * sp2, sy + (1 - r) * sp2, 0])
                board.add(s)
        board_lab = fm("符号 (−1)<sup>i+j</sup>", 19, MUTED).move_to([sx, sy + 1.18, 0])

        formula = fm("A<sub>ij</sub> = (−1)<sup>i+j</sup>M<sub>ij</sub>", 30, GOLD)
        formula.move_to([2.7, 2.28, 0])
        formula_sub = fm("M<sub>ij</sub>：划去第 i 行、第 j 列，余下的 2 阶行列式", 19, MUTED)
        formula_sub.move_to([2.7, 1.8, 0])

        self.play(FadeIn(board_lab), run_time=self.rt(0.5))
        self.play(
            LaggedStart(*[FadeIn(s, scale=0.8) for s in board], lag_ratio=0.08),
            run_time=self.rt(1.5),
        )
        self.play(FadeIn(formula, shift=DOWN * 0.12), run_time=self.rt(0.8))
        self.play(FadeIn(formula_sub), run_time=self.rt(0.6))
        self.play(Indicate(formula, color=GOLD, scale_factor=1.08), run_time=self.rt(1.2))
        self.end_beat()

        # ============================================== 03 选定第二行
        self.show_sub(["这里选第二行——它含有一个 0"])

        row_rect = Rectangle(
            width=2 * sp + 0.85, height=0.72, color=PINK, stroke_width=3
        ).move_to(pos(1, 1))
        caption = cn("按第二行展开", 22, MUTED).move_to([cx, cy - 2.05, 0])
        board_row = SurroundingRectangle(
            VGroup(*[board[3 + c] for c in range(3)]),
            color=GOLD,
            stroke_width=2.5,
            buff=0.07,
        )
        self.play(Create(row_rect), FadeIn(caption), run_time=self.rt(0.9))
        self.play(Flash(grid[4], color=PINK, flash_radius=0.5), run_time=self.rt(0.8))
        self.play(Create(board_row), run_time=self.rt(0.7))
        self.end_beat()

        # ============================================== 04-06 逐项展开
        def cell_cover(r: int, c: int) -> Rectangle:
            return Rectangle(
                width=0.78,
                height=0.66,
                fill_color=BG,
                fill_opacity=0.9,
                stroke_width=0,
            ).move_to(pos(r, c))

        def minor_visual(r: int, c: int):
            covers = VGroup()
            for cc in range(3):
                covers.add(cell_cover(r, cc))
            for rr in range(3):
                if rr != r:
                    covers.add(cell_cover(rr, c))
            rest = VGroup(
                *[
                    grid[rr * 3 + cc]
                    for rr in range(3)
                    if rr != r
                    for cc in range(3)
                    if cc != c
                ]
            )
            return (
                covers,
                SurroundingRectangle(rest, color=CYAN, stroke_width=2.5, buff=0.1),
            )

        term_specs = [
            (
                ["4 × A<sub>21</sub> = −4 × M<sub>21</sub>：划去第 2 行、第 1 列",
                 "M<sub>21</sub> = 1×6 − 3×2 = 0"],
                "4 × A<sub>21</sub>",
                "= −4 × M<sub>21</sub>",
                "M<sub>21</sub> = 1×6 − 3×2 = 0",
                0,
                1.0,
            ),
            (
                ["0 × A<sub>22</sub> = 0，这一项直接省掉"],
                "0 × A<sub>22</sub>",
                "= 0 × 9 = 0",
                "M<sub>22</sub> = 2×6 − 3×1 = 9",
                1,
                0.15,
            ),
            (
                ["5 × A<sub>23</sub> = −5 × M<sub>23</sub>",
                 "M<sub>23</sub> = 2×2 − 1×1 = 3，这一项 = −15"],
                "5 × A<sub>23</sub>",
                "= −5 × M<sub>23</sub>",
                "M<sub>23</sub> = 2×2 − 1×1 = 3",
                2,
                -0.7,
            ),
        ]
        made: list[Mobject] = []
        for subs, head, tail, sub_text, col, y in term_specs:
            self.show_sub(subs)

            # 右侧算式的系数位先留空：等元素从行列式里“取出来”再落位
            entry = ENTRIES[1][col]
            num_txt = fm(entry, 28, PINK)
            head_grp = VGroup(num_txt, fm(f"× A<sub>2{col + 1}</sub>", 28, PINK))
            head_grp.arrange(RIGHT, buff=0.12)
            line = VGroup(head_grp, fm(tail, 28, INK)).arrange(RIGHT, buff=0.15)
            line.move_to([2.7, y, 0])
            sub = fm(sub_text, 20, MUTED).next_to(line, DOWN, buff=0.07)
            head_grp.remove(num_txt)  # 定位完成后再剥离，坐标仍保留

            src = grid[3 + col]
            frame = SurroundingRectangle(src, color=PINK, stroke_width=2, buff=0.13)
            flyer = Text(entry, font=CN, font_size=40, color=PINK).move_to(src)

            # 1) 亮出右侧算式（系数位暂空），并用描边框点出待取的元素——不做放大缩小
            self.play(FadeIn(line), FadeIn(sub), Create(frame), run_time=self.rt(0.8))
            # 2) 元素变红高亮
            self.play(src.animate.set_color(PINK), run_time=self.rt(0.3))
            # 3) 从行列式里取出来，弧线飞到算式系数位
            self.add(flyer)
            src.set_opacity(0)
            self.play(
                flyer.animate(path_arc=PI / 6)
                .move_to(num_txt.get_center())
                .scale(0.7),
                FadeOut(frame),
                run_time=self.rt(0.8),
            )
            self.play(FadeIn(num_txt), FadeOut(flyer), run_time=self.rt(0.25))
            # 4) 划去该行该列，余下 2 阶行列式
            covers, box = minor_visual(1, col)
            self.play(FadeIn(covers), Create(box), run_time=self.rt(0.85))
            self.wait(self.rt(1.3))
            # 5) 撤遮罩；元素淡回原位并转灰，表示「已被取用」而非被抹掉
            self.play(
                FadeOut(covers),
                FadeOut(box),
                src.animate.set_opacity(1).set_color(DIM),
                run_time=self.rt(0.45),
            )
            made.extend([line, sub, num_txt])
            self.end_beat()

        # ============================================== 07 求和
        self.show_sub(["三项相加：0 + 0 − 15 = −15"])
        sum_line = (
            VGroup(
                fm("D = 4×0 + 0×9 + 5×(−3) =", 25, INK),
                fm("−15", 30, GOLD),
            )
            .arrange(RIGHT, buff=0.16)
            .move_to([2.6, -1.9, 0])
        )
        self.play(FadeIn(sum_line, shift=UP * 0.1), run_time=self.rt(0.9))
        self.play(Indicate(sum_line[1], color=GOLD, scale_factor=1.2), run_time=self.rt(0.9))

        result = fm("D = −15", 34, GOLD).move_to([cx, cy - 2.05, 0])
        self.play(FadeOut(caption), FadeIn(result, scale=0.85), run_time=self.rt(0.9))
        self.end_beat()

        # ============================================== 08 换第三列验证
        self.show_sub(["换第三列：3×8 + 5×(−3) + 6×(−4) = −15"])
        col_rect = Rectangle(
            width=0.85, height=2 * sp + 0.85, color=GOLD, stroke_width=3
        ).move_to(pos(1, 2))
        board_col = SurroundingRectangle(
            VGroup(*[board[r * 3 + 2] for r in range(3)]),
            color=GOLD,
            stroke_width=2.5,
            buff=0.07,
        )
        line_c1 = fm("A<sub>13</sub> = 8，A<sub>23</sub> = −3，A<sub>33</sub> = −4", 23, GOLD)
        line_c1.move_to([2.7, 0.85, 0])
        line_c2 = (
            VGroup(fm("3×8 + 5×(−3) + 6×(−4) =", 25, INK), fm("−15", 28, GOLD))
            .arrange(RIGHT, buff=0.18)
            .move_to([2.7, 0.05, 0])
        )

        self.play(
            FadeOut(row_rect),
            FadeOut(board_row),
            FadeOut(sum_line),
            *[FadeOut(m) for m in made],
            run_time=self.rt(0.8),
        )
        # 换视角验证：第二行恢复常规亮度，避免与算式里的 5 对不上
        self.play(
            *[grid[3 + c].animate.set_color(INK) for c in range(3)],
            run_time=self.rt(0.4),
        )
        self.play(Create(col_rect), Create(board_col), run_time=self.rt(1.0))
        self.play(FadeIn(line_c1, shift=UP * 0.08), run_time=self.rt(0.8))
        self.play(FadeIn(line_c2, shift=UP * 0.08), run_time=self.rt(0.9))
        self.play(Indicate(line_c2[1], color=GOLD, scale_factor=1.2), run_time=self.rt(1.0))
        self.end_beat()

        # ============================================== 09 结论
        self.show_sub(["任一行（列）都能展开", "含 0 越多，计算越省力"])
        conclusion = fm("D = −15，按行按列结果一致", 25, GOLD)
        conclusion.move_to([0, -2.58, 0])
        self.play(FadeIn(conclusion, shift=UP * 0.1), run_time=self.rt(1.0))
        self.end_beat()

        # ============================================== 收尾
        self.play(
            FadeOut(
                VGroup(
                    title, heading, det, lab_d, board, board_lab, formula,
                    formula_sub, col_rect, board_col, result, line_c1,
                    line_c2, conclusion, self.cur_sub,
                )
            ),
            run_time=self.rt(1.0),
        )
        self.wait(self.rt(1.0))


class DetExpansion(DetExpansionBase):
    """正常节奏（约 1 分钟）。"""

    TIMING = "timings.json"
    SPEED = 1.0


class DetExpansionSlow(DetExpansionBase):
    """更慢一版：节拍拉长 30%，动画放慢到 0.8 倍。"""

    TIMING = "timings_slow.json"
    SPEED = 0.8
