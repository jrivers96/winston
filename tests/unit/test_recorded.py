"""Tests for recorded fixture bundles."""

import json
from pathlib import Path

import pytest

from winston.evaluation.cases import run_case
from winston.evaluation.recorded import (
    RecordingError,
    load_bundle,
    record_supercalc_late_correction,
    redact_value,
    replay_bundle,
    validate_no_secrets,
)


@pytest.mark.supercalc
class TestRedaction:
    def test_redacts_secret_keys(self):
        payload = {
            "api_key": "secret-value",
            "host": "example.com",
            "nested": {"password": "x", "ok": 1},
        }
        redacted = redact_value(payload)
        assert redacted["api_key"] == "[REDACTED]"
        assert redacted["nested"]["password"] == "[REDACTED]"
        assert redacted["host"] == "example.com"
        assert redacted["nested"]["ok"] == 1

    def test_omits_customer_pnl(self):
        payload = {"pnl": 123.45, "index_id": "STRESS"}
        redacted = redact_value(payload)
        assert redacted["pnl"] == "[OMITTED_CUSTOMER_DATA]"
        assert redacted["index_id"] == "STRESS"

    def test_validate_rejects_unredacted_secrets(self):
        with pytest.raises(RecordingError):
            validate_no_secrets({"token": "still-present"})


@pytest.mark.supercalc
class TestRecordedBundle:
    def test_sample_bundle_loads(self):
        bundle = load_bundle(
            Path("fixtures/recorded/samples/supercalc-stress-s2-correction")
        )
        assert bundle["manifest"]["schema_version"] == "1.0.0"
        assert bundle["manifest"]["policy"]["credentials_excluded"] is True
        assert "STRESS" in {
            n.index_id for n in bundle["graph"].nodes.values()
        }

    def test_replay_sample_bundle(self):
        report = replay_bundle(
            Path("fixtures/recorded/samples/supercalc-stress-s2-correction"),
            offline=True,
        )
        assert report["passed"] is True
        assert "STRESS" in report["impact"]["affected_indices"]
        assert "HEDGE_ARM" in report["impact"]["affected_indices"]
        assert report["impact"]["unrelated_excluded"] is True

    def test_run_case_by_sample_name(self):
        report = run_case("supercalc-stress-s2-correction", offline=True)
        assert report["passed"] is True
        assert report["source"] == "recorded_bundle"

    def test_run_case_with_bundle_option(self):
        report = run_case(
            "recorded",
            offline=True,
            bundle="fixtures/recorded/samples/supercalc-stress-s2-correction",
        )
        assert report["passed"] is True

    def test_live_replay_rejected(self):
        with pytest.raises(ValueError, match="offline-only"):
            replay_bundle(
                Path("fixtures/recorded/samples/supercalc-stress-s2-correction"),
                offline=False,
            )

    def test_record_roundtrip(self, temp_dir: Path):
        out = temp_dir / "bundle"
        written = record_supercalc_late_correction(out)
        assert (written / "manifest.json").exists()
        manifest = json.loads((written / "manifest.json").read_text())
        assert "password" not in json.dumps(manifest).lower()
        report = replay_bundle(written, offline=True)
        assert report["passed"] is True
