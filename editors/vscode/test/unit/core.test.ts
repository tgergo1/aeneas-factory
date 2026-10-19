import * as assert from "assert";
import * as fs from "fs";
import * as http from "http";
import { AddressInfo } from "net";
import * as os from "os";
import * as path from "path";
import { blenderArgs } from "../../src/core/blender";
import { jobTitle, resultFile } from "../../src/core/jobs";
import { errorLine, outputPath, problemText, renderTarget, slug } from "../../src/core/outputs";
import { recordFor, remakeSpec, summarize } from "../../src/core/provenance";
import { Client, findFactory, Job, olderThan, readInfo, ServiceError } from "../../src/core/service";

const REPO = path.resolve(__dirname, "../../../../..");
const GALLERY = path.join(REPO, "docs", "gallery");

suite("outputs", () => {
  test("paths follow the MCP server's layout", () => {
    const at = new Date(2026, 9, 19, 9, 5, 7);
    assert.strictEqual(outputPath("image", "/p", "A Lighthouse, at dawn!", "generated", at), "/p/generated/images/a-lighthouse-at-dawn-090507.png");
    assert.strictEqual(outputPath("model3d", "/p", "chest", "out", at), "/p/out/models/chest-090507.glb");
    assert.strictEqual(slug("!!!", "image"), "image");
    assert.ok(slug("x".repeat(80), "f").length <= 40);
  });

  test("sources render next to themselves", () => {
    assert.deepStrictEqual(renderTarget("/a/flow.d2", "x")?.args, { source: "x", kind: "d2", out: "/a/flow.png" });
    assert.strictEqual(renderTarget("/a/g.gv", "")?.args.kind, "graphviz");
    assert.strictEqual(renderTarget("/a/chart.vl.json", "")?.out, "/a/chart.png");
    assert.strictEqual(renderTarget("/a/icon.svg", "")?.op, "svg");
    assert.strictEqual(renderTarget("/a/tune.abc", "")?.out, "/a/tune.wav");
    assert.strictEqual(renderTarget("/a/story.ink", "")?.out, "/a/story.json");
    assert.strictEqual(renderTarget("/a/story.yarn", "")?.out, "/a/story.yarnc");
    assert.strictEqual(renderTarget("/a/data.json", ""), undefined);
    assert.strictEqual(renderTarget("/a/notes.md", ""), undefined);
  });

  test("error lines from the tools' messages", () => {
    assert.strictEqual(errorLine("Error: syntax error in line 3 near '->'"), 2);
    assert.strictEqual(errorLine("err: /x/flow.d2:7:12: unexpected text"), 6);
    assert.strictEqual(errorLine("something else"), undefined);
  });

  test("problem messages carry the tool's words and the user's file name", () => {
    const err = "EngineError: dot failed (exit 1). End of ~/w/broken.png.log:\n\nError: /Users/x/w/tmp1cvvtrjj/diagram.dot: syntax error in line 3 near '->'";
    assert.strictEqual(problemText(err, "broken.dot"), "Error: broken.dot: syntax error in line 3 near '->'");
    assert.strictEqual(problemText("TypeError: oops", "a.d2"), "oops");
  });
});

suite("provenance", () => {
  test("finds the record beside a file, of a source's render, or the record itself", () => {
    assert.strictEqual(recordFor(path.join(GALLERY, "chest.png")), path.join(GALLERY, "chest.png.json"));
    assert.strictEqual(recordFor(path.join(GALLERY, "chest.png.json")), path.join(GALLERY, "chest.png.json"));
    assert.strictEqual(recordFor(path.join(GALLERY, "explicit", "tavern.abc")), path.join(GALLERY, "explicit", "tavern.wav.json"));
    assert.strictEqual(recordFor(path.join(GALLERY, "explicit", "chest-pixel.png")), undefined);
  });

  test("summarises a generated image, a 3D model and a written tune", () => {
    const img = summarize(path.join(GALLERY, "chest.png.json"));
    assert.strictEqual(img.madeWith, "bin/ai-image");
    assert.strictEqual(img.seed, 11);
    assert.strictEqual(img.models[0].licence, "Apache-2.0");
    const glb = summarize(path.join(GALLERY, "chest.glb.json"));
    assert.ok(glb.models[0].licence.includes("DINOv3"));
    const tune = summarize(path.join(GALLERY, "explicit", "tavern.wav.json"));
    assert.ok(tune.source?.includes("The Brass Lock"));
    assert.ok(tune.checks.some(([k]) => k === "rms_dbfs"));
    assert.strictEqual(tune.policy, "none (no .aeneas/policy.toml in the project)");
  });

  test("checks the file against its recorded checksum", () => {
    const sha = (f: string) => require("crypto").createHash("sha256").update(fs.readFileSync(f)).digest("hex");
    assert.strictEqual(summarize(path.join(GALLERY, "explicit", "potion.png.json"), sha).verified, true);
    assert.strictEqual(summarize(path.join(GALLERY, "explicit", "potion.png.json"), () => "0").verified, false);
  });

  test("makes another image with the same prompt and model, beside the first", () => {
    const spec = remakeSpec(summarize(path.join(GALLERY, "chest.png.json")))!;
    assert.strictEqual(spec.op, "image");
    assert.strictEqual(spec.args.model, "z-image-turbo");
    assert.strictEqual(spec.args.size, 1024);
    assert.match(String(spec.args.out), /docs\/gallery\/chest-v\d{6}\.png$/);
    assert.strictEqual(remakeSpec(summarize(path.join(GALLERY, "explicit", "tavern.wav.json"))), undefined);
  });
});

