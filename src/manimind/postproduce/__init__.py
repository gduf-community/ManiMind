"""Post-production helpers for assembling reviewed segment assets."""

from .assembler import (
    VideoAssemblyResult,
    assemble_manim_video,
    collect_segment_video_paths,
)
from .subtitles import (
    SubtitleBurnResult,
    SubtitleBuildResult,
    SubtitleCue,
    SubtitleMuxResult,
    burn_subtitle_track,
    build_subtitle_file,
    mux_subtitle_track,
)
from .voiceover import (
    VoiceoverBuildResult,
    VoiceoverMuxResult,
    build_voiceover_audio,
    mux_voiceover_track,
)

__all__ = [
    "SubtitleBurnResult",
    "SubtitleBuildResult",
    "SubtitleCue",
    "SubtitleMuxResult",
    "VideoAssemblyResult",
    "VoiceoverBuildResult",
    "VoiceoverMuxResult",
    "assemble_manim_video",
    "burn_subtitle_track",
    "build_subtitle_file",
    "build_voiceover_audio",
    "collect_segment_video_paths",
    "mux_subtitle_track",
    "mux_voiceover_track",
]
