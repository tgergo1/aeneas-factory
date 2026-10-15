"""ComfyUI nodes shipped with aeneas-factory (linked into ComfyUI's custom_nodes by `make comfyui`).

AeneasUnetLoaderGGUF: ComfyUI-GGUF's UNet loader, but able to read stable-diffusion.cpp GGUF files
(for example leejet/Z-Image-Turbo-GGUF, which the factory also uses with sd-cli). Those store
Z-Image's x_pad_token and cap_pad_token as flat [3840] tensors where ComfyUI expects [1, 3840];
the loader reshapes just those, so one file on disk serves both engines."""
import sys

import folder_paths
import torch

PAD_KEYS = ("x_pad_token", "cap_pad_token")


def _gguf_nodes():
    # Look in each module's own namespace: some (torch.ops) answer hasattr() for any name.
    for mod in list(sys.modules.values()):
        d = getattr(mod, "__dict__", {})
        if isinstance(d.get("UnetLoaderGGUF"), type) and callable(d.get("gguf_sd_loader")):
            return mod
    raise RuntimeError("ComfyUI-GGUF is not loaded; install it in custom_nodes")


class AeneasUnetLoaderGGUF:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"unet_name": (folder_paths.get_filename_list("unet_gguf"),)}}

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "load"
    CATEGORY = "aeneas"
    TITLE = "Unet Loader (GGUF, sd.cpp files)"

    def load(self, unet_name):
        gg = _gguf_nodes()
        original = gg.gguf_sd_loader

        def loader(path, *a, **k):
            sd, extra = original(path, *a, **k)
            for key in PAD_KEYS:
                t = sd.get(key)
                if t is not None and t.ndim == 1:
                    sd[key] = t.as_subclass(torch.Tensor).reshape(1, -1).clone()
            return sd, extra

        gg.gguf_sd_loader = loader
        try:
            return gg.UnetLoaderGGUF().load_unet(unet_name)
        finally:
            gg.gguf_sd_loader = original


NODE_CLASS_MAPPINGS = {"AeneasUnetLoaderGGUF": AeneasUnetLoaderGGUF}
NODE_DISPLAY_NAME_MAPPINGS = {"AeneasUnetLoaderGGUF": AeneasUnetLoaderGGUF.TITLE}