suite("jobs", () => {
  const job = (spec: Job["spec"], result: Job["result"] = null): Job =>
    ({ id: "1", kind: spec.recipe ? "recipe" : "op", spec, status: "done", progress: 1, message: "", created: 0, started: 0, finished: 0, result, error: null });

  test("names a job by what it makes", () => {
    assert.strictEqual(jobTitle(job({ op: "image", args: { prompt: "a red door" } })), "image “a red door”");
    assert.strictEqual(jobTitle(job({ op: "upscale", args: { src: "/a/b/c.png" } })), "upscale c.png");
    assert.ok(jobTitle(job({ op: "sfx", args: { prompt: "x".repeat(80) } })).endsWith("…”"));
  });

  test("finds the result of an operation and of a recipe", () => {
    assert.strictEqual(resultFile(job({ op: "image" }, { path: "/a.png" })), "/a.png");
    assert.strictEqual(resultFile(job({ recipe: "prop" }, { manifest: "/m.json" })), "/m.json");
    assert.strictEqual(resultFile(job({ op: "image" })), undefined);
  });
});

suite("blender", () => {
  test("opens .blend files and imports everything else, with the path outside the script", () => {
    assert.deepStrictEqual(blenderArgs("/a/scene.blend"), ["/a/scene.blend"]);
    const args = blenderArgs("/a/it's.glb");
    assert.strictEqual(args[0], "--python-expr");
    assert.ok(!args[1].includes("it's"));
    assert.deepStrictEqual(args.slice(2), ["--", "/a/it's.glb"]);
  });
});

suite("service client", () => {
  let server: http.Server;
  let seen: http.IncomingHttpHeaders[] = [];
  let client: Client;

  suiteSetup(async () => {
    server = http.createServer((req, res) => {
      seen.push(req.headers);
      let body = "";
      req.on("data", (c) => (body += c));
      req.on("end", () => {
        res.setHeader("Content-Type", "application/json");
        if (req.headers.authorization !== "Bearer t0k") {
          res.statusCode = 401;
          return res.end(JSON.stringify({ error: "missing or wrong token" }));
        }
        if (req.url === "/jobs" && req.method === "POST") return res.end(JSON.stringify({ id: "j1", status: "queued", echo: JSON.parse(body) }));
        if (req.url?.startsWith("/jobs/j1")) return res.end(JSON.stringify({ id: "j1", status: "done", result: { path: "/x.png" } }));
        if (req.url?.startsWith("/library")) return res.end(JSON.stringify([{ path: "/x.png", url: req.url }]));
        res.statusCode = 400;
        res.end(JSON.stringify({ error: "ValueError: out must be a path under your home folder, outside the factory" }));
      });
    });
    await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
    client = new Client({ port: (server.address() as AddressInfo).port, token: "t0k" });
  });
  suiteTeardown(() => server.close());

  test("sends the token and never an Origin header", async () => {
    seen = [];
    await client.library({ q: "mossy stone", kind: "", licence: "CC0" });
    assert.strictEqual(seen[0].authorization, "Bearer t0k");
    assert.strictEqual(seen[0].origin, undefined);
  });

  test("drops empty arguments and passes library: false", async () => {
    const job: any = await client.submitOp("diagram", { source: "a->b", kind: "d2", out: "/o.png", width: undefined, model: "" }, { library: false });
    assert.deepStrictEqual(job.echo, { kind: "op", spec: { op: "diagram", args: { source: "a->b", kind: "d2", out: "/o.png" }, library: false } });
  });

  test("encodes library queries", async () => {
    const rows: any = await client.library({ q: "mossy stone", licence: "CC0" });
    assert.strictEqual(rows[0].url, "/library?q=mossy+stone&licence=CC0");
  });

  test("waits for a job to finish", async () => {
    const seenStatus: string[] = [];
    const done = await client.wait("j1", (j) => seenStatus.push(j.status));
    assert.strictEqual(done.status, "done");
    assert.deepStrictEqual(seenStatus, ["done"]);
  });

  test("turns refusals into readable errors", async () => {
    await assert.rejects(client.request("GET", "/nope"), (e: any) => e instanceof ServiceError && e.status === 400 && /under your home folder/.test(e.message));
    await assert.rejects(new Client({ port: client.info.port, token: "wrong" }).health(), /wrong token/);
  });

  test("reports a service that is not there", async () => {
    await assert.rejects(new Client({ port: 1, token: "x" }).health(), /not reachable/);
  });
});

suite("finding the factory", () => {
  test("from the setting, then the service's record, then aen on the PATH", () => {
    const tmp = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "aen-")));
    const fake = path.join(tmp, "factory");
    fs.mkdirSync(path.join(fake, "bin"), { recursive: true });
    fs.writeFileSync(path.join(fake, "bin", "aen"), "");
    fs.writeFileSync(path.join(tmp, "service.json"), JSON.stringify({ port: 1, token: "t", root: fake }));
    assert.strictEqual(findFactory(fake, null, ""), fake);
    assert.strictEqual(findFactory("", readInfo(tmp), ""), fake);
    assert.strictEqual(findFactory("", null, path.join(fake, "bin")), fake);
    assert.strictEqual(findFactory("/nowhere", null, ""), undefined);
    fs.rmSync(tmp, { recursive: true });
  });
});

suite("versions", () => {
  test("compares factory versions", () => {
    assert.ok(olderThan("0.3.0", "0.4.0"));
    assert.ok(olderThan("0.3.9", "0.4"));
    assert.ok(!olderThan("0.4.0", "0.4.0"));
    assert.ok(!olderThan("0.10.0", "0.4.0"));
    assert.ok(!olderThan("1.0.0rc1", "0.4.0"));
    assert.ok(olderThan("", "0.4.0"));
  });
});
