"""Versioned readability and route repair over permanently frozen v009 inputs.

Only this candidate owns its temporary formula copies and source choices.
Any source, clock or layout change expires its evidence, never old consumers.
"""

from manimlib import FadeIn, FadeOut, Group, Transform, linear
from derivative_ch02_traceable import DerivativeCh02Traceable


class DerivativeCh02TraceableV010(DerivativeCh02Traceable):
    def tf(self, latex, tokens, y, x=0, size=37, width=12.0, colors=None):
        if self._cue["id"] == "reciprocal" and y == .8:
            y = .25
        if self._cue["id"] == "root" and "top" in tokens and "den" in tokens and latex.startswith(r"\frac{(\sqrt"):
            tokens = {**tokens, "top_sum": (r"\sqrt{x+h}+\sqrt x", 0),
                      "bottom_sum": (r"\sqrt{x+h}+\sqrt x", 1)}
        obj = super().tf(latex, tokens, y, x, size, width, colors)
        if self._cue["id"] == "logarithm" and latex.startswith(r"\Delta y="):
            self._log_dy = obj
        return obj

    def reveal(self, obj, start, end):
        if self._cue["id"] == "logarithm" and start == 43.2:
            start, end = 43.7, 44.4
        return super().reveal(obj, start, end)

    def transfer(self, identity, source, target, pairs, start, end, *, retain=False, arc=0, serial=False):
        windows = {"root_difference_squares": (16.4, 18.8), "root_cancel_x": (19.0, 20.6),
                   "root_divide_h": (20.8, 23.8), "log_factor_exponential": (38.2, 40.8),
                   "log_replace_exp_y": (41.0, 43.6)}
        start, end = windows.get(identity, (start, end))
        if identity == "root_multiply_conjugate":
            return self.conjugate_product(source, target)
        if identity == "reciprocal_cancel_x":
            return self.cancel_reciprocal_numerator(source, target)
        self.at(start)
        pairs = list(pairs)
        moving = {a: source.tag(a).copy() for a, _ in pairs}
        destinations = {a: target.tag(b) for a, b in pairs}
        used = {id(g) for part in destinations.values() for g in part.family_members_with_points()}
        syntax = Group(*(g for g in target.family_members_with_points() if id(g) not in used))
        driver, phase, active = Group(), "source", None

        def sample(_):
            self.sample("traceable_formula", transition=identity, cue=self._cue["id"], phase=phase,
                        retained=retain, active_role=active, source_tex=source.get_tex(), target_tex=target.get_tex(),
                        moving={key: part.get_center().tolist() for key, part in moving.items()},
                        target={b: target.tag(b).get_center().tolist() for _, b in pairs},
                        widths={key: part.get_width() for key, part in moving.items()})

        sample(driver)
        self.add(driver, *moving.values())
        driver.add_updater(sample)
        if not retain:
            phase = "clear_old_syntax"
            self.at(start + .2, FadeOut(source))
        shrinking = {key for key, part in moving.items() if destinations[key].get_width() < .75 * part.get_width()}
        if shrinking:
            if retain:
                phase = "departure_from_retained_source"
                self.at(start + .45, *(Transform(moving[key], moving[key].copy().move_to(
                    (moving[key].get_center() + destinations[key].get_center()) / 2)) for key in shrinking), rate_func=linear)
            phase = "local_operation_at_readable_source"
            self.at(start + (1.15 if retain else .9), *(Transform(moving[key], destinations[key].copy().move_to(
                moving[key].get_center())) for key in shrinking))
        phase = "travel_readable_term"
        if identity == "log_reciprocal_limit":
            # Separate lanes keep the two increments distinct while their roles swap.
            first = self.time - self._cue["start"]
            for fraction, waypoint in ((.35, "departure"), (.7, "height"), (1., "landing")):
                animations = []
                for key, part in moving.items():
                    dx, dy, _ = destinations[key].get_center()
                    side = 1.7 if key == "dx" else 4.7 if key == "dy" else 6.1
                    point = [side, part.get_center()[1], 0] if waypoint == "departure" else (
                        [side, dy, 0] if waypoint == "height" else [dx, dy, 0])
                    animations.append(Transform(part, part.copy().move_to(point)))
                self.at(first + (end - .6 - first) * fraction, *animations, rate_func=linear)
        elif serial:
            first = self.time - self._cue["start"]
            for index, (key, part) in enumerate(moving.items()):
                active = key
                self.at(first + (index + 1) * (end - .6 - first) / len(moving),
                        Transform(part, part.copy().move_to(destinations[key].get_center())), rate_func=linear)
        else:
            self.at(end - .6, *(Transform(part, part.copy().move_to(destinations[key].get_center()), path_arc=arc)
                                for key, part in moving.items()), rate_func=linear)
        phase, active = "local_operation_at_destination", None
        self.at(end - .25, *(Transform(part, destinations[key].copy()) for key, part in moving.items()))
        phase = "new_syntax"
        self.at(end, FadeIn(syntax))
        driver.clear_updaters()
        self.remove(driver, syntax, *moving.values())
        self.add(target)
        self.sample("traceable_complete", transition=identity, cue=self._cue["id"],
                    source_tex=source.get_tex(), target_tex=target.get_tex())
        if identity == "root_limit":
            self.at(end + .15, FadeOut(self._chosen_conjugate))
        return target

    def gather(self, identity, target, tracks, start, end, *, arc=0, retire=()):
        if identity == "reciprocal_common":
            return self.reciprocal_common_by_voice(target, tracks)
        elif identity == "log_subtract_relations":
            end = 38.0
        self.at(start)
        tracks = list(tracks)
        priority = {"reciprocal_common": {"den", "bottom_old", "bottom_changed"},
                    "log_base_restore_k": {"input", "coefficient"},
                    "sine_apply_limits": {"one", "zero"},
                    "root_multiply_conjugate": {"den", "bottom_sum"},
                    "log_subtract_relations": {"new_x", "new_exp"},
                    "exp_apply_limit": {"limit"}}
        order = sorted(range(len(tracks)), key=lambda i: (
            0 if tracks[i][2] in priority.get(identity, set()) else 1,
            target.tag(tracks[i][2]).get_center()[0]))
        moving = [source.tag(source_id).copy() for source, source_id, _ in tracks]
        destinations = [target.tag(target_id) for _, _, target_id in tracks]
        used = {id(g) for part in destinations for g in part.family_members_with_points()}
        syntax = Group(*(g for g in target.family_members_with_points() if id(g) not in used))
        driver, phase, active = Group(), "source", None

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
        hidden_history = []
        for sequence, index in enumerate(order):
            part, destination = moving[index], destinations[index]
            active, phase = tracks[index][2], "travel_readable_term"
            self.add(part)
            departure = first + sequence * span
            landing = first + (sequence + 1) * span
            if identity == "log_subtract_relations" and sequence == 2:
                endpoint = tracks[next(i for i, t in enumerate(tracks) if t[2] == "new_x")][0]
                hidden_history = [endpoint, self._log_dy]
                self.at(departure + .15, *(FadeOut(obj) for obj in hidden_history))
            if identity == "reciprocal_common":
                sx, sy, _ = part.get_center()
                dx, dy, _ = destination.get_center()
                side = -4.8 if sx < 0 else 4.8
                points = [[side, sy, 0], [side, 1.15, 0], [dx, 1.15, 0], [dx, dy, 0]]
                for step, point in enumerate(points):
                    self.at(departure + (step + 1) * (span - .15) / 4,
                            Transform(part, part.copy().move_to(point)), rate_func=linear)
            elif identity == "exp_apply_limit" and active == "factor":
                dx, dy, _ = destination.get_center()
                sx, sy, _ = part.get_center()
                for step, point in enumerate([[-4.8, sy, 0], [-4.8, dy, 0], [dx, dy, 0]]):
                    self.at(departure + (step + 1) * (span - .15) / 3,
                            Transform(part, part.copy().move_to(point)), rate_func=linear)
            else:
                self.at(landing - .15, Transform(part, part.copy().move_to(destination.get_center()), path_arc=arc), rate_func=linear)
            phase = "resolve_operation"
            self.at(landing, Transform(part, destination.copy()))
        phase, active = "new_syntax", None
        self.at(end, FadeIn(syntax))
        driver.clear_updaters()
        self.remove(driver, syntax, *moving)
        self.add(target)
        if hidden_history:
            self.at(end + .15, *(FadeIn(obj) for obj in hidden_history))
        self.sample("traceable_complete", transition=identity, cue=self._cue["id"], target_tex=target.get_tex())
        return target

    def reciprocal_common_by_voice(self, target, tracks):
        self.at(13.0)
        moving = [source.tag(a).copy() for source, a, _ in tracks]
        destinations = [target.tag(b) for _, _, b in tracks]
        driver, phase, active = Group(), "source", None

        def sample(_):
            self.sample("traceable_gather", transition="reciprocal_common", cue=self._cue["id"], phase=phase,
                        active_role=active, roles=[(t[1], t[2]) for t in tracks],
                        moving=[p.get_center().tolist() for p in moving],
                        target=[p.get_center().tolist() for p in destinations])

        sample(driver)
        self.add(driver)
        driver.add_updater(sample)
        # The original phrase names the numerator before it names the three denominator factors.
        for index, departure, landing in ((0, 13., 14.5), (1, 14.6, 16.9)):
            active, phase = tracks[index][2], "travel_readable_term"
            self.add(moving[index])
            self.at(landing-.15, Transform(moving[index], moving[index].copy().move_to(destinations[index].get_center())), rate_func=linear)
            self.at(landing, Transform(moving[index], destinations[index].copy()))
        numerator = self.tf(r"x-(x+h)", {"num": "x-(x+h)"}, .25)
        numerator.set_width(Group(*destinations[:2]).get_width()).move_to(Group(*destinations[:2]).get_center())
        self.at(17.15, FadeIn(numerator))
        self.remove(*moving[:2])
        self._reciprocal_numerator_note = self.tf(r"x-(x+h)=-h", {"result": "-h"}, 1.25, x=3.2, size=29, width=5.3)
        self.transfer("reciprocal_numerator_identity", numerator, self._reciprocal_numerator_note,
                      [("num", "result")], 17.3, 20.5, retain=True)
        for index, departure, landing in ((2, 21., 23.25), (3, 23.3, 24.4), (4, 24.45, 25.55)):
            self.at(departure)
            active, phase = tracks[index][2], "travel_readable_term"
            part, destination = moving[index], destinations[index]
            self.add(part)
            sx, sy, _ = part.get_center()
            dx, dy, _ = destination.get_center()
            side = -5.6 if sx < 0 else 6.1
            points = [[side, sy, 0], [side, -.7, 0], [dx, -.7, 0], [dx, dy, 0]]
            for step, point in enumerate(points):
                self.at(departure+(step+1)*(landing-.15-departure)/4,
                        Transform(part, part.copy().move_to(point)), rate_func=linear)
            self.at(landing, Transform(part, destination.copy()))
        used = {id(g) for part in destinations for g in part.family_members_with_points()}
        syntax = Group(*(g for g in target.family_members_with_points() if id(g) not in used))
        phase, active = "new_syntax", None
        self.at(25.8, FadeIn(syntax))
        driver.clear_updaters()
        self.remove(driver, syntax, numerator, *moving)
        self.add(target)
        self.sample("traceable_complete", transition="reciprocal_common", cue=self._cue["id"], target_tex=target.get_tex())
        return target

    def cancel_reciprocal_numerator(self, source, target):
        self.at(25.9)
        driver = Group()

        def sample(_):
            self.sample("traceable_formula", transition="reciprocal_cancel_x", cue=self._cue["id"],
                        phase="local_operation_at_readable_source", retained=False,
                        source_tex=source.get_tex(), target_tex=target.get_tex(),
                        moving={"num": source.tag("num").get_center().tolist()},
                        target={"num": target.tag("num").get_center().tolist()},
                        widths={"num": source.tag("num").get_width()})

        sample(driver)
        self.add(driver)
        driver.add_updater(sample)
        part = source.tag("num")
        self.at(27.3, Transform(part, target.tag("num").copy()))
        driver.clear_updaters()
        self.remove(driver, source)
        self.add(target)
        self.remove(self._reciprocal_numerator_note)
        self.sample("traceable_complete", transition="reciprocal_cancel_x", cue=self._cue["id"],
                    source_tex=source.get_tex(), target_tex=target.get_tex())
        return target

    def conjugate_product(self, source, target):
        self.at(12.6)
        self.at(12.85, source.animate.move_to([-3.2, 2.25, 0]))
        unit = self.tf(r"\frac{\sqrt{x+h}+\sqrt x}{\sqrt{x+h}+\sqrt x}=1",
                       {"top_sum": (r"\sqrt{x+h}+\sqrt x", 0),
                        "bottom_sum": (r"\sqrt{x+h}+\sqrt x", 1)}, 2.25, x=3.2, size=30, width=5.8)
        self._chosen_conjugate = unit
        self.at(13.15, FadeIn(unit))
        self.gather("root_multiply_conjugate", target,
                    [(source, "top", "top"), (source, "den", "den"),
                     (unit, "top_sum", "top_sum"), (unit, "bottom_sum", "bottom_sum")], 13.15, 16.2)
        return target
