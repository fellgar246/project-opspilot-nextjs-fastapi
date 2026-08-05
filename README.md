# OpsPilot AI

Local-first platform for AI-assisted incident investigation. This repository implements the project in spec-driven phases; **SPEC-01** delivers the executable skeleton.

## Quick start

Requirements: Docker, [uv](https://docs.astral.sh/uv/), [pnpm](https://pnpm.io/) (via Corepack).

```bash
git clone <repo-url> ops-pilot
cd ops-pilot
make bootstrap
make up
make smoke
```

Open [http://localhost:3000](http://localhost:3000) for the web UI and [http://localhost:8000/health](http://localhost:8000/health) for API health.

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

By default `MODEL_PROVIDER=mock` so the stack boots without external calls (principle C8). For real inference, set in `.env`:

```env
MODEL_PROVIDER=openai
OPENAI_API_KEY=sk-your-key
OPENAI_MODEL=gpt-4o-mini
```

See [ADR-009](docs/adr/ADR-009-openai-llm-provider.md).

## Quality gates

```bash
make lint typecheck test migrate security-scan
```

## Repository layout

```text
apps/          # api (FastAPI), web (Next.js), worker (ARQ)
packages/      # shared Python libraries
infra/         # compose fragments, scripts, observability configs
docs/          # ADRs, architecture, backlog
plans/         # executable specs (SPEC-01…SPEC-10)
simulator/     # production simulator (SPEC-04)
datasets/      # evaluation datasets
```

## Documentation

- [Architecture (C4)](docs/architecture/README.md)
- [ADRs](docs/adr/)
- [Backlog](docs/backlog.md)
- [Plan maestro](plans/AI_Incident_Response_Engineer_Plan_Maestro.md)
