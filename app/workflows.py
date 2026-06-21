"""ComfyUI workflow (prompt graph) builders.

Each function returns a ComfyUI "prompt" dict — a node graph keyed by node id —
ready to POST to ``/prompt``. The graphs mirror ComfyUI's official templates for
each model family and expose only the parameters worth tuning from an API.

Model/checkpoint names below are the conventional filenames these pipelines use;
override them per request if your ComfyUI install names them differently.
"""
from __future__ import annotations

from typing import Optional


def sdxl_txt2img(
    prompt: str,
    negative: str = "text, watermark, low quality, blurry",
    width: int = 1024,
    height: int = 1024,
    steps: int = 28,
    cfg: float = 7.0,
    seed: int = 42,
    sampler: str = "dpmpp_2m",
    scheduler: str = "karras",
    checkpoint: str = "sd_xl_base_1.0.safetensors",
    vae: str = "sdxl_vae.safetensors",
    prefix: str = "sdxl",
) -> dict:
    """Standard SDXL text-to-image graph (CheckpointLoader + KSampler)."""
    return {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "11": {"class_type": "VAELoader", "inputs": {"vae_name": vae}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["4", 1]}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "3": {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": steps, "cfg": cfg, "sampler_name": sampler,
            "scheduler": scheduler, "denoise": 1.0,
            "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["11", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["8", 0]}},
    }


def flux_txt2img(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    steps: int = 20,
    guidance: float = 4.0,
    seed: int = 42,
    unet: str = "flux-2-klein-base-4b-fp8.safetensors",
    clip: str = "qwen_3_4b.safetensors",
    vae: str = "full_encoder_small_decoder.safetensors",
    prefix: str = "flux",
) -> dict:
    """FLUX.2-klein text-to-image graph (flow-matching SamplerCustomAdvanced)."""
    return {
        "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": "default"}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": clip, "type": "flux2", "device": "default"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": vae}},
        "pos": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["clip", 0]}},
        "guid": {"class_type": "FluxGuidance", "inputs": {"conditioning": ["pos", 0], "guidance": guidance}},
        "guider": {"class_type": "BasicGuider", "inputs": {"model": ["unet", 0], "conditioning": ["guid", 0]}},
        "sched": {"class_type": "Flux2Scheduler", "inputs": {"steps": steps, "width": width, "height": height}},
        "samplersel": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "noise": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "latent": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "sampler": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["noise", 0], "guider": ["guider", 0], "sampler": ["samplersel", 0],
            "sigmas": ["sched", 0], "latent_image": ["latent", 0]}},
        "dec": {"class_type": "VAEDecode", "inputs": {"samples": ["sampler", 0], "vae": ["vae", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["dec", 0]}},
    }


def upscale(
    image_name: str,
    model: str = "RealESRGAN_x4plus_anime_6B.pth",
    prefix: str = "upscaled",
) -> dict:
    """Model-based image upscale graph (e.g. Real-ESRGAN)."""
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "2": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": model}},
        "3": {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["2", 0], "image": ["1", 0]}},
        "4": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["3", 0]}},
    }


# Optional 4-step Lightning LoRA: pass to ``qwen_edit`` with steps=4, cfg=1.0 for ~5x faster edits.
QWEN_LIGHTNING_LORA = "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors"


def qwen_edit(
    image_name: str,
    prompt: str,
    seed: int = 42,
    steps: int = 20,
    cfg: float = 2.5,
    gguf: str = "qwen-image-edit-2511-Q3_K_M.gguf",
    clip: str = "qwen_2.5_vl_7b_fp8_scaled.safetensors",
    vae: str = "qwen_image_vae.safetensors",
    lora: Optional[str] = None,
    prefix: str = "qwen_edit",
) -> dict:
    """Qwen-Image-Edit instruction-based image editing graph.

    Pass ``lora=QWEN_LIGHTNING_LORA`` with ``steps=4, cfg=1.0`` for fast edits.
    """
    model_src = ["unet", 0]
    wf = {
        "load": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "scale": {"class_type": "FluxKontextImageScale", "inputs": {"image": ["load", 0]}},
        "unet": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": gguf}},
        "clip": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": clip, "type": "qwen_image", "device": "default"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": vae}},
        "pos": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {
            "clip": ["clip", 0], "vae": ["vae", 0], "image1": ["scale", 0], "prompt": prompt}},
        "neg": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {
            "clip": ["clip", 0], "vae": ["vae", 0], "image1": ["scale", 0], "prompt": ""}},
        "enc": {"class_type": "VAEEncode", "inputs": {"pixels": ["scale", 0], "vae": ["vae", 0]}},
    }
    if lora:
        wf["lora"] = {"class_type": "LoraLoaderModelOnly",
                      "inputs": {"model": ["unet", 0], "lora_name": lora, "strength_model": 1.0}}
        model_src = ["lora", 0]
    wf["ms"] = {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": model_src, "shift": 3.0}}
    wf["cfgn"] = {"class_type": "CFGNorm", "inputs": {"model": ["ms", 0], "strength": 1.0}}
    wf["ksampler"] = {"class_type": "KSampler", "inputs": {
        "model": ["cfgn", 0], "positive": ["pos", 0], "negative": ["neg", 0], "latent_image": ["enc", 0],
        "seed": seed, "steps": steps, "cfg": cfg, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}}
    wf["dec"] = {"class_type": "VAEDecode", "inputs": {"samples": ["ksampler", 0], "vae": ["vae", 0]}}
    wf["save"] = {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["dec", 0]}}
    return wf
