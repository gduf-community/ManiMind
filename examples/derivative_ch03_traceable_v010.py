"""Versioned local route repair; frozen 02/03 v009 consumers stay untouched.

Cue-local formulas and sampled routes belong to this candidate. Source, timing
or layout changes invalidate its evidence. Native tests do not approve pixels.
"""

from manimlib import FadeIn, FadeOut, Group, Transform, linear
from derivative_ch03_traceable import DerivativeCh03Traceable


class DerivativeCh03TraceableV010(DerivativeCh03Traceable):
    def tf(self, latex, tokens, y, x=0, size=37, width=12.0, colors=None):
        cue = self._cue["id"]
        if cue == "quotient_increment" and y in (.8, -.65):
            y = .15
        if cue == "cost_example":
            if latex.startswith("C="):
                x = 0
            elif latex.startswith("u'="):
                pass
            elif "cost_given_" not in tokens:
                x, y, size, width = 0, -1.15, 39, 11.5
        obj = super().tf(latex, tokens, y, x, size, width, colors)
        if cue == "cost_example" and latex.startswith("C="):
            self._cost_model = obj
        if cue == "cost_example" and latex.startswith("u'=") and "cost_given_" not in tokens:
            self._cost_rates = obj
        return obj

    def transfer(self, identity, source, target, pairs, start, end, *, retain=False, arc=0, serial=False):
        if identity in {"cost_expand_numerator", "quotient_expand_products"}:
            retain = False
        self.at(start)
        pairs = list(pairs)
        moving = {a: source.tag(a).copy() for a, _ in pairs}
        destinations = {a: target.tag(b) for a, b in pairs}
        used = {id(g) for part in destinations.values() for g in part.family_members_with_points()}
        syntax = Group(*(g for g in target.family_members_with_points() if id(g) not in used))
        phase = "source"
        driver = Group()

        def sample(_):
            self.sample("traceable_formula", transition=identity, cue=self._cue["id"], phase=phase,
                        retained=retain, source_tex=source.get_tex(), target_tex=target.get_tex(),
                        moving={a: part.get_center().tolist() for a, part in moving.items()},
                        target={b: target.tag(b).get_center().tolist() for _, b in pairs},
                        widths={a: part.get_width() for a, part in moving.items()})

        sample(driver)
        self.add(driver, *moving.values())
        driver.add_updater(sample)
        if not retain:
            phase = "clear_old_syntax"
            self.at(start + .2, FadeOut(source))
        shrinking = {key for key, part in moving.items()
                     if destinations[key].get_width() < .75 * part.get_width()}
        if shrinking:
            if retain:
                phase = "departure_from_retained_source"
                self.at(start + .45, *(Transform(moving[key], moving[key].copy().move_to(
                    (moving[key].get_center() + destinations[key].get_center()) / 2)) for key in shrinking),
                    rate_func=linear)
            phase = "local_operation_at_readable_source"
            self.at(start + (1.15 if retain else .9),
                    *(Transform(moving[key], destinations[key].copy().move_to(moving[key].get_center()))
                      for key in shrinking))
        phase = "travel_readable_term"
        self.at(end - .6, *(Transform(part, part.copy().move_to(destinations[key].get_center()), path_arc=arc)
                            for key, part in moving.items()), rate_func=linear)
        phase = "local_operation_at_destination"
        self.at(end - .25, *(Transform(part, destinations[key].copy()) for key, part in moving.items()))
        phase = "new_syntax"
        self.at(end, FadeIn(syntax))
        driver.clear_updaters()
        self.remove(driver, syntax, *moving.values())
        self.add(target)
        self.sample("traceable_complete", transition=identity, cue=self._cue["id"],
                    source_tex=source.get_tex(), target_tex=target.get_tex())
        if identity == "cost_cancel_square":
            self.at(end + .2, self._cost_model.animate.move_to([3.2, 1.65, 0]),
                    target.animate.move_to([3.2, -.75, 0]))
        return target

    def gather(self, identity, target, tracks, start, end, *, arc=0, retire=()):
        self.at(start)
        helpers = []
        if identity == "product_collect_areas":
            end = 56.4
        elif identity == "quotient_cross_multiply":
            end = 32.0
        elif identity == "cost_substitute":
            specs = [(r"u'=2x", "2x", -4.8), (r"v=x", "x", -1.8),
                     (r"u=x^2+4", "x^2+4", 1.4), (r"v'=1", "1", 4.8)]
            for latex, value, x in specs:
                helpers.append(self.tf(latex, {"cost_given_": value}, .45, x=x, size=29, width=2.7))
            self.at(start + .15, FadeOut(self._cost_rates))
            self.at(start + .35, *(FadeIn(obj) for obj in helpers))
            up, denominator, numerator, vp = helpers
            tracks = [(up, "cost_given_", "up"), (denominator, "cost_given_", "top_den"),
                      (numerator, "cost_given_", "num"), (vp, "cost_given_", "vp"),
                      (denominator, "cost_given_", "bottom_den")]
        moving = [source.tag(source_id).copy() for source, source_id, _ in tracks]
        destinations = [target.tag(target_id) for _, _, target_id in tracks]
        used = {id(g) for part in destinations for g in part.family_members_with_points()}
        syntax = Group(*(g for g in target.family_members_with_points() if id(g) not in used))
        denominator_roles = ({"old_v_bottom", "new_v_bottom"} if identity == "quotient_cross_multiply"
                             else {"bottom_den"} if identity == "cost_substitute" else set())
        order = sorted(range(len(tracks)), key=lambda i: (
            0 if tracks[i][2] in denominator_roles else 1, destinations[i].get_center()[0]))
        phase, active = "source", None
        driver = Group()

        def sample(_):
            self.sample("traceable_gather", transition=identity, cue=self._cue["id"], phase=phase,
                        active_role=active, roles=[(t[1], t[2]) for t in tracks],
                        moving=[part.get_center().tolist() for part in moving],
                        target=[part.get_center().tolist() for part in destinations])

        sample(driver)
        self.add(driver)
        driver.add_updater(sample)
        if retire:
            self.at(start + .25, *(FadeOut(obj) for obj in retire))
        first = self.time - self._cue["start"]
        span = (end - .25 - first) / len(order)
        for sequence, index in enumerate(order):
            part, destination = moving[index], destinations[index]
            active, phase = tracks[index][2], "travel_readable_term"
            self.add(part)
            landing = first + (sequence + 1) * span
            departure = first + sequence * span
            if identity == "product_collect_areas":
                sx, sy, _ = part.get_center()
                dx, dy, _ = destination.get_center()
                points = [[.65, sy, 0], [.65, -1.35, 0], [dx, -1.35, 0], [dx, dy, 0]]
                for step, point in enumerate(points):
                    self.at(departure + (step + 1) * (span - .15) / 4,
                            Transform(part, part.copy().move_to(point)), rate_func=linear)
            elif identity == "quotient_cross_multiply":
                sx, _, _ = part.get_center()
                dx, dy, _ = destination.get_center()
                self.at(departure + .2, Transform(part, part.copy().move_to([sx, 1.15, 0])), rate_func=linear)
                self.at(landing - .55, Transform(part, part.copy().move_to([dx, 1.15, 0])), rate_func=linear)
                self.at(landing - .15, Transform(part, part.copy().move_to([dx, dy, 0])), rate_func=linear)
            else:
                self.at(landing - .15, Transform(part, part.copy().move_to(destination.get_center())), rate_func=linear)
            phase = "resolve_operation"
            self.at(landing, Transform(part, destination.copy()))
        phase, active = "new_syntax", None
        self.at(end, FadeIn(syntax))
        driver.clear_updaters()
        self.remove(driver, syntax, *moving)
        self.add(target)
        self.sample("traceable_complete", transition=identity, cue=self._cue["id"], target_tex=target.get_tex())
        if helpers:
            self.at(end + .2, *(FadeOut(obj) for obj in helpers))
        return target
