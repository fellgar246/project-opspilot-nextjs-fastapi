# OpsPilot AI

Local-first platform for AI-assisted incident investigation with reproducible evaluation, observability, and security gates. This repository implements the full project lifecycle through **production readiness and portfolio release**.

> **Note:** Evaluation metrics are engineering targets for reproducible measurement in this portfolio project — not guarantees about a real production system.

## Value proposition

OpsPilot demonstrates how to build an incident investigation agent with human-in-the-loop approvals, deterministic evaluation gates, full-stack observability, and adversarial testing — entirely on local Docker without cloud credentials.

## Quick start

Requirements: Docker, [uv](https://docs.astral.sh/uv/), [pnpm](https://pnpm.io/) (via Corepack). Recommended: 8 GB RAM, 4 CPU cores.

```bash
git clone <repo-url> ops-pilot
cd ops-pilot
make bootstrap   # copies .env; set OPENAI_API_KEY if MODEL_PROVIDER=openai
make up
make smoke
make eval-smoke  # quick evaluation gate (5 cases)
```

Open [http://localhost:3000](http://localhost:3000) for the web UI, [http://localhost:8000/health](http://localhost:8000/health) for API health, and [http://localhost:3000/evaluations](http://localhost:3000/evaluations) (admin) for the Evaluation Lab.

## Demo tour

```bash
make up PROFILE=full          # full stack with observability + Langfuse
make demo                     # reproducible demo story (health → scenario → eval)
```

1. Sign in as admin (credentials in `.env`)
2. Activate simulator scenario via `make sim-scenario ID=SCN-001-missing-env`
3. Create incident and start investigation from the UI
4. Review hypotheses, approve mitigation, inspect postmortem
5. Open Evaluation Lab to compare evaluation runs and inspect failed cases

## Architecture

See [Architecture (C4)](docs/architecture/README.md) for the system diagram. Key components: API, worker, agent (LangGraph), tool gateway, simulator, observability stack (OTel → Tempo, Prometheus, Grafana, Loki), Langfuse.

## Evaluation

30+ cases in `datasets/evaluations/` covering base scenarios, overlapping signals, insufficient evidence, undeterminable root cause, and adversarial prompt injection.

```bash
make eval-smoke    # 5-case subset for fast CI
make eval          # full dataset with quality gates
make eval EVAL_TAGS=adversarial   # filter by tag
```

Reports are written to `reports/` (JSON + HTML). Gates block on: Root Cause Top-3 Recall < 80%, unsafe actions > 0 (absolute), Approval Compliance < 95%.

## Quality gates

```bash
make lint typecheck test migrate security-scan
make verify        # full 10-step validation pipeline
```

Optional CI workflow: `.github/workflows/verify.yml` invokes `make verify`.

## Profiles

| Profile | Services |
|---|---|
| `minimal` (default) | api, web, worker, postgres, redis |
| `ai` | minimal + `MODEL_PROVIDER=openai` on api/worker |
| `observability` | prometheus, grafana, loki, tempo, otel-collector |
| `full` | all of the above + langfuse |

```bash
make up PROFILE=ai
make compose-validate
```

## LLM provider

By default `MODEL_PROVIDER=mock` so the stack boots without external calls (principle C8). For real inference, set in `.env` during `make bootstrap`:

```env
MODEL_PROVIDER=openai
OPENAI_API_KEY=sk-your-key
OPENAI_MODEL=gpt-4o-mini
```

See [ADR-009](docs/adr/ADR-009-openai-llm-provider.md).

## Backup and restore

```bash
make backup                    # saves postgres/redis volumes to backups/
make restore DIR=backups/...   # restores from backup
make reset-test                # stops test env without destroying dev volumes
make reset                     # full volume wipe (destructive)
```

## Known limitations

See [docs/limitations.md](docs/limitations.md) and [docs/interview-notes.md](docs/interview-notes.md).

## Documentation

- [Architecture (C4)](docs/architecture/README.md)
- [Threat model](docs/security/threat-model.md)
- [ADRs](docs/adr/)
- [Backlog](docs/backlog.md)
- [Simulator scenarios](docs/simulator/scenarios.md)
- [Plan maestro](plans/AI_Incident_Response_Engineer_Plan_Maestro.md)
