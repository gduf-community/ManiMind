"""Two measured overlay repairs over the frozen visual-v006 author scene.

Writer: 01a19f6b-1725-7be3-a4d8-bf988a308b31. Consumers: native renderer,
tests and independent reviewers. Lifetime: one bound revision. Source, grouping,
clock or pixels changing invalidates evidence. No approval or publication.
"""

from derivative_ch04_traceable import DerivativeChainTraceable, AUTHOR_AGENT
from manimlib import FadeIn, FadeOut, VGroup, Transform


class DerivativeChainTraceableV007(DerivativeChainTraceable):
    def carry(self, source, target, start, end, role):
        if role not in {"subtract_affine_states", "collect_4_times_3"}:
            return super().carry(source, target, start, end, role)
        self.at(start)
        self.sample("active_replacement", role=role, origin=source.get_center().tolist(),
                    destination=target.get_center().tolist(), end=self._cue["start"]+end)
        if role == "subtract_affine_states":
            self.at(end, Transform(source, target))
            self.remove(source)
            self.add(target)
            return

        # Carry the numerical multiplier below the intact inner expression,
        # then collect 4 and 3. Only the active row, never a retained copy, moves.
        coefficient, multiplier = source.tag("coefficient"), source.tag("rate")
        inside, power = source.tag("input"), source.tag("power")
        selected = {id(g) for p in (coefficient, multiplier, inside, power)
                    for g in p.family_members_with_points()}
        old_syntax = VGroup(*(g for g in source.family_members_with_points() if id(g) not in selected))
        selected_target = {id(g) for k in ("coefficient", "input", "power")
                           for g in target.tag(k).family_members_with_points()}
        new_syntax = VGroup(*(g for g in target.family_members_with_points() if id(g) not in selected_target))
        self.remove(source)
        body = VGroup(inside, power)
        self.add(coefficient, multiplier, body, old_syntax)
        waypoint = multiplier.copy().move_to(coefficient.get_center()+[.6, -.6, 0])
        self.at(start+.8, Transform(multiplier, waypoint, path_arc=-.55))
        factors = VGroup(coefficient, multiplier)
        self.remove(coefficient, multiplier)
        self.add(factors)
        self.at(end, Transform(factors, target.tag("coefficient")),
                Transform(body, VGroup(target.tag("input"), target.tag("power"))),
                Transform(old_syntax, new_syntax))
        self.remove(factors, body, old_syntax, new_syntax)
        self.add(target)
