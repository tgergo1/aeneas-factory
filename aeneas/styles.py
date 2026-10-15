"""Style packs: what keeps a project's content consistent. A style is a folder with style.toml:

  name = "storybook"
  description = "Warm, painterly, soft light"
  prompt_prefix = ""
  prompt_suffix = ", painterly storybook illustration, warm soft light, muted earthy palette"
  negative = "photo, 3d render, text, watermark"
  model = "z-image-turbo"            # preferred image model
  references = ["refs/a.png"]        # used with flux2-klein-4b as style references
  loras = [["my_style", 0.8]]        # LoRA files in the style's loras/ folder (sd.cpp format)
  palette = ["#6b4f3a", "#c9a66b"]   # recorded; shown to agents
  sfx_suffix = ", recorded close, dry, natural"

Styles are looked up in <project>/.aeneas/styles/<name>/ first, then in the factory's styles/.
"""
import tomllib
from pathlib import Path

from .paths import ROOT
from .policy import project_root


class StyleError(Exception):
    pass


def find(name, near=None):
    dirs = []
    if near:
        dirs.append(project_root(near) / ".aeneas" / "styles" / name)
    dirs.append(ROOT / "styles" / name)
    for d in dirs:
        if (d / "style.toml").exists():
            s = tomllib.loads((d / "style.toml").read_text())
            s["_dir"] = d
            s.setdefault("name", name)
            return s
    raise StyleError(f"no style named {name} (looked in {', '.join(str(d) for d in dirs)})")


def list_styles(near=None):
    out = {}
    roots = [ROOT / "styles"] + ([project_root(near) / ".aeneas" / "styles"] if near else [])
    for r in roots:
        if r.is_dir():
            for d in sorted(r.iterdir()):
                if (d / "style.toml").exists():
                    s = tomllib.loads((d / "style.toml").read_text())
                    out[d.name] = s.get("description", "")
    return out


def apply_image(style, prompt, negative=None, model=None):
    """Returns (prompt, negative, model, refs, loras, lora_dir) with the style applied."""
    if not style:
        return prompt, negative, model, [], [], None
    p = f"{style.get('prompt_prefix', '')}{prompt}{style.get('prompt_suffix', '')}"
    neg = ", ".join(x for x in (negative, style.get("negative")) if x) or None
    model = model or style.get("model")
    refs = [style["_dir"] / r for r in style.get("references", [])]
    for r in refs:
        if not r.exists():
            raise StyleError(f"style {style['name']}: missing reference {r}")
    loras = [(n, float(w)) for n, w in style.get("loras", [])]
    lora_dir = style["_dir"] / "loras" if loras else None
    return p, neg, model, refs, loras, lora_dir


def summary(style):
    if not style:
        return None
    return {k: style.get(k) for k in ("name", "description", "prompt_prefix", "prompt_suffix", "negative", "model",
                                      "references", "loras", "palette") if style.get(k)}
