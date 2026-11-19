# Winston Implementation Map

## Module Ownership

| Module | Responsibility | Status |
| ------ | -------------- | ------ |
| `winston.domain` | Identities, calendars, revisions, evidence envelopes, issue lifecycles | Phase 1 |
| `winston.storage` | Alembic migrations, transactions, artifact store (temp→fsync→rename) | Phase 1 |
| `winston.sources` | Databricks, Datadog, recording, offline replay adapters | Phase 3-4 |
| `winston.repositories` | Registry, component/path maps, pinned reads, coverage budgets | Phase 1-2 |
| `winston.lineage` | Dependency graph, impact closure, replay planning | Phase 2 |
| `winston.checks` | Deterministic business/chain/ops checks | Phase 2 |
| `winston.context` | Validity, assembly, manifests, explain | Phase 5 |
| `winston.investigations` | Evidence-linked hypotheses; optional model interface | Phase 5 |
| `winston.maintenance` | Cursors, due obligations, invalidation, recovery | Phase 2 |
| `winston.cli` | Human + JSON interfaces | Phase 1+ |
| `winston.evaluation` | Synthetic cases, recorded evidence, fault injection; Phase 0–1 case contracts + token counters | Phase 2 / 7 |

## Authority Split (non-negotiable)

- **Databricks**: Business inputs/outputs/run records (read-only)
- **Datadog**: Operational observations in query windows
- **Local PostgreSQL**: Issues, obligations, hypotheses, knowledge validity, investigation state, receipts, manifests
- **Local files**: Immutable evidence, fixtures, reports, Git object cache
- **Local replay**: Scenario results only; never official publication

## Two Graphs

1. **Software graph**: Components, revisions, packages, deployments (cycles allowed)
2. **Calculation DAG**: Consumed input/state revisions → executions → outputs (acyclic for concrete lineage)

Joined only via execution evidence.

## Phase 7 (token-efficiency eval) — in progress

| Slice | Status |
| ----- | ------ |
| Phase 0 case contracts, fixtures, rubric | Done |
| Phase 1 TokenCounter + prompt export | Done |
| Phase 2 Winston assemble runner | Planned |
| Phase 3 BIT / VS Code baseline ingest | Planned |
| Phase 4 compare report + CI gate | Planned |

See `docs/eval-protocol.md`.

## Deferred Items (not in v1)

- Dashboard / web UI
- HTTP / MCP hosting
- Separate graph database
- Vector database / embeddings
- Multi-worker distributed processing
- Broad connector framework beyond Databricks/Datadog

## Fixture-Only vs Live-Template

| Capability | Fixture-Only | Live-Template |
| ---------- | ------------ | ------------- |
| Synthetic DEMO index calculation | ✓ | - |
| Fixture Git repositories | ✓ | - |
| Databricks query templates | - | ✓ |
| Datadog metric mappings | - | ✓ |
| Calendar configurations | ✓ (synthetic) | ✓ (template) |
| Jobs metadata reader | - | ✓ (optional) |

## CLI Commands

```
winston doctor --profile <name>
winston sync --index <id> --from <date> --to <date> --profile <name>
winston diagnose --index <id> --date <date> --scenario <scenario>
winston chain show --index <id> --date <date>
winston impact --change <id> --through <date>
winston replay --case <name> --offline
winston repair-plan --issue <id> --through <date>
winston issues list
winston issues show <id>
winston repos list
winston repos doctor
winston repos sync --repo <id>
winston repos inspect --repo <id> --revision <commit>
winston source-manifest show --run <id>
winston context search --investigation <id> --query <text>
winston context explain <id>
winston maintain --once
winston export --output <path>
```
