"""Pydantic request/response models for the API."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ----------------------------- requests -----------------------------
class SDXLRequest(BaseModel):
    prompt: str = Field(..., description="Positive text prompt.")
    negative: str = Field(
        "text, watermark, low quality, blurry",
        description="Negative text prompt.",
    )
    width: int = Field(1024, ge=64, le=4096)
    height: int = Field(1024, ge=64, le=4096)
    steps: int = Field(28, ge=1, le=150)
    cfg: float = Field(7.0, ge=0.0, le=30.0)
    seed: int = Field(42, ge=0)
    sampler: str = Field("dpmpp_2m")
    scheduler: str = Field("karras")
    checkpoint: Optional[str] = Field(None, description="Override checkpoint filename.")


class FluxRequest(BaseModel):
    prompt: str = Field(..., description="Positive text prompt.")
    width: int = Field(1024, ge=64, le=4096)
    height: int = Field(1024, ge=64, le=4096)
    steps: int = Field(20, ge=1, le=150)
    guidance: float = Field(4.0, ge=0.0, le=30.0)
    seed: int = Field(42, ge=0)


class QwenEditRequest(BaseModel):
    image_path: str = Field(..., description="Path to a local source image to edit.")
    prompt: str = Field(..., description="Natural-language edit instruction.")
    seed: int = Field(42, ge=0)
    fast: bool = Field(
        True,
        description="Use the 4-step Lightning LoRA (~5x faster) instead of the full 20-step pass.",
    )


class UpscaleRequest(BaseModel):
    image_path: str = Field(..., description="Path to a local source image to upscale.")
    model: str = Field(
        "RealESRGAN_x4plus_anime_6B.pth",
        description="Upscale model filename available to ComfyUI.",
    )


# ----------------------------- responses -----------------------------
class GenerationResponse(BaseModel):
    images: list[str] = Field(..., description="Paths of the generated/downloaded images.")
    count: int = Field(..., description="Number of images produced.")


class HealthResponse(BaseModel):
    api: str = Field("ok", description="API liveness.")
    comfyui_reachable: bool = Field(..., description="Whether the ComfyUI server responded.")
    comfyui_url: str = Field(..., description="Configured ComfyUI base URL.")
