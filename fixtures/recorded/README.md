# Recorded fixtures

Offline continual-testing bundles. Schema version `1.0.0`.

## Layout

```
<bundle>/
  manifest.json      # schema, case, change, policy
  graph.json         # nodes + dependency edges
  evidence.json      # allowlisted receipts/snapshots only
  expectations.json  # impact assertions for replay
```

## Policy

- No credentials, tokens, passwords, or auth headers
- No customer P&L / positions / inventory
- Replay is offline-only (`--offline`)

## Samples

Checked-in samples live under `samples/` and are safe for CI.

Runtime recordings (larger / environment-specific) go under `.winston/fixtures/recorded/` (gitignored).

```bash
winston record --case supercalc-late-correction --output .winston/fixtures/recorded/my-run
winston replay --bundle supercalc-stress-s2-correction --offline
```
