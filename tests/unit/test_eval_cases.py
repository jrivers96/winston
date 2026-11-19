"""Phase 0–1 unit tests: investigation cases, scoring, token counters."""

from __future__ import annotations

import pytest

from winston.context import ContextBuilder
from winston.evaluation import (
    CharApproxCounter,
    TiktokenCounter,
    get_default_counter,
    list_case_ids,
    load_all_cases,
    load_case,
    score_case,
    score_findings,
)
from winston.evaluation.cases import InvestigationCase


EXPECTED_CASES = {
    "carry_correction",
    "impact_closure",
    "unrelated_exclusion",
    "ops_spike_window",
    "repeat_investigation",
}


@pytest.mark.phase7
class TestInvestigationCases:
    def test_list_case_ids(self):
        ids = list_case_ids()
        assert EXPECTED_CASES.issubset(set(ids))

    def test_load_all_cases(self):
        cases = load_all_cases()
        assert len(cases) >= 5
        assert all(isinstance(c, InvestigationCase) for c in cases)

    def test_carry_correction_ground_truth(self):
        case = load_case("carry_correction")
        assert case.case_id == "carry_correction"
        assert case.ground_truth.root_cause == "d2_q_correction"
        assert case.ground_truth.affected_dates == ["D3", "D4", "D5"]
        assert "DEMO_UNRELATED" in case.ground_truth.excluded_indices
        assert case.token_budget_default == 8000
        assert case.baseline.arms == ["bit", "vscode"]

    def test_baseline_bundle_includes_noise_and_question(self):
        case = load_case("carry_correction")
        bundle = case.baseline_bundle_text()
        assert "DEMO D2 input q=5" in bundle
        assert "DEMO_UNRELATED" in bundle
        assert case.question.strip()[:20] in bundle
        assert "Raw logs" in bundle

    def test_ops_spike_is_original_scenario(self):
        case = load_case("ops_spike_window")
        assert case.scenario == "original"
        assert case.ground_truth.root_cause == "ops_noise_only"
        assert case.ground_truth.affected_dates == []


@pytest.mark.phase7
class TestQualityScore:
    def test_perfect_score(self):
        case = load_case("carry_correction")
        score = score_case(
            case,
            {
                "root_cause": "d2_q_correction",
                "affected_dates": ["D3", "D4", "D5"],
                "affected_indices": ["DEMO", "DEMO_DEPENDENT"],
            },
        )
        assert score.score == 1.0
        assert score.root_cause_match
        assert score.exclusions_ok

    def test_exclusion_penalty(self):
        case = load_case("unrelated_exclusion")
        score = score_case(
            case,
            {
                "root_cause": "d2_q_correction",
                "affected_dates": ["D3", "D4", "D5"],
                "affected_indices": ["DEMO", "DEMO_DEPENDENT", "DEMO_UNRELATED"],
            },
        )
        assert score.exclusions_ok is False
        assert score.score < 1.0

    def test_partial_dates(self):
        case = load_case("carry_correction")
        score = score_findings(
            case.ground_truth,
            {
                "root_cause": "d2_q_correction",
                "affected_dates": ["D3"],
                "affected_indices": ["DEMO", "DEMO_DEPENDENT"],
            },
            case.rubric,
        )
        assert score.dates_recall == pytest.approx(1 / 3)
        assert 0.0 < score.score < 1.0


@pytest.mark.phase7
class TestTokenCounters:
    def test_char_approx(self):
        counter = CharApproxCounter()
        assert counter.name == "char_approx_div4"
        assert counter.count("") == 0
        assert counter.count("abcd") == 1
        assert counter.count("a" * 40) == 10

    def test_tiktoken_if_available(self):
        tiktoken = pytest.importorskip("tiktoken")
        counter = TiktokenCounter()
        assert counter.name.startswith("tiktoken:")
        assert counter.count("hello world") > 0
        # Stable for empty
        assert counter.count("") == 0
        _ = tiktoken  # silence unused if linters complain

    def test_default_counter_prefers_tiktoken(self):
        pytest.importorskip("tiktoken")
        counter = get_default_counter()
        assert counter.name.startswith("tiktoken:")


@pytest.mark.phase7
class TestContextBuilderTokens:
    def test_budget_excludes_low_relevance(self):
        builder = ContextBuilder(
            token_budget=80,
            max_items=10,
            token_counter=CharApproxCounter(),
        )
        builder.add_execution(
            "big",
            "DEMO",
            "D3",
            "succeeded",
            state_content={"blob": "x" * 400},
            relevance_score=0.1,
        )
        builder.add_execution(
            "small",
            "DEMO",
            "D2",
            "succeeded",
            state_content={"level": 102, "carry": 5},
            relevance_score=0.9,
        )
        manifest = builder.build(index_id="DEMO", business_date="D3")
        assert manifest.tokenizer_name == "char_approx_div4"
        assert any(i.item_id == "exec:small" for i in manifest.items)
        assert manifest.tokens_used <= manifest.token_budget
        assert manifest.items_excluded >= 0

    def test_export_prompt_recounts(self):
        builder = ContextBuilder(
            token_budget=10_000,
            token_counter=CharApproxCounter(),
        )
        builder.add_issue(
            "iss1",
            "Carry drift",
            "D2 q correction",
            "open",
            relevance_score=1.0,
        )
        builder.add_evidence(
            "ev1",
            "datadog",
            "D2 metrics",
            content={"q": 5, "carry": 5},
            relevance_score=0.8,
        )
        manifest = builder.build(investigation_id="inv1")
        package = builder.export_prompt(manifest, case_id="carry_correction")

        assert package.case_id == "carry_correction"
        assert package.tokenizer_name == "char_approx_div4"
        assert package.item_count == 2
        assert "Carry drift" in package.prompt_text
        assert package.token_count == CharApproxCounter().count(package.prompt_text)
        assert package.to_dict()["token_count"] == package.token_count

    def test_max_items_cap(self):
        builder = ContextBuilder(
            token_budget=100_000,
            max_items=2,
            token_counter=CharApproxCounter(),
        )
        for i in range(5):
            builder.add_evidence(
                f"e{i}",
                "log",
                f"line {i}",
                content={"i": i},
                relevance_score=float(i),
            )
        manifest = builder.build()
        assert manifest.items_included == 2
        assert "Max items reached" in manifest.exclusion_reasons
