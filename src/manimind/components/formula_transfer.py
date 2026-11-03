"""Copy a semantic formula from its visible origin, retaining its history.

The returned native animation owns the traveling copy until cleanup. The scene
and reviewer consume its geometry; any formula/route/timing change invalidates
observations. This helper does not infer algebra or guarantee collision safety.
"""

from .formula_motion import SemanticFormula, matching_transform


def copy_formula_transform(source, target, *, pairs=None, run_time=1,
                           path_arc=0, **kwargs):
    """Keep source readable while an unrelocated copy becomes target.

    Authors can provide explicit pairings or compose native waypoint actions
    for crossings. In particular, do not shift the copy into the destination
    row before this animation starts: that would hide the source-to-row path.
    """
    if not isinstance(source, SemanticFormula) or not isinstance(target, SemanticFormula):
        raise TypeError("Copy transfer requires separate native semantic formulas")
    if source is target:
        raise ValueError("History and destination must be separate formulas")
    moving = source.copy()
    animation = matching_transform(moving, target, pairs=pairs, run_time=run_time,
                                   path_arc=path_arc, unmatched_in_place=True, **kwargs)
    animation.retained_source = source
    return animation
