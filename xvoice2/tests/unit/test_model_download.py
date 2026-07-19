"""
Unit tests for model_download (Parakeet first-run download helpers).
"""

from unittest.mock import patch

import pytest

from xvoice2 import model_download

MODEL = "nemo-parakeet-tdt-0.6b-v2"
REPO = "istupakov/parakeet-tdt-0.6b-v2-onnx"


class TestModelDownload:
    def test_repo_id_from_resolver(self):
        assert model_download.model_repo_id(MODEL) == REPO

    def test_repo_id_unknown(self):
        assert model_download.model_repo_id("does-not-exist") is None

    def test_is_model_cached_true(self, tmp_path):
        snap = tmp_path / ("models--" + REPO.replace("/", "--")) / "snapshots" / "abc"
        snap.mkdir(parents=True)
        (snap / "model.onnx").write_bytes(b"x")
        with patch("huggingface_hub.constants.HF_HUB_CACHE", str(tmp_path)):
            assert model_download.is_model_cached(MODEL) is True

    def test_is_model_cached_false_when_no_onnx(self, tmp_path):
        snap = tmp_path / ("models--" + REPO.replace("/", "--")) / "snapshots" / "abc"
        snap.mkdir(parents=True)
        (snap / "config.json").write_bytes(b"{}")
        with patch("huggingface_hub.constants.HF_HUB_CACHE", str(tmp_path)):
            assert model_download.is_model_cached(MODEL) is False

    def test_is_model_cached_false_when_absent(self, tmp_path):
        with patch("huggingface_hub.constants.HF_HUB_CACHE", str(tmp_path)):
            assert model_download.is_model_cached(MODEL) is False

    def test_cache_bytes_on_disk(self, tmp_path):
        d = tmp_path / ("models--" + REPO.replace("/", "--"))
        d.mkdir(parents=True)
        (d / "blob1").write_bytes(b"a" * 100)
        (d / "blob2").write_bytes(b"b" * 50)
        with patch("huggingface_hub.constants.HF_HUB_CACHE", str(tmp_path)):
            assert model_download.cache_bytes_on_disk(MODEL) == 150

    def test_download_model_calls_snapshot(self):
        with patch("huggingface_hub.snapshot_download") as snap:
            model_download.download_model(MODEL)
            snap.assert_called_once_with(REPO)

    def test_download_model_unknown_raises(self):
        with pytest.raises(ValueError):
            model_download.download_model("no-such-model")

    def test_total_bytes_offline_returns_zero(self):
        with patch("huggingface_hub.HfApi", side_effect=RuntimeError("offline")):
            assert model_download.model_total_bytes(MODEL) == 0
