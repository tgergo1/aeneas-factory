"""Kokoro text to speech with the PyTorch kokoro package, from local files only (nothing is downloaded).
Run with the speech environment's Python:  python kokoro_torch.py MODEL_DIR VOICE SPEED TEXT_FILE OUT.wav"""
import os
import sys

os.environ["HF_HUB_OFFLINE"] = "1"  # every file is passed as a path; never reach the Hub

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
import torch  # noqa: E402
from kokoro import KModel, KPipeline  # noqa: E402

REPO = "hexgrad/Kokoro-82M"  # only names the model family; the weights come from MODEL_DIR


def main():
    model_dir, voice, speed, text_file, out = sys.argv[1:6]
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = KModel(repo_id=REPO, config=os.path.join(model_dir, "config.json"),
                   model=os.path.join(model_dir, "kokoro-v1_0.pth")).to(device).eval()
    pipe = KPipeline(lang_code=voice[0], repo_id=REPO, model=model)  # a: American English, b: British English
    text = open(text_file, encoding="utf-8").read()
    parts = [r.audio.cpu().numpy() for r in pipe(text, voice=os.path.join(model_dir, "voices", f"{voice}.pt"),
                                                  speed=float(speed)) if r.audio is not None]
    if not parts:
        sys.exit("kokoro produced no audio")
    sf.write(out, np.concatenate(parts), 24000)
    print(f"wrote {out} on {device}")


if __name__ == "__main__":
    main()
