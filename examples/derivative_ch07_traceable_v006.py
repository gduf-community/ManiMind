"""CH07 v006: clear completed-history routes, preserve all v004 mathematics.

Local history references are written by role_formula, consumed and retired
after the stationary-position transfer. They expire on cue exit. This narrow
layout/path repair neither edits frozen v005 nor supplies review authority.
"""
from derivative_ch07_traceable import DerivativeCh07Traceable
from manimlib import FadeOut


class DerivativeCh07TraceableV006(DerivativeCh07Traceable):
    def role_formula(self, latex, tokens, x, y, size=32, width=6):
        if self._cue["id"] == "compare" and latex == r"\min f=0\quad(x=1)":
            y = 2.8
        formula = super().role_formula(latex, tokens, x, y, size=size, width=width)
        if self._cue["id"] == "candidates" and latex in (
            r"f'(x)=2(x-1)", r"f'(x)=0\ \Longrightarrow\ x=1"):
            if latex == r"f'(x)=2(x-1)":
                self._candidate_history = []
            self._candidate_history.append(formula)
        return formula

    def transfer_roles(self, origins, target, end, stage):
        super().transfer_roles(origins, target, end, stage)
        if stage == "stationary_to_candidate":
            self.beat(.46, *(FadeOut(formula) for formula in self._candidate_history))
            for formula in self._candidate_history:
                formula.set_opacity(0)
            self._candidate_history.clear()
            self.sample("candidate_history_retired", stationary_position_already_transferred=True)
