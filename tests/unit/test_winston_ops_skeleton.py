"""Guards for winston-ops GCP skeleton (no cloud calls)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPS = ROOT / "ops" / "winston-ops"


def test_terraform_skeleton_files_exist():
    tf = OPS / "terraform"
    for name in (
        "main.tf",
        "variables.tf",
        "apis.tf",
        "network.tf",
        "sql.tf",
        "secrets.tf",
        "storage.tf",
        "iam.tf",
        "scheduler.tf",
        "outputs.tf",
        "terraform.tfvars.example",
    ):
        assert (tf / name).is_file(), f"missing {name}"


def test_enable_resources_defaults_false_in_example():
    text = (OPS / "terraform" / "terraform.tfvars.example").read_text()
    assert "enable_resources = false" in text


def test_scripts_exist_and_are_executable_bits_optional():
    for name in (
        "nightly_replay.sh",
        "provision_check.sh",
        "staging_maintain.sh",
        "bootstrap_live_profile.sh",
    ):
        path = OPS / "scripts" / name
        assert path.is_file(), f"missing {name}"
        assert path.read_text().startswith("#!/usr/bin/env bash")


def test_cloudrun_dockerfile_uses_offline_entrypoint():
    dockerfile = (OPS / "cloudrun" / "Dockerfile").read_text()
    assert "WINSTON_OFFLINE_MODE=true" in dockerfile
    assert "nightly_replay.sh" in dockerfile
