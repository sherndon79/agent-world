# agentworld-core

Shared Python helpers for Agent World Isaac Sim extensions and MCP servers.

## Development

```bash
# From the repo root
pip install -e agentworld-core
```

When running tests or scripts without installing, add `agentworld-core/src` to
`PYTHONPATH`.

```bash
PYTHONPATH=agentworld-core/src python -m pytest agentworld-extensions/tests
```

## Contents

- `auth` – Security manager, HMAC/Bearer validation, rate limiting
- `config` – Unified extension configuration loader
- `logging` – Structured logging utilities shared across runtimes
- `metrics` – Request/health metrics collection
- `validation` – Input validation and asset path sanitizers
- `asset_security` – Safe asset path resolution helpers
- `transport` – Response normalization utilities
- `requests` – Request tracking helper used by HTTP/MCP transports
- `versions` – Helper utilities for extension version metadata
