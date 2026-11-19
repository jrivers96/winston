# Winston

Winston is an operations agent that manages system context over time.

It keeps a durable record of how a system is set up, what has changed, and what still matters, so later decisions can be made from that history rather than from a fresh snapshot.

## Status

**All Phases Complete** - Winston is a working operations agent:

- **Phase 0-1**: Foundation with PostgreSQL, Alembic, artifact store, domain models
- **Phase 2**: Chain analysis, lineage graph, impact analysis, replay planning
- **Phase 3-4**: Databricks and Datadog adapters (fixture-first, live stubs)
- **Phase 5**: Context assembly with token budgets and provenance
- **Phase 6**: Documentation and release polish

### Verified Golden Values

The synthetic calculator correctly produces:
- Original D1-D5: 101, 102, 103, 104, 105
- After D2 q=5 correction: 101, 102, 108, 109, 110
- Dependent index (2× D3): 206 → 216

Supercalc-shaped offline case (`supercalc-late-correction`):
- `STRESS` S1–S5 mirrors the same arithmetic
- `HEDGE_ARM` tracks 2× STRESS S3 (206 → 216)
- `TRUST_UNRELATED` stays out of STRESS impact

```bash
winston replay --case supercalc-late-correction --offline
winston replay --bundle supercalc-stress-s2-correction --offline
winston maintain --once --profile supercalc_synthetic --no-persist
winston doctor --profile supercalc_live
winston live-smoke --profile supercalc_live   # reports missing live config unless opted in
```

See [docs/continual-testing.md](docs/continual-testing.md) for CI, recorded fixtures, nightly, live-smoke, and trust/maintain layers.

GCP staging skeleton (no apply by default): [ops/winston-ops/README.md](ops/winston-ops/README.md) — run `./ops/winston-ops/scripts/provision_check.sh` before any `terraform apply`.

## Quick Start

### VS Code Dev Container (recommended)

One-click local setup with Winston + PostgreSQL:

1. Install the [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension
2. Open this repo in VS Code / Cursor
3. Run **Dev Containers: Reopen in Container**

That builds the Winston image, starts Postgres, installs the package, and runs `winston init`.

Then in the container terminal:

```bash
winston doctor --profile synthetic
```

### Local setup (without Dev Container)

#### Prerequisites

- Python 3.8+
- PostgreSQL 13+
- Docker & Docker Compose (optional, for local PostgreSQL)

#### Setup

1. **Start PostgreSQL** (using Docker Compose):

```bash
docker compose up -d postgres
```

2. **Install Winston**:

```bash
pip install -e ".[dev]"
```

3. **Initialize the database**:

```bash
winston init
```

4. **Check health**:

```bash
winston doctor --profile synthetic
```

## CLI Commands

```bash
# System health
winston doctor --profile synthetic

# Initialize database and directories
winston init

# Issue management
winston issues list
winston issues show <issue-id>

# Repository management  
winston repos list
winston repos doctor

# Export/import data
winston export --output bundle.tar.gz
winston import bundle.tar.gz
```

## Architecture

Winston maintains two separate graphs joined through execution evidence:

- **Software Graph**: Components, revisions, packages, deployments (cycles allowed)
- **Calculation DAG**: Consumed inputs → executions → outputs (acyclic)

### Authority Split

| System | Owns |
| ------ | ---- |
| Databricks | Business inputs, calculation outputs, run records (read-only) |
| Datadog | Operational observations within query windows |
| PostgreSQL | Issues, obligations, hypotheses, investigation state, manifests |
| Local Files | Immutable evidence, fixtures, reports, Git cache |

### Module Map

| Module | Purpose |
| ------ | ------- |
| `winston.domain` | Identities, calendars, revisions, evidence, issues |
| `winston.storage` | PostgreSQL + artifact store |
| `winston.sources` | Databricks, Datadog, synthetic adapters |
| `winston.repositories` | Registry, component maps, source reads |
| `winston.lineage` | Dependency graph, impact, replay planning |
| `winston.checks` | Deterministic business/chain/ops checks |
| `winston.context` | Validity, assembly, manifests |
| `winston.investigations` | Hypotheses, model interface |
| `winston.cli` | Command-line interface |

## Development

### Running Tests

```bash
# Unit tests (no database required)
pytest tests/unit -v

# Integration tests (requires PostgreSQL)
export WINSTON_TEST_DATABASE_URL="postgresql://winston:winston_dev@localhost:5432/winston_test"
pytest tests/integration -v -m integration
```

### Project Structure

```
winston/
├── src/winston/          # Main package
│   ├── domain/           # Domain models
│   ├── storage/          # Database and artifacts
│   ├── sources/          # Data source adapters
│   ├── cli/              # CLI commands
│   └── ...
├── tests/
│   ├── unit/             # Unit tests
│   └── integration/      # PostgreSQL integration tests
├── profiles/             # Profile definitions
├── registry/             # Repository registry
├── docs/                 # Documentation
├── alembic/              # Database migrations
├── docker-compose.yaml   # Local PostgreSQL
└── pyproject.toml        # Package configuration
```

## Configuration

Winston uses environment variables prefixed with `WINSTON_`:

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `WINSTON_DATABASE_URL` | `postgresql://winston:winston_dev@localhost:5432/winston` | PostgreSQL connection |
| `WINSTON_DATA_DIR` | `.winston` | Runtime data directory |
| `WINSTON_PROFILE` | `synthetic` | Active profile |
| `WINSTON_OFFLINE_MODE` | `true` | Block live network adapters |

## License

MIT
