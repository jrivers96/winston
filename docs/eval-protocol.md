# Token-Efficiency Eval Protocol (Phase 0–1)

Shared incident contracts used to compare Winston context assembly against
prompting Datadog / log dumps via BIT or a VS Code agent.

## Arms

| Arm | How context reaches the model |
| --- | ----------------------------- |
| Winston | `ContextBuilder` + token budget → `PromptPackage` |
| BIT | Paste `InvestigationCase.baseline_bundle_text()` into BIT |
| VS Code | Paste the same frozen bundle into a VS Code agent chat |

All arms share the same `InvestigationCase` YAML under
`src/winston/evaluation/cases/`.

## Case schema

Each YAML file defines:

- `question` / `baseline` — identical question text for every arm
- `ground_truth` — root cause, affected dates/indices, exclusions
- `rubric` — weights for deterministic `score_findings`
- `datadog.raw_log_lines` — frozen baseline paste (noise + signal)
- `token_budget_default` — Winston assemble budget for the case

Load with `winston.evaluation.load_case("carry_correction")`.

## Token accounting (Phase 1)

- Prefer `TiktokenCounter` (`tiktoken:cl100k_base`) when `winston[eval]` is installed
- Fallback: `CharApproxCounter` (`len // 4`)
- `ContextBuilder.export_prompt(manifest)` returns the canonical `prompt_text`
  and a recountable `token_count`
- Baseline runs should record provider `input_tokens`, or recount the pasted
  bundle with the **same** `TokenCounter`

## Quality rule

A Winston token win only counts when `quality_score >= baseline` for that case.

```python
from winston.evaluation import load_case, score_case

case = load_case("carry_correction")
score = score_case(case, {
    "root_cause": "d2_q_correction",
    "affected_dates": ["D3", "D4", "D5"],
    "affected_indices": ["DEMO", "DEMO_DEPENDENT"],
})
assert score.score == 1.0
```

## Out of scope here

Automated BIT / VS Code driving, live Datadog pulls, and `winston eval compare`
CLI land in later Phase 7 steps.
