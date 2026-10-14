# Aeneas Factory: notes for AI agents

For Claude Code, Codex or any agent asked to make images, textures, 3D models, sound effects or other content on a machine with this factory installed.

## Generate with the commands in `bin/`

| Need | Command | Model |
|---|---|---|
| Image from text | `bin/ai-image "<prompt>" -o out.png` | Z-Image Turbo (default) or `--model flux2-klein-4b` |
| Edit an image | `bin/ai-image "<what to change>" --model flux2-klein-4b --ref in.png -o out.png` | FLUX.2 [klein] 4B |
| Seamless texture | `bin/ai-image "<surface>" --tile --size 512 -o tile.png` | Z-Image Turbo |
| Restyle a photo | `bin/ai-image "<style>" --init photo.png --strength 0.4 -o out.png` | Z-Image Turbo |
| 3D model from one image | `bin/ai-3d object.png -o object.glb` (`--res 512` is lighter) | TRELLIS.2 4B |
| Sound effect | `bin/ai-sfx "<description>" --seconds 5 -o out.wav` | MOSS-SoundEffect v2.0 |

- Run `bin/ai-models list` to see what is downloaded and `bin/ai-check --quick` if something fails.
- Every command writes `<output>.json` next to its output. Keep it with the file: it records the models, their licences, the prompt, the seed and the exact command.
- Pass `--seed` when the result must be reproducible.
- For 3D, describe one object on a plain white background in the image prompt. Generate the image first, then `ai-3d` it.
- Do not download a second copy of a model that `models.json` already lists. A model several projects could use belongs in this factory's register, not inside a project.

## Prefer the right tool over a workaround

An editor or an existing free asset often beats drawing something in code or generating it from nothing. Combine them: a generated concept image as a modelling reference in Blender, a Poly Haven texture cleaned up in GIMP, a generated sound trimmed with ffmpeg.

| Tool | Use it for |
|---|---|
| Blender (`/Applications/Blender.app/Contents/MacOS/Blender -b --python script.py`) | Modelling, retopology, UVs, baking, rigging, animation, rendering, converting glTF, FBX, OBJ, USD. `scripts/render_glb.py` renders a `.glb` preview |
| GIMP (`/Applications/GIMP.app/Contents/MacOS/gimp-console` for batch work) | Retouching, masks, tiling, sprite sheets, icons |
| ffmpeg | Cutting, encoding and converting video and audio |

## Free sources to look in first

Check each asset's own licence on its page; several sites mix licences.

| Source | What | Usual licence |
|---|---|---|
| [Inside Out Library](https://insideoutlibrary.com/) | Over 1.8 million historical illustrations, diagrams and ornaments from old books | The site says free to use for anything; still record the source book |
| [Poly Haven](https://polyhaven.com/) | HDRIs, PBR textures, 3D models | CC0 |
| [ambientCG](https://ambientcg.com/) | PBR textures and materials | CC0 |
| [Kenney](https://kenney.nl/) | Game kits (3D, 2D, UI), sound packs | CC0 |
| [OpenGameArt](https://opengameart.org/) | Sprites, models, music, sound | Mixed: CC0, CC BY, CC BY-SA, GPL |
| [Wikimedia Commons](https://commons.wikimedia.org/) | Photos, scans, illustrations, audio | Per file |
| [Sketchfab](https://sketchfab.com/) | 3D models (filter to downloadable) | Per model, often CC BY 4.0 |
| [Fab](https://www.fab.com/) | Epic's store, including Quixel Megascans | Per listing |
| [Mixamo](https://www.mixamo.com/) | Rigged characters and motion capture | Adobe terms: royalty-free |
| [MakeHuman](https://www.makehumancommunity.org/) | Human base meshes, clothing, hair | Mostly CC0 |
| [Pexels](https://www.pexels.com/) | Stock photos and video | Pexels licence |
| [Google Fonts](https://fonts.google.com/) | Fonts | OFL or Apache-2.0 |
| [LibriVox](https://librivox.org/) | Public-domain audiobook recordings | Public domain |
| [CMU Motion Capture](http://mocap.cs.cmu.edu/) | Motion capture clips (BVH) | Free for any use |
| [MuJoCo Menagerie](https://github.com/google-deepmind/mujoco_menagerie) | Robot models | Per model, often BSD-3-Clause or Apache-2.0 |

## Rules

- **Record every asset.** Title, author, source URL, licence and date go in the project's credits file. For generated content, the sidecar already holds the model, licence, prompt and date.
- **Check commercial use** before anything ships or is shown publicly. Prefer CC0 and other permissive licences; treat CC BY-SA, GPL and non-commercial as the owner's decision. TRELLIS.2's `dinov3.gguf` is under Meta's DINOv3 License: read it before shipping 3D models.
- **Credit what requires credit** (CC BY and similar) wherever the work is shown.
- **Ask the owner before** buying anything, creating an account or signing in to a store.
- **Project rules win.** A project's own instructions may forbid sources or require stricter licences.
