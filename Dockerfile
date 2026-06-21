# ComfyUI Automation API — the FastAPI service only.
#
# NOTE: This image contains the automation API, NOT ComfyUI itself. ComfyUI runs
# as a separate process/container (it needs the GPU and model weights). Point the
# API at it with COMFYUI_HOST / COMFYUI_PORT.
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code.
COPY app ./app

# Default config — override at runtime with -e / --env-file.
ENV COMFYUI_HOST=host.docker.internal \
    COMFYUI_PORT=8188 \
    OUTPUT_DIR=/data/outputs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
