import pytest

import greth.agent.artifact as artifact


def test_read_artifact_returns_requested_slice(monkeypatch, tmp_path):
    (tmp_path / "scout-ref.txt").write_text("first second third", encoding="utf-8")
    monkeypatch.setattr(artifact, "ARTIFACT_DIR", tmp_path)

    assert artifact.read_artifact("scout-ref", start=6, length=6) == "second"


def test_read_artifact_reports_missing_references(monkeypatch, tmp_path):
    monkeypatch.setattr(artifact, "ARTIFACT_DIR", tmp_path)

    with pytest.raises(FileNotFoundError, match="artifact 'missing' was not found"):
        artifact.read_artifact("missing")
