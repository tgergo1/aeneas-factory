"""A scoring worker: holds SigLIP and CLAP in its own process and exits after a while without work,
so their memory (torch, transformers, the weights; about 370 MB) really goes back to the system.
One JSON request per line on stdin, one JSON answer per line on stdout:

  {"op": "image", "paths": [...]}          -> {"ok": true, "vectors": [[...], ...]}
  {"op": "text", "texts": [...]}           -> {"ok": true, "vectors": [[...], ...]}
  {"op": "audio_scores", "paths": [...], "text": "..."} -> {"ok": true, "scores": [...]}
  {"op": "calibration"}                    -> {"ok": true, "scale": ..., "bias": ...}

Only this protocol is spoken; nothing in a request is evaluated as code."""
import json
import select
import sys


def main():
    idle = float(sys.argv[1]) if len(sys.argv) > 1 else 300.0
    from . import scoring as s
    print(json.dumps({"ready": True}), flush=True)
    while True:
        ready, _, _ = select.select([sys.stdin], [], [], idle)
        if not ready:
            return  # idle: exit, freeing everything
        line = sys.stdin.readline()
        if not line:
            return
        try:
            r = json.loads(line)
            op = r["op"]
            if op == "image":
                out = {"vectors": s._local_image_embeddings(r["paths"]).tolist()}
            elif op == "text":
                out = {"vectors": s._local_text_embeddings(r["texts"]).tolist()}
            elif op == "audio_scores":
                out = {"scores": s._local_audio_scores(r["paths"], r["text"])}
            elif op == "calibration":
                model, _ = s._siglip()
                out = {"scale": float(model.logit_scale.detach().exp()), "bias": float(model.logit_bias.detach())}
            else:
                raise ValueError(f"unknown op {op}")
            print(json.dumps({"ok": True, **out}), flush=True)
        except Exception as e:
            print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}), flush=True)


if __name__ == "__main__":
    main()
