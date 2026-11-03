"""Consume four conflicting working fractions over permanently frozen inputs."""

from manimlib import FadeIn
from derivative_ch02_traceable_v011 import DerivativeCh02TraceableV011


class DerivativeCh02TraceableV012(DerivativeCh02TraceableV011):
    CONSUME_FRACTIONS = frozenset({
        "square_factor_h", "cubic_divide_h", "exp_split_power", "sine_angle_substitution"
    })
    RESTORE_GIVENS = frozenset({"exp_split_power", "sine_angle_substitution"})

    def sample(self, kind, **values):
        working = getattr(self, "_consumed_fraction", None)
        if working and values.get("transition") == working[0]:
            source = working[1]
            den = source.tag("den")
            values.update(working_source_present=source in self.mobjects,
                          working_denominator_bounds=[float(den.get_left()[0]), float(den.get_right()[0]),
                                                      float(den.get_bottom()[1]), float(den.get_top()[1])])
        return super().sample(kind, **values)

    def transfer(self, identity, source, target, pairs, start, end, **kwargs):
        if identity not in self.CONSUME_FRACTIONS:
            return super().transfer(identity, source, target, pairs, start, end, **kwargs)
        self._consumed_fraction = (identity, source)
        result = super().transfer(identity, source, target, pairs, start, end, **{**kwargs, "retain": False})
        self._consumed_fraction = None
        if identity in self.RESTORE_GIVENS:
            self.at(end + .15, FadeIn(source))
            self.sample("traceable_history", transition=identity, phase="given_restored_after_landing",
                        source_tex=source.get_tex(), target_tex=target.get_tex())
        else:
            # Later explicit FadeOut cleanup must not resurrect a consumed row.
            source.set_opacity(0)
            self.sample("traceable_history", transition=identity, phase="working_row_consumed",
                        source_tex=source.get_tex(), target_tex=target.get_tex())
        return result
