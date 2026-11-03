"""Bounded layout correction over the frozen derivative teaching prototype."""

from derivative_intro_refined import DerivativeIntroRefinedLesson


class DerivativeIntroDeliveryLesson(DerivativeIntroRefinedLesson):
    def readable_matching(self, source, target, end, stage):
        if stage == "simplified":
            conditions = [obj for obj in self.mobjects
                          if callable(getattr(obj, "get_tex", None)) and obj.get_tex() == r"h\ne0"]
            if len(conditions) != 1:
                raise ValueError("The actual cancellation condition must remain identifiable")
            condition = conditions[0]
            self.sample("condition_relocation", phase="before", bounds=condition.get_bounding_box().tolist())
            self.play(condition.animate.move_to([4.6, -.5, 0]), run_time=.6)
            self.sample("condition_relocation", phase="after", bounds=condition.get_bounding_box().tolist())
        return super().readable_matching(source, target, end, stage)
