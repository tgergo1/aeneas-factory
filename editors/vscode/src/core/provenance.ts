// Finding and reading the provenance record of an asset (<file>.json beside it).
import * as fs from "fs";
import * as path from "path";
import { renderTarget } from "./outputs";

export interface ModelLine {
  id: string;
  name: string;
  licence: string;
  commercial: string;
  attribution?: string;
  upstream?: string;
}

export interface Summary {
  file: string;
  recordPath: string;
  madeWith: string;
  created?: string;
  seconds?: number;
  prompt?: string;
  negative?: string;
  seed?: number | null;
  params: Array<[string, string]>;
  models: ModelLine[];
  inputs: string[];
  checks: Array<[string, string]>;
  policy?: string;
  source?: string;
  selection?: string;
  versions: Array<[string, string]>;
  credits: string[];
  verified?: boolean;
}

export function isRecord(value: unknown): value is Record<string, any> {
  return !!value && typeof value === "object" && typeof (value as any).generated_by === "string";
}

/** The record for a file: its sidecar, the file itself when it is a record, or the record of what a source renders to. */
export function recordFor(file: string): string | undefined {
  const candidates = [file + ".json"];
  if (file.toLowerCase().endsWith(".json")) candidates.push(file);
  const target = renderTarget(file, "");
  if (target) candidates.push(target.out + ".json");
  for (const c of candidates) {
    try {
      if (isRecord(JSON.parse(fs.readFileSync(c, "utf8")))) return c;
    } catch {
      /* no record there */
    }
  }
  return undefined;
}

function show(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export function summarize(recordPath: string, sha256?: (file: string) => string | undefined): Summary {
  const r = JSON.parse(fs.readFileSync(recordPath, "utf8"));
  if (!isRecord(r)) throw new Error(`${path.basename(recordPath)} is not a provenance record`);
  const file = path.join(path.dirname(recordPath), r.output ?? path.basename(recordPath, ".json"));
  const models: ModelLine[] = (r.models ?? []).map((m: any) => ({
    id: m.id,
    name: m.name ?? m.id,
    licence: m.licence ?? "",
    commercial: show(m.licence_allows_commercial_use ?? m.commercial_output),
    attribution: m.attribution_required,
    upstream: m.upstream,
  }));
  const credits = models.filter((m) => m.attribution).map((m) => `${m.attribution} (${m.name})`);
  const sel = r.selection;
  let verified: boolean | undefined;
  if (r.output_sha256 && sha256) {
    const actual = sha256(file);
    if (actual) verified = actual === r.output_sha256;
  }
  return {
    file,
    recordPath,
    madeWith: String(r.generated_by).replace(/^aeneas-factory\s*/, "") || "aeneas-factory",
    created: r.created,
    seconds: r.seconds,
    prompt: r.prompt ?? undefined,
    negative: r.negative_prompt ?? undefined,
    seed: r.seed,
    params: Object.entries(r.params ?? {}).filter(([, v]) => v !== null && v !== undefined).map(([k, v]) => [k, show(v)]),
    models,
    inputs: (r.inputs ?? []).map((i: any) => i.file ?? show(i)),
    checks: Object.entries(r.checks ?? {}).map(([k, v]) => [k, show(v)]),
    policy: r.policy ? (typeof r.policy === "string" ? r.policy : typeof r.policy.policy === "string" && Object.keys(r.policy).length === 1 ? r.policy.policy : JSON.stringify(r.policy)) : undefined,
    source: typeof r.source === "string" ? r.source : undefined,
    selection: sel ? `best of ${sel.candidates} (${sel.passed_checks} passed checks)${sel.ranked_by ? `, ranked by ${sel.ranked_by}` : ""}` : undefined,
    versions: Object.entries(r.versions ?? {}).map(([k, v]) => [k, show(v)]),
    credits,
    verified,
  };
}

/** The operation to make another like this one, when the record says enough to do it. */
export function remakeSpec(s: Summary): { op: string; args: Record<string, unknown> } | undefined {
  if (!s.prompt) return undefined;
  const params = Object.fromEntries(s.params);
  const tool = s.madeWith.replace(/^bin\/ai-/, "");
  const stem = path.parse(s.file).name.replace(/-v\d{6}$/, "");
  const stamp = new Date().toTimeString().slice(0, 8).replace(/:/g, "");
  const out = (ext: string) => path.join(path.dirname(s.file), `${stem}-v${stamp}${ext}`);
  if (tool === "image" || tool === "texture") {
    if (params.tile === "true") return { op: "texture", args: { prompt: s.prompt, out: out(".png"), size: Number(params.width) || undefined } };
    const model = s.models.find((m) => m.id === "z-image-turbo" || m.id === "flux2-klein-4b")?.id;
    return { op: "image", args: { prompt: s.prompt, model, negative: s.negative, size: Number(params.width) || undefined, out: out(".png") } };
  }
  if (tool === "sfx") return { op: "sfx", args: { prompt: s.prompt, seconds: Number(params.seconds) || undefined, out: out(".wav") } };
  return undefined;
}
