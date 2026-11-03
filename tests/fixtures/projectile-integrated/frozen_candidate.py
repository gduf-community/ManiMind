from manimlib import *
import numpy as np
import math
from manimind.experiments.visual_first_support import VisualLessonScene


class GeneratedLesson(VisualLessonScene):
    BG = '#0B1422'
    PANEL = '#101F30'
    WHITE = '#EDF3F7'
    MUTED = '#8FA4B7'
    GRID = '#304458'
    BLUE = '#67BEFF'
    ORANGE = '#FFB36B'
    MINT = '#8AE0C8'
    X0 = -5.10
    GY = -1.55
    SX = 1.00
    SY = 0.60

    def p(self, x, y):
        return np.array([x, y, 0.0])

    def label(self, text, x, y, size=30, color=None, width=None):
        m = self.cn(text, size=size, color=color or self.WHITE)
        if width is not None and m.get_width() > width:
            m.scale(width / m.get_width())
        return m.move_to(self.p(x, y))

    def tex(self, text, x, y, size=36, color=None, width=None):
        m = self.formula(text, size=size, color=color or self.WHITE)
        if width is not None and m.get_width() > width:
            m.scale(width / m.get_width())
        return m.move_to(self.p(x, y))

    def plate(self, w, h, x, y, color=None, border=None):
        return Rectangle(width=w, height=h, fill_color=color or self.PANEL,
                         fill_opacity=1, stroke_color=border or self.GRID,
                         stroke_width=1).move_to(self.p(x, y))

    def heading(self, index, text):
        return Group(
            self.label('%02d' % index, -6.42, 3.35, 28, self.MINT),
            self.label(text, -1.55, 3.35, 44, width=9.1),
            self.label('%02d / 06' % index, 6.02, 3.35, 24, self.MUTED),
            Line(self.p(-6.65, 2.94), self.p(6.65, 2.94),
                 stroke_color=self.GRID, stroke_width=1.2)
        )

    def clock(self, x=5.12, y=1.94, state='重置 · 待释放'):
        number = DecimalNumber(0, num_decimal_places=2, font_size=35,
                               color=self.WHITE, group_with_commas=False)
        number.move_to(self.p(x + 0.04, y - 0.02))
        status = self.label(state, x, y - 0.44, 23, self.MUTED, 2.42)
        root = Group(
            self.plate(2.65, 1.32, x, y + 0.02),
            self.label('模型时钟', x, y + 0.43, 23, self.MUTED),
            self.tex('t=', x - 0.78, y - 0.02, 34),
            number,
            self.tex(r'\mathrm{s}', x + 0.87, y - 0.02, 31),
            status
        )
        return {'root': root, 'number': number, 'status': status, 'x': x, 'y': y}

    def state(self, clock, text, color=None):
        old = clock['status']
        new = self.label(text, clock['x'], clock['y'] - 0.44, 23,
                         color or self.MUTED, 2.42)
        clock['root'].remove(old)
        clock['root'].add(new)
        clock['status'] = new

    def page(self, root, duration=0.6):
        if self.current_page is None:
            self.play(FadeIn(root), run_time=duration)
        else:
            self.play(FadeOut(self.current_page), run_time=duration / 3)
            self.play(FadeIn(root), run_time=2 * duration / 3)
        self.current_page = root

    def reveal(self, root, obj, duration=0.6):
        root.add(obj)
        self.play(FadeIn(obj), run_time=duration)
        return obj

    def flash(self, root, positions, duration=0.4):
        rings = Group(*[
            Circle(radius=0.24, stroke_color=c, stroke_width=3,
                   fill_opacity=0).move_to(pos)
            for pos, c in positions
        ])
        root.add(rings)
        self.play(FadeIn(rings), run_time=duration / 2)
        self.play(Transform(rings, rings.copy().scale(1.65).set_opacity(0)),
                  run_time=duration / 2)

    def pos(self, x, y):
        return self.p(self.X0 + self.SX * x, self.GY + self.SY * y)

    def height_brace(self, x, bottom, top, text, color, text_x=None, size=31):
        if text_x is None:
            text_x = x - 0.38
        lines = VGroup(
            Line(self.p(x, bottom), self.p(x, top), stroke_color=color, stroke_width=2),
            Line(self.p(x - 0.10, bottom), self.p(x + 0.10, bottom), stroke_color=color, stroke_width=2),
            Line(self.p(x - 0.10, top), self.p(x + 0.10, top), stroke_color=color, stroke_width=2)
        )
        return Group(lines, self.tex(text, text_x, (bottom + top) / 2,
                                     size, color, 1.12))

    def range_bar(self, xa, xb, y, color, text, size=30):
        return Group(
            VGroup(
                Line(self.p(xa, y), self.p(xb, y), stroke_color=color, stroke_width=2.4),
                Line(self.p(xa, y - 0.08), self.p(xa, y + 0.08), stroke_color=color, stroke_width=2.4),
                Line(self.p(xb, y - 0.08), self.p(xb, y + 0.08), stroke_color=color, stroke_width=2.4)
            ),
            self.tex(text, (xa + xb) / 2, y - 0.25, size, color,
                     max(2.0, xb - xa + 0.1))
        )

    def axes(self, with_height=True):
        ground = Group(
            Rectangle(width=9.7, height=0.13, fill_color='#1C2D3E',
                      fill_opacity=1, stroke_width=0).move_to(self.p(-1.45, self.GY - 0.10)),
            Line(self.p(-6.30, self.GY), self.p(3.40, self.GY),
                 stroke_color=self.MUTED, stroke_width=2)
        )
        guides = VGroup(*[
            Line(self.pos(0, yy), self.pos(8.35, yy), stroke_color=self.GRID,
                 stroke_width=1).set_opacity(0.32)
            for yy in (2.5, 5)
        ])
        root = Group(
            guides, ground,
            Arrow(self.pos(0, 0), self.pos(0, 5.85), buff=0,
                  fill_color=self.MUTED, thickness=1.8),
            Arrow(self.pos(0, 0), self.pos(8.55, 0), buff=0,
                  fill_color=self.MUTED, thickness=1.8),
            self.tex(r'y\,/\,\mathrm{m}', -5.45, 2.15, 28, self.MUTED),
            self.tex(r'x\,/\,\mathrm{m}', 3.18, -1.87, 27, self.MUTED),
            self.tex('0', -5.33, -1.79, 25, self.MUTED),
            self.tex('y=0', -6.02, -1.26, 27, self.MUTED)
        )
        if with_height:
            brace = self.height_brace(-5.92, self.GY, self.pos(0, 5)[1],
                                       r'5\,\mathrm{m}', self.MINT, -6.36)
            root.add(brace)
        return root

    def curve(self, mapper, vx, h, t, color, width=2.8, opacity=0.80):
        m = VMobject(stroke_color=color, stroke_width=width, fill_opacity=0)
        self.update_curve(m, mapper, vx, h, t)
        return m.set_stroke(opacity=opacity).set_fill(opacity=0)

    def update_curve(self, curve, mapper, vx, h, t):
        T = math.sqrt(2 * h / 10)
        end = max(0.0001, min(float(t), T))
        pts = [mapper(vx * u, max(0.0, h - 5 * u * u))
               for u in np.linspace(0, end, 42)]
        curve.set_points_smoothly(pts)

    def dash_group(self, color, count=20):
        return VGroup(*[
            Line(self.p(0, 0), self.p(0.001, 0), stroke_color=color,
                 stroke_width=1.8).set_opacity(0.70)
            for _ in range(count)
        ])

    def update_dashes(self, group, start, end, phase=0.0):
        vec = end - start
        if np.linalg.norm(vec) < 0.00001:
            vec = self.p(0.00001, 0)
        n = len(group)
        for i, dash in enumerate(group):
            aa = (i + 0.04 + phase) / n
            bb = min((i + 0.38 + phase) / n, 1.0)
            dash.put_start_and_end_on(start + aa * vec, start + bb * vec)

    def standard(self, index, title, with_height=True):
        clock = self.clock()
        blue_path = self.curve(self.pos, 4, 5, 0, self.BLUE)
        orange_path = self.curve(self.pos, 8, 5, 0, self.ORANGE)
        equal = Line(self.pos(0, 5), self.pos(0.0001, 5),
                     stroke_color=self.MINT, stroke_width=1.7).set_opacity(0.55)
        blue_ball = Dot(self.pos(0, 5), radius=0.105, fill_color=self.BLUE)
        orange_ball = Circle(radius=0.155, stroke_color=self.ORANGE,
                             stroke_width=3.2, fill_opacity=0).move_to(self.pos(0, 5))
        speeds = Group(
            self.tex(r'v_x=4\,\mathrm{m/s}', 5.12, 0.67, 32, self.BLUE, 2.65),
            self.tex(r'v_x=8\,\mathrm{m/s}', 5.12, 0.10, 32, self.ORANGE, 2.65)
        )
        arrows = VGroup(
            Arrow(self.pos(0, 5), self.pos(0, 5) + 2.05 * RIGHT, buff=0,
                  fill_color=self.ORANGE, thickness=2.0),
            Arrow(self.pos(0, 5), self.pos(0, 5) + 1.025 * RIGHT, buff=0,
                  fill_color=self.BLUE, thickness=2.7)
        )
        root = Group(self.heading(index, title), self.axes(with_height),
                     blue_path, orange_path, equal, arrows,
                     blue_ball, orange_ball, speeds, clock['root'])
        d = {'root': root, 'clock': clock, 'blue_path': blue_path,
             'orange_path': orange_path, 'blue_ball': blue_ball,
             'orange_ball': orange_ball, 'equal': equal, 'arrows': arrows,
             'vertical': None, 'horizontal': None}

        def draw(t):
            tt = min(max(float(t), 0.0), 1.0)
            yy = max(0.0, 5 - 5 * tt * tt)
            bp = self.pos(4 * tt, yy)
            op = self.pos(8 * tt, yy)
            blue_ball.move_to(bp)
            orange_ball.move_to(op)
            self.update_curve(blue_path, self.pos, 4, 5, tt)
            self.update_curve(orange_path, self.pos, 8, 5, tt)
            equal.put_start_and_end_on(bp, op + self.p(0.00001, 0))
            clock['number'].set_value(float(t))
            if d['vertical'] is not None:
                v = d['vertical']
                pp = self.pos(0, yy)
                self.update_dashes(v['blue'], pp, bp, 0.0)
                self.update_dashes(v['orange'], pp, op, 0.5)
                v['bmark'].move_to(pp)
                v['omark'].move_to(pp)
            if d['horizontal'] is not None:
                q = d['horizontal']
                bground, oground = self.pos(4 * tt, 0), self.pos(8 * tt, 0)
                self.update_dashes(q['blue'], bground, bp)
                self.update_dashes(q['orange'], oground, op)
                q['bmark'].move_to(bground)
                q['omark'].move_to(oground)
        d['draw'] = draw
        draw(0)
        return d

    def run_standard(self, d, start, end, duration):
        d['root'].remove(d['arrows'])
        self.play(UpdateFromAlphaFunc(d['root'],
                  lambda m, a: d['draw'](start + (end - start) * a)),
                  run_time=duration, rate_func=linear)

    def vertical_projection(self, d, t):
        b = self.dash_group(self.BLUE)
        o = self.dash_group(self.ORANGE)
        bm = Circle(radius=0.145, stroke_color=self.BLUE, stroke_width=3,
                    fill_opacity=0)
        om = Dot(radius=0.065, fill_color=self.ORANGE)
        group = Group(b, o, bm, om)
        d['vertical'] = {'blue': b, 'orange': o, 'bmark': bm, 'omark': om}
        d['draw'](t)
        return group

    def horizontal_projection(self, d, t):
        b = self.dash_group(self.BLUE, 17)
        o = self.dash_group(self.ORANGE, 17)
        bm = Dot(radius=0.065, fill_color=self.BLUE)
        om = Circle(radius=0.10, stroke_color=self.ORANGE, stroke_width=2,
                    fill_opacity=0)
        group = Group(b, o, bm, om)
        d['horizontal'] = {'blue': b, 'orange': o, 'bmark': bm, 'omark': om}
        d['draw'](t)
        return group

    def time_tick(self, t, y):
        label_y = self.pos(0, y)[1] + (0.16 if y > 0 else -0.37)
        return Group(
            Line(self.pos(0, y) + 0.17 * LEFT,
                 self.pos(0, y) + 0.18 * RIGHT,
                 stroke_color=self.MINT, stroke_width=2.5),
            self.tex('t=' + t, -6.05, label_y, 25, self.MUTED, 1.55)
        )

    def construct(self):
        self.current_page = None
        background = Rectangle(width=14.3, height=8.1, fill_color=self.BG,
                               fill_opacity=1, stroke_width=0)
        footer = Group(
            Line(self.p(-6.65, -3.42), self.p(6.65, -3.42),
                 stroke_color=self.GRID, stroke_width=1),
            self.label('质点 · 均匀重力场 · 无空气阻力', -3.35, -3.70,
                       25, self.MUTED, 6.5),
            self.tex(r'v_{y0}=0,\quad g=10\,\mathrm{m/s^2}',
                     3.35, -3.70, 28, self.MUTED, 5.5)
        )
        self.add(background, footer)

        # 1. The same release point, two horizontal speeds.
        d = self.standard(1, '横速改变了什么？')
        gravity_reference = Group(
            Arrow(self.p(2.25, 1.55), self.p(2.25, 0.68), buff=0,
                  fill_color=self.MINT, thickness=2.6),
            self.tex(r'g=10\,\mathrm{m/s^2}', 2.25, 0.29,
                     28, self.MINT, 2.2)
        )
        d['root'].add(gravity_reference)
        self.page(d['root'], 0.9)
        self.mark('launch_conditions_visible')
        self.until(4.7)
        self.play(FadeOut(d['arrows']), FadeOut(gravity_reference), run_time=0.3)
        d['root'].remove(gravity_reference)
        self.state(d['clock'], '4倍慢放', self.MINT)
        self.run_standard(d, 0, 0.5, 2.0)
        self.mark('first_equal_height_visible')
        self.run_standard(d, 0.5, 1.0, 2.0)
        self.state(d['clock'], '暂停 · 已落地')
        self.flash(d['root'], [(self.pos(4, 0), self.BLUE),
                               (self.pos(8, 0), self.ORANGE)], 0.5)
        self.mark('first_simultaneous_landing')
        common = Group(
            self.label('共同落地时间', 5.12, -0.83, 25, self.MUTED),
            self.tex(r'T=1.00\,\mathrm{s}', 5.12, -1.38, 38, self.MINT, 2.65)
        )
        self.reveal(d['root'], common, 0.6)
        ranges = Group(
            self.range_bar(self.X0, self.X0 + 4, -2.10, self.BLUE, r'4\,\mathrm{m}', 33),
            self.range_bar(self.X0, self.X0 + 8, -2.75, self.ORANGE, r'8\,\mathrm{m}', 33)
        )
        self.reveal(d['root'], ranges, 0.9)
        self.mark('first_ranges_visible')
        self.until(14.2)
        self.play(Indicate(common, color=self.MINT, scale_factor=1.04), run_time=0.8)
        self.until(18.0)

        # 2. A paused observation, then a continuous replay of the projections.
        d = self.standard(2, '竖直方向发生了什么？', with_height=False)
        self.page(d['root'], 0.6)
        self.until(19.0)
        self.play(FadeOut(d['arrows']), run_time=0.3)
        self.state(d['clock'], '4倍慢放', self.MINT)
        self.run_standard(d, 0, 0.5, 2.0)
        self.state(d['clock'], '暂停', self.MINT)
        grav = Group(
            Arrow(self.pos(2, 3.75) + 0.16 * DOWN,
                  self.pos(2, 3.75) + 1.02 * DOWN, buff=0,
                  fill_color=self.MINT, thickness=3),
            Arrow(self.pos(4, 3.75) + 0.16 * DOWN,
                  self.pos(4, 3.75) + 1.02 * DOWN, buff=0,
                  fill_color=self.MINT, thickness=3),
            self.tex('g', self.pos(2, 3.75)[0] + 0.30, -0.04, 31, self.MINT),
            self.tex('g', self.pos(4, 3.75)[0] + 0.30, -0.04, 31, self.MINT),
            self.tex('a_x=0', 5.12, -0.88, 35),
            self.tex('a_y=-g', 5.12, -1.47, 35, self.MINT),
            self.tex('v_{y0}=0', 5.12, -2.06, 35)
        )
        self.reveal(d['root'], grav, 0.65)
        self.mark('equal_gravity_visible')
        projection = self.vertical_projection(d, 0.5)
        self.reveal(d['root'], projection, 0.65)
        coords = Group(
            self.tex(r'x=2\,\mathrm{m}', -3.10, 1.17, 29, self.BLUE, 1.85),
            self.tex(r'x=4\,\mathrm{m}', -1.10, 1.17, 29, self.ORANGE, 1.85),
            self.tex(r'3.75\,\mathrm{m}', -6.08, 0.70, 28, self.MINT, 1.55)
        )
        self.reveal(d['root'], coords, 0.4)
        self.mark('vertical_projections_coincide')
        self.until(25.0)
        self.play(FadeOut(grav), FadeOut(coords), run_time=0.5)
        d['root'].remove(grav, coords)
        self.state(d['clock'], '重置 · t = 0')
        d['draw'](0)
        d['equal'].set_opacity(0.23)
        self.wait(0.5)
        tick0 = self.time_tick('0', 5)
        d['root'].add(tick0)
        self.state(d['clock'], '4倍慢放', self.MINT)
        self.run_standard(d, 0, 0.5, 2.0)
        d['root'].add(self.time_tick('0.50', 3.75))
        self.run_standard(d, 0.5, 1.0, 2.0)
        d['root'].add(self.time_tick('1.00', 0))
        self.state(d['clock'], '暂停 · 已落地')
        same_y = Group(
            self.label('竖直投影重合', 5.12, -0.88, 27, self.MINT, 2.6),
            self.tex('y_1(t)=y_2(t)', 5.12, -1.54, 37, self.MINT, 2.85)
        )
        self.reveal(d['root'], same_y, 0.7)
        self.mark('shared_vertical_motion_complete')
        self.until(33.0)
        self.play(Indicate(same_y, color=self.MINT, scale_factor=1.04), run_time=0.8)
        self.until(38.0)

        # 3. The ground condition is applied to the shared vertical motion.
        clock = self.clock()
        hb = self.height_brace(-5.92, self.GY, self.pos(0, 5)[1],
                               'h', self.MINT, -6.34, 39)
        ghost = Group(
            self.curve(self.pos, 4, 5, 1, self.BLUE, 1.5, 0.12),
            self.curve(self.pos, 8, 5, 1, self.ORANGE, 1.5, 0.12)
        )
        bmark = Dot(self.pos(0, 5), radius=0.105, fill_color=self.BLUE)
        omark = Circle(radius=0.155, stroke_color=self.ORANGE,
                       stroke_width=3.0, fill_opacity=0).move_to(self.pos(0, 5))
        root = Group(self.heading(3, '落地时间从哪里来？'), self.axes(False),
                     ghost, hb, bmark, omark, clock['root'],
                     self.label('共同竖直投影', -3.76, 2.18, 26, self.MINT, 2.7))
        self.page(root, 0.6)
        part_y = self.formula('y=', size=43)
        part_h = self.formula('h', size=43, color=self.MINT)
        part_drop = self.formula(r'-\frac{1}{2}gt^2', size=43)
        equation = Group(part_y, part_h, part_drop).arrange(RIGHT, buff=0.13)
        equation.move_to(self.p(1.18, 1.75))
        self.until(39.0)
        self.reveal(root, equation, 0.8)
        self.play(Indicate(hb, color=self.MINT, scale_factor=1.035),
                  Indicate(part_h, color=self.MINT, scale_factor=1.12), run_time=0.6)
        self.mark('vertical_equation_linked')
        self.until(41.0)
        self.state(clock, '4倍慢放', self.MINT)

        def vertical_fall(m, a):
            t = a
            point = self.pos(0, max(0.0, 5 - 5 * t * t))
            bmark.move_to(point)
            omark.move_to(point)
            clock['number'].set_value(t)
        self.play(UpdateFromAlphaFunc(root, vertical_fall), run_time=4.0, rate_func=linear)
        self.state(clock, '暂停 · 已落地')
        self.flash(root, [(self.pos(0, 0), self.MINT)], 0.4)
        ground_eq = Group(
            self.tex('y=0', -4.27, -1.20, 36, self.MINT),
            self.tex(r'0=h-\frac{1}{2}gT^2', 1.18, 0.50, 43, width=5.25)
        )
        self.reveal(root, ground_eq, 0.6)
        self.mark('ground_condition_applied')
        positive_root = self.tex(r'T=\sqrt{\frac{2h}{g}}\quad(T>0)',
                                 1.18, -0.65, 43, self.MINT, 5.4)
        self.until(47.0)
        self.reveal(root, positive_root, 0.8)
        params = self.tex(r'h=5\,\mathrm{m},\quad g=10\,\mathrm{m/s^2}',
                          1.18, -2.25, 27, self.MUTED, 4.8)
        self.until(49.0)
        self.reveal(root, params, 0.6)
        result = self.tex(r'T=1.00\,\mathrm{s}', 2.00, -2.94, 43, self.MINT, 3.6)
        self.reveal(root, result, 0.7)
        speed_join = Group(
            self.tex(r'v_x=4\,\mathrm{m/s}', -3.73, -2.53, 29, self.BLUE, 2.55),
            self.tex(r'v_x=8\,\mathrm{m/s}', -3.73, -3.14, 29, self.ORANGE, 2.55),
            Line(self.p(-2.35, -2.53), self.p(-1.10, -2.94),
                 stroke_color=self.BLUE, stroke_width=2),
            Line(self.p(-2.35, -3.14), self.p(-1.10, -2.94),
                 stroke_color=self.ORANGE, stroke_width=2),
            Arrow(self.p(-1.10, -2.94), self.p(0.26, -2.94), buff=0,
                  fill_color=self.MINT, thickness=2.1)
        )
        self.reveal(root, speed_join, 0.7)
        self.mark('landing_time_derived')
        self.until(54.0)
        self.play(Indicate(result, color=self.MINT, scale_factor=1.05), run_time=0.8)
        self.until(58.0)

        # 4. Ground projections and a physical four-metre ruler.
        d = self.standard(4, '同一段时间，横向走多远？')
        common_t = self.tex(r'T=1.00\,\mathrm{s}', 5.12, -0.69, 36,
                            self.MINT, 2.65)
        x_formula = self.tex('x=v_xt', 5.12, -1.36, 39, width=2.65)
        d['root'].add(common_t, x_formula)
        hp = self.horizontal_projection(d, 0)
        d['root'].add(hp)
        half_height = Group(
            Dot(self.pos(2, 3.75), radius=0.045, fill_color=self.BLUE).set_opacity(0.35),
            Circle(radius=0.07, stroke_color=self.ORANGE, stroke_width=1.5,
                   fill_opacity=0).move_to(self.pos(4, 3.75)).set_opacity(0.35),
            Line(self.pos(2, 3.75), self.pos(4, 3.75),
                 stroke_color=self.MINT, stroke_width=1).set_opacity(0.22)
        )
        d['root'].add(half_height)
        self.page(d['root'], 0.6)
        self.until(59.0)
        self.play(FadeOut(d['arrows']), run_time=0.2)
        self.state(d['clock'], '4倍慢放', self.MINT)
        self.run_standard(d, 0, 1, 4.0)
        self.state(d['clock'], '暂停 · 已落地')
        self.flash(d['root'], [(self.pos(4, 0), self.BLUE),
                               (self.pos(8, 0), self.ORANGE)], 0.4)
        self.mark('horizontal_projections_landed')
        range_formula = self.tex('R=v_xT', 5.12, -1.36, 39, width=2.65)
        self.play(Transform(x_formula, range_formula), run_time=0.6)
        products = Group(
            self.range_bar(self.X0, self.X0 + 4, -1.98, self.BLUE,
                           r'4\,\mathrm{m/s}\times1\,\mathrm{s}=4\,\mathrm{m}', 29),
            self.range_bar(self.X0, self.X0 + 8, -2.80, self.ORANGE,
                           r'8\,\mathrm{m/s}\times1\,\mathrm{s}=8\,\mathrm{m}', 30)
        )
        self.reveal(d['root'], products, 0.8)
        self.mark('range_products_visible')
        ruler_y = -2.62
        ruler = VGroup(
            Line(self.p(self.X0, ruler_y), self.p(self.X0 + 4, ruler_y),
                 stroke_color=self.MINT, stroke_width=6),
            *[Line(self.p(self.X0 + k, ruler_y - 0.09),
                   self.p(self.X0 + k, ruler_y + 0.09),
                   stroke_color=self.MINT, stroke_width=2.4)
              for k in range(5)]
        )
        ruler_label = self.label('4 m 标尺', 5.12, -2.20, 27, self.MINT, 2.6)
        self.until(66.0)
        self.reveal(d['root'], Group(ruler, ruler_label), 0.6)
        self.until(67.3)
        first_half = ruler.copy().set_opacity(0.30)
        d['root'].add(first_half)
        self.play(Transform(ruler, ruler.copy().shift(4 * RIGHT)), run_time=1.1)
        double = self.tex(r'v_x\times2\ \Rightarrow\ R\times2',
                          5.12, -2.90, 30, self.MINT, 2.85)
        self.reveal(d['root'], double, 0.6)
        self.mark('double_range_measured')
        self.until(74.0)

        # 5. Identical spatial scales, a fourfold height, and a clamped landed ball.
        low_x, high_x = -5.50, 0.80
        scale_x, scale_y = 0.50, 0.17
        ground_y = -1.55

        def low_pos(x, y):
            return self.p(low_x + scale_x * x, ground_y + scale_y * y)

        def high_pos(x, y):
            return self.p(high_x + scale_x * x, ground_y + scale_y * y)

        panels = Group(
            self.plate(6.20, 5.70, -3.25, -0.42),
            self.plate(6.20, 5.70, 3.25, -0.42)
        )
        chart_axes = Group()
        for mapper, origin in ((low_pos, low_x), (high_pos, high_x)):
            chart_axes.add(
                Line(self.p(origin - 0.30, ground_y), self.p(origin + 4.75, ground_y),
                     stroke_color=self.MUTED, stroke_width=2),
                Arrow(mapper(0, 0), mapper(0, 21.0), buff=0,
                      fill_color=self.MUTED, thickness=1.6),
                Arrow(mapper(0, 0), mapper(9.25, 0), buff=0,
                      fill_color=self.MUTED, thickness=1.6),
                self.tex(r'x/\mathrm{m}', origin + 4.52, -1.87, 23, self.MUTED)
            )
            for yy in (0, 5, 10, 15, 20):
                q = mapper(0, yy)
                chart_axes.add(
                    Line(q + 0.055 * LEFT, q + 0.055 * RIGHT,
                         stroke_color=self.MUTED, stroke_width=1.2),
                    self.tex(str(yy), origin - 0.32, q[1], 22, self.MUTED, 0.28)
                )
                if yy > 0:
                    chart_axes.add(Line(mapper(0, yy), mapper(8.7, yy),
                                        stroke_color=self.GRID, stroke_width=0.8).set_opacity(0.35))
            for xx in (4, 8):
                q = mapper(xx, 0)
                chart_axes.add(
                    Line(q + 0.06 * DOWN, q + 0.06 * UP,
                         stroke_color=self.MUTED, stroke_width=1.2),
                    self.tex(str(xx), q[0], ground_y - 0.25, 23, self.MUTED)
                )
        low_h = self.height_brace(low_x - 0.57, ground_y, low_pos(0, 5)[1],
                                  r'5\,\mathrm{m}', self.BLUE, low_x - 0.84, 25)
        high_h = self.height_brace(high_x - 0.57, ground_y, high_pos(0, 20)[1],
                                   r'20\,\mathrm{m}', self.ORANGE, high_x - 0.91, 25)
        lpath = self.curve(low_pos, 4, 5, 0, self.BLUE, 2.5, 0.75)
        hpath = self.curve(high_pos, 4, 20, 0, self.ORANGE, 2.5, 0.75)
        lb = Dot(low_pos(0, 5), radius=0.10, fill_color=self.BLUE)
        hb_ball = Circle(radius=0.14, stroke_color=self.ORANGE, stroke_width=3,
                         fill_opacity=0).move_to(high_pos(0, 20))
        clock = self.clock(5.16, 1.49, '预测 · 待释放')
        prediction = self.tex(r'h\times4\qquad T\,?\qquad R\,?',
                              0, -2.94, 40, self.MINT, 8.7)
        root = Group(
            self.heading(5, '高度变为四倍，会怎样？'), panels, chart_axes,
            low_h, high_h, lpath, hpath, lb, hb_ball,
            self.label('蓝组 · h = 5 m', -3.35, 2.13, 31, self.BLUE, 3.8),
            self.label('橙组 · h = 20 m', 2.36, 2.13, 31, self.ORANGE, 3.3),
            self.tex(r'v_x=4\,\mathrm{m/s}', -3.62, 2.65, 33, width=3.0),
            self.label('两组相同 · 坐标同尺度', 0.15, 2.65, 26, self.MUTED, 3.75),
            clock['root'], prediction
        )

        def height_draw(t):
            lt = min(float(t), 1.0)
            ht = min(float(t), 2.0)
            lb.move_to(low_pos(4 * lt, max(0.0, 5 - 5 * lt * lt)))
            hb_ball.move_to(high_pos(4 * ht, max(0.0, 20 - 5 * ht * ht)))
            self.update_curve(lpath, low_pos, 4, 5, lt)
            self.update_curve(hpath, high_pos, 4, 20, ht)
            clock['number'].set_value(t)

        def height_run(a, b, duration):
            self.play(UpdateFromAlphaFunc(root,
                      lambda m, u: height_draw(a + (b - a) * u)),
                      run_time=duration, rate_func=linear)

        self.page(root, 0.7)
        self.wait(0.3)
        self.mark('height_prediction_ready')
        self.until(78.2)
        self.play(FadeOut(prediction), run_time=0.3)
        root.remove(prediction)
        self.state(clock, '4倍慢放', self.MINT)
        height_run(0, 1, 4.0)
        self.state(clock, '暂停', self.MINT)
        high_dash = self.dash_group(self.ORANGE, 17)
        self.update_dashes(high_dash, high_pos(4, 0), high_pos(4, 15))
        coord_pack = Group(
            high_dash,
            self.tex(r'x=4\,\mathrm{m}', low_pos(4, 0)[0], -1.99, 29, self.BLUE, 2.0),
            self.tex(r'x=4\,\mathrm{m}', high_pos(4, 0)[0], -1.99, 29, self.ORANGE, 2.0),
            self.tex(r'y=15\,\mathrm{m}', 3.85, 0.46, 29, self.ORANGE, 2.0),
            Line(high_pos(4, 15) + self.p(0.12, -0.10), self.p(3.12, 0.65),
                 stroke_color=self.ORANGE, stroke_width=1.3)
        )
        low_time = self.tex(r'T=1.00\,\mathrm{s}', -3.22, -2.72, 34, self.BLUE, 3.1)
        root.add(coord_pack, low_time)
        self.play(FadeIn(coord_pack), FadeIn(low_time), run_time=0.5)
        self.mark('low_ball_landed_high_ball_flying')
        self.until(85.0)
        self.play(FadeOut(coord_pack), run_time=0.3)
        root.remove(coord_pack)
        self.state(clock, '4倍慢放', self.MINT)
        height_run(1, 2, 4.0)
        self.state(clock, '暂停 · 两组已落地')
        self.flash(root, [(high_pos(8, 0), self.ORANGE)], 0.4)
        high_time = self.tex(r'T=2.00\,\mathrm{s}', 3.20, -2.72, 34, self.ORANGE, 3.1)
        low_range = self.range_bar(low_x, low_x + 2.0, -2.07,
                                   self.BLUE, r'R=4\,\mathrm{m}', 28)
        high_range = self.range_bar(high_x, high_x + 4.0, -2.07,
                                    self.ORANGE, r'R=8\,\mathrm{m}', 28)
        self.reveal(root, Group(high_time, low_range, high_range), 0.7)
        self.mark('high_ball_landed')
        h_ratio = self.tex(r'h\times4', -3.90, -3.12, 32, self.MINT)
        t_ratio = self.tex(r'T\times2', 0, -3.12, 32, self.MINT)
        r_ratio = self.tex(r'R\times2', 3.90, -3.12, 32, self.MINT)
        self.until(91.2)
        self.reveal(root, h_ratio, 0.5)
        self.play(Indicate(low_h, color=self.MINT, scale_factor=1.035),
                  Indicate(high_h, color=self.MINT, scale_factor=1.035), run_time=0.6)
        self.until(93.0)
        self.reveal(root, t_ratio, 0.6)
        self.play(Indicate(low_time, color=self.MINT, scale_factor=1.04),
                  Indicate(high_time, color=self.MINT, scale_factor=1.04), run_time=0.6)
        self.until(94.8)
        self.reveal(root, r_ratio, 0.6)
        self.play(Indicate(low_range, color=self.MINT, scale_factor=1.025),
                  Indicate(high_range, color=self.MINT, scale_factor=1.025), run_time=0.6)
        self.mark('height_scaling_verified')
        self.until(102.0)

        # 6. Two recognizable experiment thumbnails support a dependency map.
        card1 = self.plate(4.88, 2.73, -4.18, 1.21)
        card2 = self.plate(4.88, 2.85, -4.18, -1.82)

        def thumb1(x, y):
            return self.p(-6.06 + 0.42 * x, 0.30 + 0.235 * y)

        thumb_fixed = Group(
            card1,
            self.label('同高度 · 横速 ×2', -4.18, 2.19, 28, width=4.3),
            self.tex(r'T=1\,\mathrm{s}', -3.18, 1.72, 28, self.MINT, 1.7),
            Line(self.p(-6.18, 0.30), self.p(-2.28, 0.30),
                 stroke_color=self.MUTED, stroke_width=1.6),
            self.curve(thumb1, 4, 5, 1, self.BLUE, 2.2, 1),
            self.curve(thumb1, 8, 5, 1, self.ORANGE, 2.2, 1),
            Dot(thumb1(4, 0), radius=0.065, fill_color=self.BLUE),
            Circle(radius=0.095, stroke_color=self.ORANGE, stroke_width=2.1,
                   fill_opacity=0).move_to(thumb1(8, 0)),
            self.tex(r'4\,\mathrm{m}', thumb1(4, 0)[0], 0.03, 26, self.BLUE),
            self.tex(r'8\,\mathrm{m}', thumb1(8, 0)[0], 0.03, 26, self.ORANGE),
            Line(thumb1(2, 3.75), thumb1(4, 3.75),
                 stroke_color=self.MINT, stroke_width=1.1).set_opacity(0.65)
        )

        def thumb2(x, y):
            return self.p(-5.96 + 0.32 * x, -2.76 + 0.081 * y)

        thumb_height = Group(
            card2,
            self.label('同横速 · 高度 ×4', -4.18, -0.71, 28, width=4.3),
            Line(self.p(-6.08, -2.76), self.p(-2.37, -2.76),
                 stroke_color=self.MUTED, stroke_width=1.6),
            self.curve(thumb2, 4, 5, 1, self.BLUE, 2.2, 1),
            self.curve(thumb2, 4, 20, 2, self.ORANGE, 2.2, 1),
            Dot(thumb2(4, 0), radius=0.065, fill_color=self.BLUE),
            Circle(radius=0.095, stroke_color=self.ORANGE, stroke_width=2.1,
                   fill_opacity=0).move_to(thumb2(8, 0)),
            self.tex(r'5\,\mathrm{m}', -6.23, thumb2(0, 5)[1], 22, self.BLUE, 0.65),
            self.tex(r'20\,\mathrm{m}', -6.20, thumb2(0, 20)[1], 22, self.ORANGE, 0.75),
            self.tex(r'T\times2', -2.80, -1.55, 29, self.MINT, 1.35),
            self.tex(r'R\times2', -2.80, -2.18, 29, self.MINT, 1.35),
            self.tex(r'4\,\mathrm{m}', thumb2(4, 0)[0], -3.04, 25, self.BLUE),
            self.tex(r'8\,\mathrm{m}', thumb2(8, 0)[0], -3.04, 25, self.ORANGE)
        )

        def node(symbol, caption, x, y, color):
            return Group(
                self.plate(1.19, 0.89, x, y, border=color),
                self.tex(symbol, x, y + 0.01, 43, color),
                self.label(caption, x, y - 0.79, 27, self.MUTED, 2.3)
            )

        hn = node('h', '高度', -0.53, 0.93, self.MINT)
        tn = node('T', '飞行时间', 2.13, 0.93, self.MINT)
        rn = node('R', '射程', 5.32, 0.93, self.WHITE)
        vn = node('v_x', '横向初速度', 2.13, -1.43, self.BLUE)
        ht_arrow = Arrow(self.p(0.14, 0.93), self.p(1.47, 0.93),
                         buff=0, fill_color=self.MINT, thickness=2.8)
        tr_arrow = Arrow(self.p(2.80, 0.93), self.p(4.64, 0.93),
                         buff=0, fill_color=self.MINT, thickness=2.8)
        vr_arrow = Arrow(self.p(2.80, -1.43), self.p(4.91, 0.36),
                         buff=0, fill_color=self.BLUE, thickness=2.8)
        tf = self.tex(r'T=\sqrt{\frac{2h}{g}}', 0.81, 1.99, 38,
                      self.MINT, 2.8)
        rf = self.tex('R=v_xT', 4.02, 1.99, 39, width=2.8)
        gfixed = self.label('g 固定', -0.51, 2.59, 28, self.MUTED, 2.0)
        root = Group(self.heading(6, '把关系连起来'), gfixed)
        self.page(root, 0.6)
        self.reveal(root, thumb_fixed, 0.6)
        self.reveal(root, Group(tn, tf), 0.6)
        self.reveal(root, Group(vn, rn, tr_arrow, vr_arrow, rf), 0.7)
        self.mark('fixed_height_relation_highlighted')
        self.until(105.2)
        self.reveal(root, thumb_height, 0.5)
        self.reveal(root, Group(hn, ht_arrow), 0.6)
        self.play(Indicate(hn[1], color=self.MINT, scale_factor=1.10), run_time=0.6)
        self.play(Indicate(tn[1], color=self.MINT, scale_factor=1.10), run_time=0.5)
        self.play(Indicate(rn[1], color=self.MINT, scale_factor=1.10), run_time=0.5)
        self.mark('height_relation_highlighted')
        self.until(108.5)
        self.play(Indicate(tf, color=self.MINT, scale_factor=1.035),
                  Indicate(rf, color=self.MINT, scale_factor=1.035), run_time=1.0)
        self.until(110.0)
        self.mark('final_relations_visible')
        self.until(114.0)
