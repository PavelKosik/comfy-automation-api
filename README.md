# ComfyUI Automation API

A small, portable **FastAPI service that turns a running [ComfyUI](https://github.com/comfyanonymous/ComfyUI) instance into a clean REST API.** Instead of clicking nodes in the ComfyUI web UI, you send a JSON request to an endpoint like `POST /generate/sdxl`; the service builds the matching ComfyUI workflow graph, queues it, polls for completion, downloads the result, and returns the image paths. It is a thin, typed automation layer — ComfyUI does the heavy lifting; this service makes it scriptable, headless, and integration-friendly.

## Why

ComfyUI is a powerful node-graph engine but is designed around its web UI. Wiring it into a backend, a batch pipeline, or another product means talking to its raw HTTP API and hand-building prompt graphs. This project encapsulates that: predictable endpoints, validated Pydantic request/response models, async I/O, and configuration via environment variables so it runs the same on a laptop or in a container.

## Architecture

```
   ┌──────────────┐   HTTP/JSON    ┌─────────────────────┐   HTTP API    ┌──────────────┐
   │ Your client  │ ─────────────► │ ComfyUI Automation  │ ────────────► │   ComfyUI    │
   │ (curl / app) │ ◄───────────── │   API (FastAPI)     │ ◄──────────── │   server     │
   └──────────────┘   image paths  └─────────────────────┘  prompt graph └──────┬───────┘
                                                                                 │ GPU + weights
                                                                          ┌──────┴───────┐
                                                                          │ model files  │
                                                                          └──────────────┘
```

- **app/main.py** — FastAPI app and endpoints.
- **app/comfy_client.py** — async client for ComfyUI's HTTP API (`/prompt`, `/history`, `/view`, `/upload/image`, `/system_stats`).
- **app/workflows.py** — builders that produce ComfyUI prompt graphs for each pipeline.
- **app/models.py** — Pydantic request/response schemas.
- **app/config.py** — settings from environment variables.

## Endpoints

| Method | Path             | Purpose                                            | Example body |
|--------|------------------|----------------------------------------------------|--------------|
| GET    | `/health`        | Liveness + whether ComfyUI is reachable            | —            |
| POST   | `/generate/sdxl` | SDXL text-to-image                                 | `{"prompt": "a red sports car, studio lighting"}` |
| POST   | `/generate/flux` | FLUX.2-klein text-to-image                          | `{"prompt": "a Formula 1 race car"}` |
| POST   | `/edit/qwen`     | Instruction-based image edit (Qwen-Image-Edit)     | `{"image_path": "car.png", "prompt": "make it a police car"}` |
| POST   | `/upscale`       | Model-based upscale (e.g. Real-ESRGAN)             | `{"image_path": "car.png"}` |

Interactive docs are served at `/docs` (Swagger) and `/redoc`.

### Example requests

```bash
# Health
curl http://localhost:8000/health

# SDXL text-to-image
curl -X POST http://localhost:8000/generate/sdxl \
  -H "Content-Type: application/json" \
  -d '{"prompt": "a chunky cartoon race car, white background", "steps": 28}'

# FLUX.2-klein text-to-image
curl -X POST http://localhost:8000/generate/flux \
  -H "Content-Type: application/json" \
  -d '{"prompt": "a Formula 1 race car, studio lighting", "guidance": 4.0}'

# Instruction-based edit (fast 4-step Lightning LoRA by default)
curl -X POST http://localhost:8000/edit/qwen \
  -H "Content-Type: application/json" \
  -d '{"image_path": "/path/to/car.png", "prompt": "change to police livery, keep shape and angle"}'

# Upscale
curl -X POST http://localhost:8000/upscale \
  -H "Content-Type: application/json" \
  -d '{"image_path": "/path/to/sprite.png"}'
```

## Supported pipelines

| Pipeline            | Endpoint         | Notes |
|---------------------|------------------|-------|
| **SDXL**            | `/generate/sdxl` | Standard checkpoint + KSampler text-to-image. |
| **FLUX.2-klein**    | `/generate/flux` | Flow-matching `SamplerCustomAdvanced` graph. |
| **Qwen-Image-Edit** | `/edit/qwen`     | Natural-language image editing; optional 4-step Lightning LoRA for ~5x faster edits. |
| **Real-ESRGAN**     | `/upscale`       | Model-based image upscaling. |

Model/checkpoint filenames default to common conventions and can be overridden per request; the actual weights must already be installed in your ComfyUI instance.

## Running

This service assumes a **ComfyUI server is already running** and reachable. It can target a local or a remote instance.

1. Start ComfyUI separately (its own process, with the GPU and model weights), e.g.:
   ```bash
   python main.py --listen 127.0.0.1 --port 8188
   ```
2. Configure and start the API:
   ```bash
   pip install -r requirements.txt
   cp .env.example .env          # optional; edit to point at your ComfyUI
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
3. Verify: `curl http://localhost:8000/health`

### Configuration

All settings come from environment variables (see `.env.example`):

| Variable        | Default                  | Description |
|-----------------|--------------------------|-------------|
| `COMFYUI_HOST`  | `127.0.0.1`              | ComfyUI host/IP. |
| `COMFYUI_PORT`  | `8188`                   | ComfyUI port. |
| `COMFYUI_SCHEME`| `http`                   | `http` or `https`. |
| `OUTPUT_DIR`    | `./outputs`              | Where decoded images are written. |
| `CLIENT_ID`     | `comfy-automation-api`   | Client id reported to ComfyUI. |
| `JOB_TIMEOUT`   | `900`                    | Per-job wait timeout (seconds). |
| `POLL_INTERVAL` | `2.0`                    | History poll interval (seconds). |

### Docker

The provided `Dockerfile` builds the **API only** — ComfyUI runs separately.

```bash
docker build -t comfy-automation-api .
docker run --rm -p 8000:8000 \
  -e COMFYUI_HOST=host.docker.internal -e COMFYUI_PORT=8188 \
  -v "$(pwd)/outputs:/data/outputs" \
  comfy-automation-api
```

## Scope (honest notes)

- This is an **automation/orchestration layer**, not a model server. It does not run inference itself; it delegates to ComfyUI, which must be installed and running with the relevant models.
- The workflow graphs mirror common ComfyUI templates for each model family. Node class names and default weight filenames assume a fairly standard ComfyUI setup; adjust the builders in `app/workflows.py` to match custom nodes or differently-named checkpoints.
- It is a focused, single-purpose service: no auth, queueing, or persistence layer is included by design — those belong to whatever system embeds it.

## License

MIT.
