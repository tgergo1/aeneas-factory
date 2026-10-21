# Aeneas Factory for VS Code

Make, preview and trace game and media assets without leaving the editor. The extension is a thin client of the [Aeneas Factory](https://github.com/tgergo1/aeneas-factory) service on your Mac: generation, checks, provenance and the asset library all stay in the factory, so the editor, the command line and AI agents (over MCP) share one queue, one library and one set of records.

**It needs [Aeneas Factory](https://github.com/tgergo1/aeneas-factory) 0.5 or later installed** (macOS, Linux or Windows); without the factory it can do nothing. It works in VS Code 1.95 or later, Cursor, Windsurf and VSCodium. This is a preview: expect changes.

## What it adds

| | |
|---|---|
| **Live preview** | Save a diagram (`.dot`, `.gv`, `.d2`, `.mmd`, `.vl.json`), an SVG, ABC music, or Ink or Yarn dialogue: it is rendered next to its source in about a second and shown beside the editor. The service runs these on their own lane, so a preview never waits behind a 3D job. Rendering errors appear in Problems on the line the tool names |
| **3D viewer** | `.glb` files open in a three.js viewer: orbit, wireframe, a 1 m grid, triangle and texture counts, and the model's real size. Meshopt-compressed files (`gltfpack -cc`) open too |
| **Audio viewer** | `.wav` files open with their waveform, play and loop, sample rate, peak and RMS level |
| **Provenance** | A side view that follows the active file and shows its record: models and licences, the credit a licence requires, prompt, seed, settings, checks passed, the licence policy, and whether the file still matches its recorded checksum. For written sources it shows the source. "Make another" queues the same prompt with a new seed |
| **Library** | Search everything generated and every imported pack, by words and (for images) by meaning, filtered by kind, licence, origin and project, with thumbnails |
| **Generate** | Commands for images, edits, seamless textures, 3D from an image, sound effects, speech, upscaling, background removal and recipes. Results go to `generated/<kind>/` in the workspace, as the MCP server does |
| **Jobs** | Every queued and running job with progress and cancel, and a status bar item; you are told when your results are ready |
| **Hand-off** | Open a model in Blender (imported into an empty scene), an image in GIMP, a project in Godot; write `CREDITS.md` from the library |

## Setting up

1. Install the factory (`make install` in the repository) and start its service once (`aen service start`, or `aen service autostart on` to start it at login).
2. Install the extension: search for **Aeneas Factory** in the Extensions view (the VS Code Marketplace, or Open VSX in Cursor, Windsurf and VSCodium), or download `aeneas-factory-<version>.vsix` from the [releases](https://github.com/tgergo1/aeneas-factory/releases) and run **Extensions: Install from VSIX…**. From a clone of the factory, `make vscode-install` builds and installs it.
3. Open a folder under your home folder (the factory writes only there) and press the Aeneas icon in the activity bar.

The extension finds the service through `~/.aeneas/service.json` and starts it when needed. If it cannot find the factory, set **Aeneas: Factory Path** to the repository folder.

## Settings

| Setting | Default | |
|---|---|---|
| `aeneas.factoryPath` | empty | The factory checkout; empty means: where the running service lives, then `aen` on the `PATH` |
| `aeneas.renderOnSave` | `true` | Render sources when they are saved |
| `aeneas.outputFolder` | `generated` | Where generated files go in the workspace |

## Security

Webviews never talk to the service: they send messages to the extension, which checks them (a webview may only open files it was shown) before acting. Every page has a strict content security policy with per-page script nonces; only the 3D viewer may run WebAssembly, for the meshopt decoder. The extension talks to the service on 127.0.0.1 with the token from `~/.aeneas/service.json` and never sends an `Origin` header; the service refuses browsers. Blender receives a file's path as an argument, never inside the script it runs.

Live previews do not add to the asset library; **Aeneas: Render Source to Asset** does.

## Development

```bash
npm ci
npm test              # unit tests, then the integration tests in a real VS Code (a throwaway profile)
npm run tour -- DIR   # a step-by-step tour of the views over DIR, for screenshots (touch the printed file to step)
npm run package       # aeneas-factory.vsix (one package for every OS)
```

Releases: bump `version` in `package.json`, commit, and push a tag `vscode-v<version>`. [The release workflow](../../.github/workflows/release-vscode.yml) runs on the owner's self-hosted Linux runner (no GitHub-hosted runners): it checks the tag against the version, runs the unit tests, packages the extension, attaches the `.vsix` to a GitHub release, and publishes it to the VS Code Marketplace and Open VSX when the repository has the secrets `VSCE_PAT` and `OVSX_PAT`. By hand: `npm run package`, then `gh release create vscode-v<version> aeneas-factory.vsix --prerelease`.

The integration tests use the installed VS Code (or download one, also with `AEN_VSCODE=download`) and the running factory service, and work in a temporary folder under `~/.aeneas`. On Linux without a display run them under a virtual one: `xvfb-run -a npm test`.

## Licence

MIT, like the factory. The 3D viewer bundles three.js and the meshoptimizer decoder (both MIT); see [THIRD_PARTY.md](THIRD_PARTY.md).
