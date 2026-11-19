# Winston

Winston is an operations agent that manages system context over time.

It keeps a durable record of how a system is set up, what has changed, and what still matters, so later decisions can be made from that history rather than from a fresh snapshot.

## Status

**Phase 1 (Foundation)** - Core infrastructure complete:
- PostgreSQL storage with Alembic migrations
- Artifact store with atomic writes and digest verification
- Domain models for issues, obligations, executions, and evidence
- Synthetic source adapter for offline testing
- CLI skeleton with doctor command

## Quick Start

### Prerequisites

- Python 3.8+
- PostgreSQL 13+
- Docker & Docker Compose (optional, for local PostgreSQL)

### Setup

1. **Start PostgreSQL** (using Docker Compose):

```bash
docker compose up -d
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
