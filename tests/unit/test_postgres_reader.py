"""Unit tests for allowlisted Supercalc Postgres reader."""

from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from winston.sources.postgres import (
    ALLOWED_RELATIONS,
    PostgresConfig,
    PostgresLiveReader,
    resolve_password,
)


def _cfg(**kwargs):
    base = dict(
        host="/cloudsql/adept-snow-481601-c6:us-central1:polymarket-gvf-db-small",
        database="polymarket_gvf",
        sslmode="disable",
        auth_method="password",
        credential_provider="env:WINSTON_SUPERCALC_PG_PASSWORD",
        db_user="winston_readonly",
        source_mappings={
            "signals": {
                "relation": "signals",
                "columns": {"id": "id", "market_id": "market_id"},
            },
            "risk_rollups": {
                "relation": "risk_rollups",
                "columns": {"id": "id", "theme": "theme"},
            },
        },
    )
    base.update(kwargs)
    return PostgresConfig(**base)


class TestResolvePassword:
    def test_env_provider(self, monkeypatch):
        monkeypatch.setenv("MY_PG_PASS", "secret-value")
        assert resolve_password("env:MY_PG_PASS") == "secret-value"

    def test_secret_provider_via_winston_env(self, monkeypatch):
        monkeypatch.setenv("WINSTON_SUPERCALC_PG_PASSWORD", "from-run")
        assert (
            resolve_password("secret:winston-staging-supercalc-pg-password")
            == "from-run"
        )


class TestAllowlist:
    def test_allowed_relations_match_supercalc(self):
        assert "signals" in ALLOWED_RELATIONS
        assert "risk_rollups" in ALLOWED_RELATIONS
        assert "executions" not in ALLOWED_RELATIONS

    def test_rejects_non_allowlisted_relation(self, monkeypatch):
        monkeypatch.setenv("WINSTON_SUPERCALC_PG_PASSWORD", "x")
        reader = PostgresLiveReader(
            _cfg(
                source_mappings={
                    "bad": {"relation": "api_keys", "columns": {"id": "id"}}
                }
            )
        )

        @contextmanager
        def fake_connect():
            conn = MagicMock()
            cur = MagicMock()
            conn.cursor.return_value.__enter__.return_value = cur
            yield conn

        reader._connect = fake_connect  # type: ignore[method-assign]
        result = reader.probe_mapped_relations()
        assert result.receipt.status.value == "failed"
        assert "allowlisted" in (result.receipt.warnings or [""])[0]


class TestProbeMapped:
    def test_probe_success(self, monkeypatch):
        monkeypatch.setenv("WINSTON_SUPERCALC_PG_PASSWORD", "x")
        reader = PostgresLiveReader(_cfg())

        class FakeCursor:
            def __init__(self):
                self._q = None
                c1, c2 = MagicMock(), MagicMock()
                c1.name, c2.name = "id", "market_id"
                self.description = [c1, c2]

            def execute(self, sql, params=None):
                self._q = sql

            def fetchone(self):
                if self._q and "COUNT" in self._q:
                    return (7,)
                return (1,)

            def fetchall(self):
                return [(1, "m1")]

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        class FakeConn:
            def cursor(self):
                return FakeCursor()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        @contextmanager
        def fake_connect():
            yield FakeConn()

        reader._connect = fake_connect  # type: ignore[method-assign]
        result = reader.probe_mapped_relations(mapping_ids=["signals"])
        assert result.receipt.status.value == "complete"
        assert result.data["probes"]["signals"]["count"] == 7
        assert result.data["probes"]["signals"]["sample_rows"] == 1
