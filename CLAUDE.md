# CLAUDE.md

Project handbook for [Claude Code](https://claude.com/claude-code) (and any AI assistant) working in this repository. This project was built with Claude Code, and this file is the source of truth for how to extend it.

## What this is

A small, portable **FastAPI service that wraps a running [ComfyUI](https://github.com/comfyanonymous/ComfyUI) instance in a clean REST API**. Clients POST JSON to endpoints like `/generate/sdxl`; the service builds the matching ComfyUI prompt graph, queues it, polls for completion, downloads the result, and returns image paths. It is an **automation/orchestration layer, not a model server** — ComfyUI does the inference; this makes it scriptable, headless, and integration-friendly.

See `README.md` for the user-facing overview, endpoint table, and run instructions.

## Layout

```
app/
  main.py          # FastAPI app + endpoints (the public surface)
  comfy_client.py  # async client for ComfyUI's HTTP API (/prompt, /history, /view, /upload/image, /system_stats)
  workflows.py     # builders that emit ComfyUI prompt graphs, one per pipeline
  models.py        # Pydantic request/response schemas
  config.py        # settings, all from environment variables
requirements.txt
Dockerfile         # builds the API only — ComfyUI runs as a separate process
.env.example       # documents every config var; never commit a real .env
```

## How it flows

`request → Pydantic model (models.py) → workflow builder (workflows.py) → ComfyClient.queue + poll (comfy_client.py) → download → response`

Adding a new pipeline (the common task) means touching, in order:
1. `workflows.py` — add a `build_<name>_workflow(...)` that returns the ComfyUI graph dict.
2. `models.py` — add the request/response Pydantic models.
3. `main.py` — add the endpoint that validates input, calls the builder, queues via the client, returns paths.

Keep that four-file rhythm. Don't inline graph-building into `main.py`.

## Conventions

- **Async everywhere.** `comfy_client.py` is async; endpoints are `async def`. Don't introduce blocking I/O in the request path.
- **Config via environment only.** Every tunable lives in `config.py` sourced from env vars and is documented in `.env.example`. No hardcoded hosts, ports, paths, or secrets — ever.
- **Validate at the boundary.** All input is a Pydantic model so bad requests fail with a clear 422 before touching ComfyUI.
- **ComfyUI is assumed external and already running.** This service must run the same on a laptop or in a container; never assume a specific local install beyond what `config.py` exposes.
- **Node class names and default checkpoint filenames** in `workflows.py` mirror a fairly standard ComfyUI setup. If you change a model family, update the builder, not the endpoint.
- Match the surrounding style: small focused functions, type hints, no over-abstraction. This is intentionally a single-purpose service — no auth, queueing, or persistence by design.

## Working here

```bash
pip install -r requirements.txt
cp .env.example .env          # point at your ComfyUI
uvicorn app.main:app --reload --port 8000
curl http://localhost:8000/health
```

Interactive docs at `/docs`. Health endpoint reports whether ComfyUI is actually reachable — use it to tell "my service is broken" from "ComfyUI is down."

## Guardrails

- Never commit `.env`, `outputs/`, model weights, or any generated images.
- Never hardcode a credential or an absolute machine path; add a config var instead.
- Keep `README.md`'s endpoint table in sync when you add or change an endpoint.
