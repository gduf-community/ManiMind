"""Two local route corrections over permanently frozen v010 source inputs."""

from manimlib import FadeIn, FadeOut, Group, Transform, linear
from derivative_ch02_traceable_v010 import DerivativeCh02TraceableV010


class DerivativeCh02TraceableV011(DerivativeCh02TraceableV010):
    def transfer(self, identity, source, target, pairs, start, end, **kwargs):
        if identity != "log_factor_exponential":
            return super().transfer(identity, source, target, pairs, start, end, **kwargs)
        self.at(38.2)
        moving = {key: source.tag(key).copy() for key in ("dx", "factor", "increment")}
        destinations = {key: target.tag(key) for key in moving}
        used = {id(g) for part in destinations.values() for g in part.family_members_with_points()}
        syntax = Group(*(g for g in target.family_members_with_points() if id(g) not in used))
        driver, phase, active = Group(), "source", None

        def sample(_):
            self.sample("traceable_formula", transition=identity, cue=self._cue["id"], phase=phase,
                        active_role=active, retained=False, source_tex=source.get_tex(), target_tex=target.get_tex(),
                        moving={key: part.get_center().tolist() for key, part in moving.items()},
                        bounds={key: [float(part.get_left()[0]), float(part.get_right()[0]),
                                      float(part.get_bottom()[1]), float(part.get_top()[1])]
                                for key, part in moving.items()},
                        target={key: part.get_center().tolist() for key, part in destinations.items()})

        sample(driver)
        self.add(driver, *moving.values())
        driver.add_updater(sample)
        phase = "clear_old_syntax"
        self.at(38.4, FadeOut(source))
        phase, active = "local_dx_and_factor_departure", "factor"
        factor_x = moving["factor"].get_center()[0]
        self.at(39.05,
                Transform(moving["dx"], destinations["dx"].copy().move_to(moving["dx"].get_center())),
                Transform(moving["factor"], moving["factor"].copy().move_to([factor_x, -.95, 0])),
                rate_func=linear)
        phase = "factor_crosses_below_waiting_increment"
        self.at(39.55,
                Transform(moving["dx"], destinations["dx"].copy()),
                Transform(moving["factor"], moving["factor"].copy().move_to(
                    [destinations["factor"].get_center()[0], -.95, 0])), rate_func=linear)
        phase = "factor_lands_left_of_increment"
        self.at(39.85, Transform(moving["factor"], destinations["factor"].copy()), rate_func=linear)
        phase, active = "local_exponential_factorization", "increment"
        self.at(40.55, Transform(moving["increment"], destinations["increment"].copy()))
        phase, active = "new_syntax", None
        self.at(40.8, FadeIn(syntax))
        driver.clear_updaters()
        self.remove(driver, syntax, *moving.values())
        self.add(target)
        self.sample("traceable_complete", transition=identity, cue=self._cue["id"],
                    source_tex=source.get_tex(), target_tex=target.get_tex())
        return target

    def gather(self, identity, target, tracks, start, end, **kwargs):
        if identity != "log_base_difference":
            return super().gather(identity, target, tracks, start, end, **kwargs)
        self.at(start)
        tracks = list(tracks)
        moving = [source.tag(source_id).copy() for source, source_id, _ in tracks]
        destinations = [target.tag(target_id) for _, _, target_id in tracks]
        used = {id(g) for part in destinations for g in part.family_members_with_points()}
        syntax = Group(*(g for g in target.family_members_with_points() if id(g) not in used))
        driver, phase, active = Group(), "source", None
        old_denominator = tracks[0][0].get_parts_by_tex(r"\ln a")
        old_denominator_bounds = [float(old_denominator.get_left()[0]), float(old_denominator.get_right()[0]),
                                  float(old_denominator.get_bottom()[1]), float(old_denominator.get_top()[1])]

        def sample(_):
            self.sample("traceable_gather", transition=identity, cue=self._cue["id"], phase=phase,
                        active_role=active, roles=[(a, b) for _, a, b in tracks],
                        moving=[part.get_center().tolist() for part in moving],
                        target=[part.get_center().tolist() for part in destinations],
                        retained_denominator_bounds=old_denominator_bounds,
                        bounds=[[float(p.get_left()[0]), float(p.get_right()[0]),
                                 float(p.get_bottom()[1]), float(p.get_top()[1])] for p in moving])

        sample(driver)
        self.add(driver)
        driver.add_updater(sample)
        span = (end - .25 - start) / len(tracks)
        for index, (part, destination) in enumerate(zip(moving, destinations, strict=True)):
            departure = start + index * span
            active = tracks[index][2]
            self.add(part)
            sx = part.get_center()[0]
            dx, dy, _ = destination.get_center()
            # Leave vertically at the true right-hand origin before crossing below the old fraction.
            for fraction, point, phase in ((.35, [sx, .8, 0], "vertical_departure_beside_old_fraction"),
                                           (.7, [dx, .8, 0], "cross_below_retained_definition"),
                                           (1., [dx, dy, 0], "land_in_own_role")):
                self.at(departure + span * fraction,
                        Transform(part, part.copy().move_to(point)), rate_func=linear)
        phase, active = "new_syntax", None
        self.at(end, FadeIn(syntax))
        driver.clear_updaters()
        self.remove(driver, syntax, *moving)
        self.add(target)
        self.sample("traceable_complete", transition=identity, cue=self._cue["id"], target_tex=target.get_tex())
        return target
