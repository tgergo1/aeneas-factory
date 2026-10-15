"""A long-lived MOSS-SoundEffect worker. Runs in the MOSS environment (MLX), loads the model once
and then takes one JSON request per line on stdin, answering one JSON line on stdout.

  {"prompt": "...", "seconds": 5, "steps": 100, "cfg": 4.0, "seed": 1, "out": "/abs/path.wav"}
  -> {"ok": true, "peak": 0.42, "seconds": 31.2}   or   {"ok": false, "error": "..."}

Only this protocol is spoken: no code is evaluated, and output paths come from the factory.
"""
import json
import sys
import time
import wave
from pathlib import Path

import numpy as np


def save_wav(path, audio, rate):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(audio, -1.0, 1.0) * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(pcm.shape[0])
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.T.tobytes())


def main():
    model_dir = sys.argv[1]
    from moss_sfx_mlx.pipeline_mlx import MossSoundEffectPipeline
    t = time.time()
    pipe = MossSoundEffectPipeline.from_pretrained(model_dir)
    print(json.dumps({"ready": True, "load_seconds": round(time.time() - t, 1)}), flush=True)
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
            t = time.time()
            audio = pipe(prompt=str(req["prompt"]), seconds=float(req["seconds"]),
                         num_inference_steps=int(req["steps"]), cfg_scale=float(req["cfg"]), seed=int(req["seed"]))
            a = np.array(audio[0]).astype(np.float32)
            save_wav(req["out"], a, pipe.sample_rate)
            print(json.dumps({"ok": True, "peak": round(float(np.abs(a).max()), 4),
                              "seconds": round(time.time() - t, 1), "sample_rate": pipe.sample_rate}), flush=True)
        except Exception as e:  # report and keep serving
            print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}), flush=True)


if __name__ == "__main__":
    main()
