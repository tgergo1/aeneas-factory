// How jobs are named and where their results are.
import * as path from "path";
import { Job } from "./service";

export function jobTitle(job: Job): string {
  const what = job.spec.op ?? job.spec.recipe ?? job.kind;
  const args = job.spec.args ?? job.spec.inputs ?? {};
  const text = (args as any).prompt ?? (args as any).text ?? (args as any).subject ?? "";
  const out = (args as any).out ?? (args as any).src ?? job.spec.out_dir ?? "";
  const label = text ? `“${String(text).slice(0, 48)}${String(text).length > 48 ? "…" : ""}”` : out ? path.basename(String(out)) : "";
  return `${what}${label ? " " + label : ""}`;
}

export function resultFile(job: Job): string | undefined {
  const r = job.result;
  if (!r) return undefined;
  if (typeof r.path === "string") return r.path;
  // a recipe: its manifest lists the steps; open the last step's main file
  const steps = r.steps ?? r.results;
  if (steps && typeof steps === "object") {
    const last = Object.values(steps).reverse().find((s: any) => s && typeof s.path === "string") as any;
    if (last) return last.path;
  }
  return typeof r.manifest === "string" ? r.manifest : undefined;
}
