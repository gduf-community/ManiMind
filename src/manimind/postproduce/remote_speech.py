"""Fetch reproducible WAV speech through an already established private tunnel."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import urllib.parse
import urllib.request
import wave


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def audio_request(base_url, token_file: Path, payload: dict, target: Path, *, timeout=600):
    url = urllib.parse.urlsplit(base_url)
    if url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"} or url.username or url.password or url.query or url.fragment:
        raise ValueError("Use a loopback HTTP endpoint protected by the SSH tunnel")
    if target.exists() or target.with_suffix(".receipt.json").exists():
        raise ValueError("Existing audio is not overwritten")
    token = token_file.read_text(encoding="utf-8").strip()
    if len(token) < 32 or any(c.isspace() for c in token):
        raise ValueError("Private speech token is missing or invalid")
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(base_url.rstrip("/") + "/v1/audio/speech", body,
        {"Content-Type": "application/json", "Authorization": "Bearer " + token})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=timeout) as response:
        if response.headers.get_content_type() != "audio/wav":
            raise ValueError("Speech endpoint did not return WAV")
        data = response.read(32 * 1024 * 1024 + 1)
        if len(data) > 32 * 1024 * 1024:
            raise ValueError("Unexpected audio response size")
        sha = hashlib.sha256(data).hexdigest()
        if response.headers.get("X-Audio-SHA256") != sha:
            raise ValueError("Speech response hash mismatch")
        headers = {k: response.headers.get(k) for k in ("X-Request-ID", "X-Synthesis-Seconds", "X-Cache-Hit")}
    with wave.open(io.BytesIO(data)) as audio:
        if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or audio.getnframes() <= 0:
            raise ValueError("Expected nonempty mono PCM16 audio")
        measured = {"sample_rate": audio.getframerate(), "duration_seconds": audio.getnframes() / audio.getframerate()}
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as stream:
        stream.write(data)
    receipt = {"schema_version": 1, "request": payload, "request_sha256": hashlib.sha256(body).hexdigest(),
               "wav_sha256": sha, **measured, "server": headers,
               "acceptance": "generated_not_listening_approved", "writer": "private speech client",
               "consumers": ["alignment", "auditor", "user"], "lifecycle": "This request and exact received WAV",
               "invalidation": "Text, parameters, model receipt or WAV changes"}
    with target.with_suffix(".receipt.json").open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:17666")
    parser.add_argument("--token-file", required=True, type=Path)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    receipt = audio_request(args.base_url, args.token_file, json.loads(args.request.read_text(encoding="utf-8")), args.output)
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
