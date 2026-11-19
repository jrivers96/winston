"""Winston evaluation - synthetic cases, recorded evidence, token-efficiency eval."""

from winston.evaluation.calculator import SyntheticCalculator
from winston.evaluation.cases import (
    BaselinePromptSpec,
    DatadogCaseFixture,
    GroundTruth,
    InvestigationCase,
    QualityRubric,
    list_case_ids,
    load_all_cases,
    load_case,
)
from winston.evaluation.fixtures import (
    GOLDEN_VALUES,
    create_demo_graph,
    load_fixture,
    verify_golden_values,
)
from winston.evaluation.score import QualityScore, score_case, score_findings
from winston.evaluation.tokens import (
    CharApproxCounter,
    PromptPackage,
    TiktokenCounter,
    TokenCounter,
    get_default_counter,
    render_context_prompt,
)

__all__ = [
    "SyntheticCalculator",
    "load_fixture",
    "create_demo_graph",
    "verify_golden_values",
    "GOLDEN_VALUES",
    # Phase 0 cases
    "InvestigationCase",
    "GroundTruth",
    "QualityRubric",
    "BaselinePromptSpec",
    "DatadogCaseFixture",
    "list_case_ids",
    "load_case",
    "load_all_cases",
    "QualityScore",
    "score_findings",
    "score_case",
    # Phase 1 tokens
    "TokenCounter",
    "CharApproxCounter",
    "TiktokenCounter",
    "PromptPackage",
    "get_default_counter",
    "render_context_prompt",
]
