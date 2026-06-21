"""Application settings, sourced from environment variables with sane defaults.

Nothing here is machine-specific: point ``COMFYUI_HOST`` / ``COMFYUI_PORT`` at any
ComfyUI instance (local or remote) and set ``OUTPUT_DIR`` to wherever generated
images should land.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


class Settings:
    """Runtime configuration resolved from the environment.

    Environment variables (all optional):
        COMFYUI_HOST   ComfyUI hostname or IP            (default: 127.0.0.1)
        COMFYUI_PORT   ComfyUI port                      (default: 8188)
        COMFYUI_SCHEME http or https                     (default: http)
        OUTPUT_DIR     where decoded images are written  (default: ./outputs)
        CLIENT_ID      client id sent to ComfyUI         (default: comfy-automation-api)
        JOB_TIMEOUT    seconds to wait per job           (default: 900)
        POLL_INTERVAL  history poll interval in seconds   (default: 2.0)
    """

    def __init__(self) -> None:
        self.comfyui_host: str = os.environ.get("COMFYUI_HOST", "127.0.0.1")
        self.comfyui_port: int = int(os.environ.get("COMFYUI_PORT", "8188"))
        self.comfyui_scheme: str = os.environ.get("COMFYUI_SCHEME", "http")
        self.output_dir: Path = Path(
            os.environ.get("OUTPUT_DIR", str(Path.cwd() / "outputs"))
        )
        self.client_id: str = os.environ.get("CLIENT_ID", "comfy-automation-api")
        self.job_timeout: int = int(os.environ.get("JOB_TIMEOUT", "900"))
        self.poll_interval: float = float(os.environ.get("POLL_INTERVAL", "2.0"))

    @property
    def comfyui_base_url(self) -> str:
        """Fully-qualified base URL of the ComfyUI HTTP API."""
        return f"{self.comfyui_scheme}://{self.comfyui_host}:{self.comfyui_port}"


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance (FastAPI dependency-friendly)."""
    return Settings()
