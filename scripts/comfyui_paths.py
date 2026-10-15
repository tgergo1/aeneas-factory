"""Print ComfyUI's extra_model_paths.yaml so ComfyUI reads the factory's models/ in place (no copies).
`make comfyui` writes the output to tools/ComfyUI/extra_model_paths.yaml."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"

print(f"""# Written by aeneas-factory (scripts/comfyui_paths.py): ComfyUI uses the factory's models in place.
aeneas:
  base_path: {MODELS}
  diffusion_models: |
    z-image-turbo
    flux2-klein-4b
  unet: |
    z-image-turbo
    flux2-klein-4b
  text_encoders: z-image-turbo
  clip: z-image-turbo
  vae: |
    z-image-turbo
    flux2-klein-4b
  upscale_models: realesrgan-x4plus
""")
