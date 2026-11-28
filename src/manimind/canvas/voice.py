"""Voice track for a Canvas film: whole takes placed on the film clock, one constant gain.

HyperFrames renders the picture silently; the narration is mixed here under the project's audio
rule: every unit WAV is placed whole and unedited (no trimming, speed change, compression or
normalising filter), the sum gets exactly one constant gain chosen to approach ``target_lufs``
without letting the true peak exceed ``ceiling_dbtp``, and the video stream is copied, not re-encoded.

State: voice.wav and the mux are derived output of one render attempt (writer: render.py; readers:
reviewers, publishers); any WAV, placement or gain change invalidates them.
"""

from __future__ import annotations

from pathlib import Path
import re
import subprocess


def _ffmpeg(env) -> str:
    return env.get("FFMPEG_PATH", "ffmpeg")


def loudness(path: Path, env) -> dict:
    """Integrated loudness (LUFS) and true peak (dBTP) via FFmpeg's ebur128 filter."""
    err = subprocess.run([_ffmpeg(env), "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true",
                          "-f", "null", "-"], capture_output=True, text=True, env=env).stderr
    integrated = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", err)[-1])
    peak = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", err)[-1])
    return {"integrated_lufs": integrated, "true_peak_dbtp": peak}


def mix(tracks, duration: float, out: Path, env, target_lufs: float = -16.0, ceiling_dbtp: float = -1.0) -> dict:
    """Place ``tracks`` [{"source": Path, "start": s, "volume": v}] and write ``out`` (48 kHz mono PCM16)."""
    if not tracks:
        raise ValueError("no voice tracks to mix")
    inputs, graph = [], []
    for k, t in enumerate(tracks):
        inputs += ["-i", str(t["source"])]
        ms = int(round(t["start"] * 1000))
        graph.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=mono,volume={t['volume']:.6f},"
                     f"adelay={ms}:all=1,apad=whole_dur={duration}[a{k}]")
    labels = "".join(f"[a{k}]" for k in range(len(tracks)))
    graph.append(f"{labels}amix=inputs={len(tracks)}:normalize=0:duration=longest,atrim=0:{duration}[m]")
    unity = out.with_name(out.stem + "-unity.wav")
    subprocess.run([_ffmpeg(env), "-v", "error", "-y", *inputs, "-filter_complex", ";".join(graph), "-map", "[m]",
                    "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le", str(unity)], check=True, env=env)
    before = loudness(unity, env)
    gain = round(min(target_lufs - before["integrated_lufs"], ceiling_dbtp - before["true_peak_dbtp"]), 2)
    subprocess.run([_ffmpeg(env), "-v", "error", "-y", "-i", str(unity), "-af", f"volume={gain}dB",
                    "-c:a", "pcm_s16le", str(out)], check=True, env=env)
    return {"before": before, "gain_db": gain, "after": loudness(out, env), "target_lufs": target_lufs,
            "ceiling_dbtp": ceiling_dbtp, "processing": "whole takes, adelay placement, one constant gain"}


def mux(picture: Path, voice: Path, out: Path, env):
    """Copy the video stream and add the voice as AAC; the picture is never re-encoded."""
    subprocess.run([_ffmpeg(env), "-v", "error", "-y", "-i", str(picture), "-i", str(voice), "-map", "0:v", "-map",
                    "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "1", "-shortest",
                    str(out)], check=True, env=env)
