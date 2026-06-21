"""Async HTTP client for a ComfyUI server.

This is a portable, sanitized port of a headless ComfyUI driver. It talks to
ComfyUI's HTTP API (``/prompt``, ``/history``, ``/view``, ``/upload/image``,
``/system_stats``) and knows nothing about where it runs — host, port and output
directory all come from :class:`app.config.Settings`.

The client is fully async (``httpx.AsyncClient``) so a single FastAPI worker can
service multiple generation jobs without blocking the event loop.
"""
from __future__ import annotations

import asyncio
import json
import urllib.parse
from pathlib import Path

import httpx

from .config import Settings


class ComfyError(RuntimeError):
    """Raised when ComfyUI rejects a prompt or reports an execution error."""


class ComfyClient:
    """Thin async wrapper over the ComfyUI HTTP API."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = settings.comfyui_base_url

    # ----------------------------- health -----------------------------
    async def server_up(self) -> bool:
        """Return ``True`` if the ComfyUI server answers ``/system_stats``."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self._base_url}/system_stats")
                return resp.status_code == 200
        except httpx.HTTPError:
            return False

    # ----------------------------- core -----------------------------
    async def submit(self, workflow: dict, client_id: str | None = None) -> str:
        """Queue a workflow and return its ``prompt_id``."""
        cid = client_id or self._settings.client_id
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._base_url}/prompt",
                json={"prompt": workflow, "client_id": cid},
            )
        if resp.status_code != 200:
            raise ComfyError(f"/prompt rejected ({resp.status_code}): {resp.text}")
        return resp.json()["prompt_id"]

    async def wait(self, prompt_id: str, timeout: int | None = None) -> dict:
        """Poll ``/history`` until the job completes, then return its entry."""
        timeout = timeout or self._settings.job_timeout
        poll = self._settings.poll_interval
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        async with httpx.AsyncClient(timeout=30.0) as client:
            while loop.time() < deadline:
                resp = await client.get(f"{self._base_url}/history/{prompt_id}")
                history = resp.json()
                if prompt_id in history:
                    return history[prompt_id]
                await asyncio.sleep(poll)
        raise TimeoutError(f"workflow {prompt_id} did not finish within {timeout}s")

    async def upload_image(self, path: str | Path) -> str:
        """Upload a local image into ComfyUI's input folder; return its name."""
        path = Path(path)
        with path.open("rb") as fh:
            files = {"image": (path.name, fh, "image/png")}
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self._base_url}/upload/image",
                    files=files,
                    data={"overwrite": "true"},
                )
        resp.raise_for_status()
        return resp.json()["name"]

    async def _download_images(self, entry: dict, out_dir: Path) -> list[Path]:
        """Download every image referenced in a history entry to ``out_dir``."""
        out_dir.mkdir(parents=True, exist_ok=True)
        saved: list[Path] = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            for _node, node_out in entry.get("outputs", {}).items():
                for img in node_out.get("images", []):
                    query = urllib.parse.urlencode({
                        "filename": img["filename"],
                        "subfolder": img.get("subfolder", ""),
                        "type": img.get("type", "output"),
                    })
                    resp = await client.get(f"{self._base_url}/view?{query}")
                    resp.raise_for_status()
                    dest = out_dir / img["filename"]
                    dest.write_bytes(resp.content)
                    saved.append(dest)
        return saved

    async def generate(
        self,
        workflow: dict,
        out_dir: str | Path | None = None,
        client_id: str | None = None,
        timeout: int | None = None,
    ) -> list[Path]:
        """Submit a workflow, wait for completion and download its outputs."""
        out_dir = Path(out_dir) if out_dir else self._settings.output_dir
        prompt_id = await self.submit(workflow, client_id=client_id)
        entry = await self.wait(prompt_id, timeout=timeout)

        status = entry.get("status", {})
        if status.get("status_str") == "error":
            raise ComfyError(
                "ComfyUI execution error:\n"
                + json.dumps(status.get("messages", []), indent=2)
            )

        images = await self._download_images(entry, out_dir)
        if not images:
            raise ComfyError(
                "No images produced. status=" + json.dumps(status, indent=2)
            )
        return images
