"""Caption groups on existing forced-aligned word boundaries, without audio edits.

Pure derived data: the original alignment/word estimates remain owned by the
aligner. Caption manifests bind this module and invalidate on source/estimate,
layout or media changes. These estimates do not certify listening or spelling.
"""

from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

from . import focus_captions as captions


def make_captions(alignment, style=None):
    style = captions.validate_style(style)
    duration = captions._number(alignment["duration"])
    events, previous = [], 0
    if not alignment.get("units"):
        raise ValueError("Word captions require complete aligned units")
    for unit in alignment["units"]:
        for phrase in unit["phrases"]:
            text = captions._text(phrase["text"])
            words = phrase.get("words")
            if not isinstance(words, list) or not words:
                raise ValueError("Word captions require the original word estimates")
            positions = [index for index, char in enumerate(text) if not char.isspace()]
            expected = "".join(text.split())
            actual = "".join("".join(word["word"].split()) for word in words)
            if not expected or actual != expected:
                raise ValueError("Word estimates differ from the exact caption text")
            start = captions._number(phrase["visual_start"])
            end = captions._number(phrase["visual_end"])
            offset = start - captions._number(phrase["start"])
            if not 0 <= start < end <= duration:
                raise ValueError("Word captions require an in-range phrase")
            ends, word_times, count, prior_end = [], [], 0, start
            for word in words:
                word_text = "".join(word["word"].split())
                if not word_text:
                    raise ValueError("A word estimate cannot contain only whitespace")
                count += len(word_text)
                ends.append(positions[count - 1] + 1)
                a, b = offset + captions._number(word["start"]), offset + captions._number(word["end"])
                epsilon = Decimal("0.00000001")
                if a < start - epsilon or b > end + epsilon or a > b or a < prior_end:
                    raise ValueError("Unordered or out-of-phrase word estimates")
                a, b = max(start, a), min(end, b)
                word_times.append((a, b))
                prior_end = b
            ends[-1] = len(text)
            cursor, first_word, part = 0, 0, 1
            while cursor < len(text):
                suggestion = captions.split_text(text[cursor:], style["max_width"])[0]
                limit = cursor + len(suggestion)
                choices = [index for index in range(first_word, len(words)) if ends[index] <= limit]
                if not choices:
                    raise ValueError("One aligned word cannot fit the selected caption width")
                last_word = choices[-1]
                stop = ends[last_word]
                first = int((word_times[first_word][0] * 100).to_integral_value(rounding=ROUND_CEILING))
                last = int((word_times[last_word][1] * 100).to_integral_value(rounding=ROUND_FLOOR))
                if first < previous or last <= first:
                    raise ValueError("Word caption group has no positive nonoverlapping centisecond span")
                uncertain = [index for index in range(first_word, last_word + 1)
                             if word_times[index][0] == word_times[index][1]]
                events.append({"utterance_id": f"{unit['id']}.{phrase['id']}", "part": part,
                    "text": text[cursor:stop], "start_cs": first, "end_cs": last,
                    "utterance_start": phrase["visual_start"], "utterance_end": phrase["visual_end"],
                    "meaning_unit_id": unit["id"], "reference_id": phrase["id"],
                    "timing": "model_estimated_word_group", "first_word_index": first_word,
                    "last_word_index": last_word, "instantaneous_word_indices": uncertain})
                previous, cursor, first_word, part = last, stop, last_word + 1, part + 1
    if not events:
        raise ValueError("Word captions are empty")
    return {"schema_version": 1, "duration": alignment["duration"], "events": events,
        "timing_scope": "Model-estimated word-group boundaries; instantaneous word points remain uncertain, not listening certification",
        "audio_continuity": "Complete original meaning-unit WAVs; caption groups never restart or edit speech"}
