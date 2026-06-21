"""ComfyUI Automation API — FastAPI application.

A clean, typed automation layer over a running ComfyUI server. It exposes a small
set of REST endpoints that build ComfyUI workflows, queue them, wait for results
and return the produced image paths.

Run locally:
    uvicorn app.main:app --host 0.0.0.0 --port 8000

The ComfyUI server is a separate process; configure its location with the
COMFYUI_HOST / COMFYUI_PORT environment variables (see app/config.py).
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException

from .comfy_client import ComfyClient, ComfyError
from .config import Settings, get_settings
from .models import (
    FluxRequest,
    GenerationResponse,
    HealthResponse,
    QwenEditRequest,
    SDXLRequest,
    UpscaleRequest,
)
from . import workflows

app = FastAPI(
    title="ComfyUI Automation API",
    description="A portable FastAPI layer over a local or remote ComfyUI server.",
    version="0.1.0",
)


def get_client(settings: Settings = Depends(get_settings)) -> ComfyClient:
    """FastAPI dependency that builds a ComfyClient from current settings."""
    return ComfyClient(settings)


def _response(images: list) -> GenerationResponse:
    return GenerationResponse(images=[str(p) for p in images], count=len(images))


@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health(
    client: ComfyClient = Depends(get_client),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """Liveness probe; also reports whether ComfyUI is reachable."""
    return HealthResponse(
        api="ok",
        comfyui_reachable=await client.server_up(),
        comfyui_url=settings.comfyui_base_url,
    )


@app.post("/generate/sdxl", response_model=GenerationResponse, tags=["generate"])
async def generate_sdxl(
    req: SDXLRequest,
    client: ComfyClient = Depends(get_client),
) -> GenerationResponse:
    """Generate an image with SDXL text-to-image."""
    # exclude_none drops an unset optional 'checkpoint' so the builder default applies.
    workflow = workflows.sdxl_txt2img(**req.model_dump(exclude_none=True))
    try:
        images = await client.generate(workflow)
    except (ComfyError, TimeoutError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _response(images)


@app.post("/generate/flux", response_model=GenerationResponse, tags=["generate"])
async def generate_flux(
    req: FluxRequest,
    client: ComfyClient = Depends(get_client),
) -> GenerationResponse:
    """Generate an image with FLUX.2-klein text-to-image."""
    workflow = workflows.flux_txt2img(**req.model_dump())
    try:
        images = await client.generate(workflow)
    except (ComfyError, TimeoutError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _response(images)


@app.post("/edit/qwen", response_model=GenerationResponse, tags=["edit"])
async def edit_qwen(
    req: QwenEditRequest,
    client: ComfyClient = Depends(get_client),
) -> GenerationResponse:
    """Edit an image with a natural-language instruction (Qwen-Image-Edit)."""
    try:
        image_name = await client.upload_image(req.image_path)
    except (OSError, ComfyError) as exc:
        raise HTTPException(status_code=400, detail=f"Could not upload image: {exc}") from exc

    if req.fast:
        workflow = workflows.qwen_edit(
            image_name, req.prompt, seed=req.seed,
            steps=4, cfg=1.0, lora=workflows.QWEN_LIGHTNING_LORA,
        )
    else:
        workflow = workflows.qwen_edit(
            image_name, req.prompt, seed=req.seed, steps=20, cfg=2.5,
        )
    try:
        images = await client.generate(workflow, timeout=1200)
    except (ComfyError, TimeoutError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _response(images)


@app.post("/upscale", response_model=GenerationResponse, tags=["edit"])
async def upscale(
    req: UpscaleRequest,
    client: ComfyClient = Depends(get_client),
) -> GenerationResponse:
    """Upscale an image with a model-based upscaler (e.g. Real-ESRGAN)."""
    try:
        image_name = await client.upload_image(req.image_path)
    except (OSError, ComfyError) as exc:
        raise HTTPException(status_code=400, detail=f"Could not upload image: {exc}") from exc

    workflow = workflows.upscale(image_name, model=req.model)
    try:
        images = await client.generate(workflow)
    except (ComfyError, TimeoutError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _response(images)
