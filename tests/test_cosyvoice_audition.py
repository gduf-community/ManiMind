import hashlib
import io
import json
import wave

import pytest

from manimind.postproduce import cosyvoice_audition as audition


def fixture_wav():
    stream = io.BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(b"\0\0" * 2400)
    return stream.getvalue()


def job():
    return {"input": "Fixture, not a generated model sample", "instructions": "Original style guidance", "seed": 1729}


@pytest.mark.parametrize("change", [{"input": " "}, {"input": "x" * 601}, {"instructions": ""},
    {"instructions": "<|endofprompt|>"}, {"seed": True}, {"seed": -1}, {"reference_audio": "private.wav"}])
def test_invalid_or_unintended_job_fields_are_rejected(change):
    with pytest.raises(ValueError):
        audition.validate_request({**job(), **change})


def test_guidance_and_text_are_preserved_without_a_teacher_role():
    value = audition.validate_request(job())
    assert value == job()
    assert audition.instruction_text(value) == "You are a helpful assistant. Original style guidance<|endofprompt|>"


def test_audio_receipt_has_exact_request_and_no_listening_approval(tmp_path):
    value = job()
    data = fixture_wav()
    record = audition.save_result(tmp_path, value, {"fixture": "not actual model inference"}, data, .2)
    assert record["request"] == value and record["duration_seconds"] == .1
    assert record["wav_sha256"] == hashlib.sha256(data).hexdigest()
    assert record["acceptance"] == "generated_not_listening_approved"
    assert "not commercial" in record["limitations"][0]
    assert json.loads((tmp_path / "receipt.json").read_bytes()) == record
    with pytest.raises(ValueError, match="overwritten"):
        audition.save_result(tmp_path, value, {}, data, .2)


def test_corrupt_wave_never_becomes_a_successful_candidate(tmp_path):
    with pytest.raises((ValueError, wave.Error, EOFError)):
        audition.save_result(tmp_path, job(), {}, fixture_wav()[:-20], .2)
    assert not list(tmp_path.iterdir())


def test_pinned_model_and_reference_require_all_files_and_no_speaker_database(tmp_path):
    model = tmp_path / "model"
    model.mkdir()
    files = []
    for name in sorted(audition.MODEL_FILES):
        target = model / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"fixture, not model weights")
        files.append({"file": name, "sha256": audition.file_sha256(target)})
    reference = tmp_path / "reference.wav"
    reference.write_bytes(fixture_wav())
    setup = {"model_id": audition.MODEL_ID, "model_path": str(model), "files": files,
             "reference": str(reference), "reference_sha256": audition.file_sha256(reference),
             "reference_source": "https://raw.githubusercontent.com/FunAudioLLM/CosyVoice/fixture/asset/zero_shot_prompt.wav"}
    assert audition.validate_setup(setup, model) == reference
    with pytest.raises(ValueError, match="incomplete"):
        audition.validate_setup({**setup, "files": files[:-1]}, model)
    (model / "spk2info.pt").write_bytes(b"unintended speaker store")
    with pytest.raises(ValueError, match="speaker"):
        audition.validate_setup(setup, model)
    (model / "spk2info.pt").unlink()
    reference.write_bytes(b"changed")
    with pytest.raises(ValueError, match="reference"):
        audition.validate_setup(setup, model)
