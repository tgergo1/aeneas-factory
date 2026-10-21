// Client for the Aeneas Factory service (127.0.0.1, bearer token from ~/.aeneas/service.json).
// No VS Code imports here, so it can be tested in plain Node.
import { spawn } from "child_process";
import * as fs from "fs";
import * as http from "http";
import * as os from "os";
import * as path from "path";

export interface ServiceInfo {
  port: number;
  token: string;
  pid?: number;
  version?: string;
  root?: string;
}

export interface Health {
  ok: boolean;
  version: string;
  pid: number;
  queued: number;
  running?: number;
  idle_seconds: number;
  idle_exit_minutes: number;
  models_loaded: string[];
}

export type JobStatus = "queued" | "running" | "done" | "failed" | "cancelled";

export interface Job {
  id: string;
  kind: "op" | "recipe";
  spec: { op?: string; recipe?: string; args?: Record<string, unknown>; inputs?: Record<string, unknown>; out_dir?: string };
  status: JobStatus;
  progress: number;
  message: string;
  created: number;
  started: number | null;
  finished: number | null;
  result: Record<string, any> | null;
  error: string | null;
}

export interface LibraryEntry {
  id: number;
  path: string;
  project: string;
  kind: string;
  bytes: number;
  added: string;
  origin: "generated" | "downloaded";
  prompt: string | null;
  licence: string | null;
  source: string | null;
  url: string | null;
  author: string | null;
  tags: string | null;
}

export interface Capabilities {
  operations: string[];
  recipes: Record<string, { description: string; inputs: Record<string, string> }>;
  styles: Record<string, unknown> | string[];
}

export class ServiceError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
  }
}

export function stateDir(env: NodeJS.ProcessEnv = process.env): string {
  return env.AEN_STATE ? env.AEN_STATE.replace(/^~(?=$|\/)/, os.homedir()) : path.join(os.homedir(), ".aeneas");
}

export function readInfo(dir = stateDir()): ServiceInfo | undefined {
  try {
    const info = JSON.parse(fs.readFileSync(path.join(dir, "service.json"), "utf8"));
    return typeof info.port === "number" && typeof info.token === "string" ? info : undefined;
  } catch {
    return undefined;
  }
}

/** The factory checkout: the setting, else where the service runs from, else `aen` on the PATH. */
export function findFactory(setting: string | undefined, info: ServiceInfo | null | undefined = readInfo(), envPath = process.env.PATH ?? ""): string | undefined {
  const candidates: string[] = [];
  if (setting) candidates.push(setting.replace(/^~(?=$|\/)/, os.homedir()));
  if (info?.root) candidates.push(info.root);
  for (const dir of envPath.split(path.delimiter)) {
    const aen = path.join(dir, process.platform === "win32" ? "aen.cmd" : "aen");
    try {
      candidates.push(path.dirname(path.dirname(fs.realpathSync(aen))));
    } catch {
      /* not here */
    }
  }
  return candidates.find((c) => fs.existsSync(path.join(c, "bin", "aen")));
}

export class Client {
  constructor(readonly info: ServiceInfo) {}

  request<T>(method: "GET" | "POST", route: string, body?: unknown, timeoutMs = 150_000): Promise<T> {
    const data = body === undefined ? undefined : Buffer.from(JSON.stringify(body));
    return new Promise<T>((resolve, reject) => {
      // No Origin header: the service refuses anything that looks like a browser.
      const req = http.request(
        {
          host: "127.0.0.1",
          port: this.info.port,
          path: route,
          method,
          headers: {
            Authorization: `Bearer ${this.info.token}`,
            "Content-Type": "application/json",
            ...(data ? { "Content-Length": data.length } : {}),
          },
          timeout: timeoutMs,
        },
        (res) => {
          const chunks: Buffer[] = [];
          res.on("data", (c) => chunks.push(c));
          res.on("end", () => {
            const text = Buffer.concat(chunks).toString("utf8");
            let parsed: any;
            try {
              parsed = text ? JSON.parse(text) : {};
            } catch {
              return reject(new ServiceError(`the service answered with something that is not JSON (${res.statusCode})`));
            }
            if ((res.statusCode ?? 500) >= 400) {
              return reject(new ServiceError(parsed?.error ?? `HTTP ${res.statusCode}`, res.statusCode));
            }
            resolve(parsed as T);
          });
        },
      );
      req.on("timeout", () => req.destroy(new ServiceError("the service did not answer in time")));
      req.on("error", (e) => reject(e instanceof ServiceError ? e : new ServiceError(`the service is not reachable: ${e.message}`)));
      if (data) req.write(data);
      req.end();
    });
  }

