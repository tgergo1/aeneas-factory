// Where results go, and which sources render to which assets. Mirrors aeneas/mcp_server.py so the
// editor and agents put files in the same places.
import * as path from "path";

export const EXT: Record<string, string> = {
  image: ".png", edit: ".png", texture: ".png", upscale: ".png", model3d: ".glb", sfx: ".wav", speech: ".wav",
  matte: ".png", comfy_image: ".png", diagram: ".png", svg: ".png", music: ".wav", dialogue: ".json",
};

export const SUBDIR: Record<string, string> = {
  image: "images", edit: "images", texture: "textures", upscale: "images", model3d: "models", sfx: "sounds",
  speech: "speech", matte: "images", comfy_image: "images", diagram: "diagrams", svg: "images", music: "music",
  dialogue: "dialogue",
};

export function slug(text: string, fallback: string): string {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40).replace(/-+$/, "") || fallback;
}

function stamp(now: Date): string {
  return [now.getHours(), now.getMinutes(), now.getSeconds()].map((n) => String(n).padStart(2, "0")).join("");
}

/** <project>/<outputFolder>/<kind>/<slug-of-hint>-HHMMSS.<ext> */
export function outputPath(op: string, project: string, hint: string, outputFolder = "generated", now = new Date()): string {
  const dir = path.join(project, outputFolder, SUBDIR[op] ?? "other");
  return path.join(dir, `${slug(hint, op)}-${stamp(now)}${EXT[op] ?? ""}`);
}

export interface RenderTarget {
  op: "diagram" | "svg" | "music" | "dialogue";
  args: Record<string, unknown>;
  out: string;
  /** What the preview shows: the output itself, or a picture of it (a waveform). */
  kind: "image" | "audio" | "dialogue";
}

const DIAGRAM_KINDS: Record<string, string> = { ".dot": "graphviz", ".gv": "graphviz", ".d2": "d2", ".mmd": "mermaid" };

/** The render for a source file, or undefined when it is not a source the factory renders. */
export function renderTarget(file: string, source: string): RenderTarget | undefined {
  const lower = file.toLowerCase();
  const ext = path.extname(lower);
  const beside = (suffix: string, strip = ext.length) => file.slice(0, file.length - strip) + suffix;
  if (lower.endsWith(".vl.json")) {
    const out = beside(".png", ".vl.json".length);
    return { op: "diagram", args: { source, kind: "vega-lite", out }, out, kind: "image" };
  }
  if (DIAGRAM_KINDS[ext]) {
    const out = beside(".png");
    return { op: "diagram", args: { source, kind: DIAGRAM_KINDS[ext], out }, out, kind: "image" };
  }
  if (ext === ".svg") {
    const out = beside(".png");
    return { op: "svg", args: { source, out }, out, kind: "image" };
  }
  if (ext === ".abc") {
    const out = beside(".wav");
    return { op: "music", args: { source, format: "abc", out }, out, kind: "audio" };
  }
  if (ext === ".ink") {
    const out = beside(".json");
    return { op: "dialogue", args: { source, kind: "ink", out }, out, kind: "dialogue" };
  }
  if (ext === ".yarn") {
    const out = beside(".yarnc");
    return { op: "dialogue", args: { source, kind: "yarn", out }, out, kind: "dialogue" };
  }
  return undefined;
}

export function isRenderable(file: string): boolean {
  return renderTarget(file, "") !== undefined;
}

/** A line number from a tool's error message (Graphviz "in line 3", D2 "file.d2:3:5", Ink "line 3"). */
export function errorLine(message: string): number | undefined {
  const m = message.match(/:(\d+):\d+:/) ?? message.match(/\bline (\d+)/i);
  return m ? Math.max(0, Number(m[1]) - 1) : undefined;
}

/** A tool failure as a short problem message: the tool's own last words, naming the user's file rather
 * than the factory's temporary copy of it. */
export function problemText(error: string, sourceName: string): string {
  const lines = error.split("\n").slice(1).map((l) => l.trim()).filter((l) => l && !l.startsWith("$ "));
  const words = (lines.length ? lines.slice(-3) : [error.replace(/^\w+Error: /, "")]).join(" ");
  return words.replace(/\/?[^\s:'"]*\/tmp[\w-]{6,}\/[^\s:'"]+/g, sourceName);
}