  health(): Promise<Health> {
    return this.request("GET", "/health", undefined, 3000);
  }

  jobs(limit = 20): Promise<Job[]> {
    return this.request("GET", `/jobs?limit=${limit}`);
  }

  job(id: string, waitSeconds = 0): Promise<Job> {
    return this.request("GET", `/jobs/${encodeURIComponent(id)}?wait=${waitSeconds}`, undefined, (waitSeconds + 30) * 1000);
  }

  submitOp(op: string, args: Record<string, unknown>, options: { library?: boolean } = {}): Promise<Job> {
    const clean = Object.fromEntries(Object.entries(args).filter(([, v]) => v !== undefined && v !== null && v !== ""));
    const spec: Record<string, unknown> = { op, args: clean };
    if (options.library === false) spec.library = false;
    return this.request("POST", "/jobs", { kind: "op", spec });
  }

  submitRecipe(recipe: string, inputs: Record<string, unknown>, outDir: string): Promise<Job> {
    return this.request("POST", "/jobs", { kind: "recipe", spec: { recipe, inputs, out_dir: outDir } });
  }

  cancel(id: string): Promise<Job> {
    return this.request("POST", `/jobs/${encodeURIComponent(id)}/cancel`, {});
  }

  capabilities(project?: string): Promise<Capabilities> {
    return this.request("GET", `/capabilities${project ? `?project=${encodeURIComponent(project)}` : ""}`);
  }

  library(query: { q?: string; kind?: string; licence?: string; project?: string; origin?: string; limit?: number }): Promise<LibraryEntry[]> {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(query)) if (v !== undefined && v !== "") params.set(k, String(v));
    return this.request("GET", `/library?${params}`);
  }

  /** Wait until a job finishes, calling onUpdate as it moves. */
  async wait(id: string, onUpdate?: (job: Job) => void, isCancelled?: () => boolean): Promise<Job> {
    for (;;) {
      const job = await this.job(id, 2);
      onUpdate?.(job);
      if (job.status === "done" || job.status === "failed" || job.status === "cancelled") return job;
      if (isCancelled?.()) {
        await this.cancel(id);
      }
    }
  }
}

/** The factory's own Python (its .venv), which runs `python -m aeneas ...` on every OS. */
export function factoryPython(factory: string, platform = process.platform): string {
  return platform === "win32" ? path.join(factory, ".venv", "Scripts", "python.exe") : path.join(factory, ".venv", "bin", "python");
}

/** A client for the running service, or undefined when it is not running. */
export async function connect(dir = stateDir()): Promise<Client | undefined> {
  const info = readInfo(dir);
  if (!info) return undefined;
  const client = new Client(info);
  try {
    await client.health();
    return client;
  } catch {
    return undefined;
  }
}

/** Connect, starting the service with `aen service start` when it is not running. */
export async function ensureRunning(factory: string | undefined, dir = stateDir(), waitMs = 40_000): Promise<Client> {
  const running = await connect(dir);
  if (running) return running;
  if (!factory) {
    throw new ServiceError("The factory service is not running and the factory was not found. Set aeneas.factoryPath to your aeneas-factory folder.");
  }
  const child = spawn(factoryPython(factory), ["-m", "aeneas", "service", "start"], { cwd: factory, detached: true, stdio: "ignore", windowsHide: true });
  child.unref();
  const until = Date.now() + waitMs;
  while (Date.now() < until) {
    await new Promise((r) => setTimeout(r, 500));
    const c = await connect(dir);
    if (c) return c;
  }
  throw new ServiceError(`The factory service did not start; see ${path.join(dir, "service.log")}`);
}

/** True when version a is older than b ("0.3.0" < "0.4.0"; anything after the numbers is ignored). */
export function olderThan(a: string, b: string): boolean {
  const parts = (v: string) => (v.match(/^\d+(\.\d+)*/)?.[0] ?? "0").split(".").map(Number);
  const x = parts(a), y = parts(b);
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    if ((x[i] ?? 0) !== (y[i] ?? 0)) return (x[i] ?? 0) < (y[i] ?? 0);
  }
  return false;
}
