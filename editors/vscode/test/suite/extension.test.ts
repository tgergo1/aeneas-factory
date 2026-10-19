// Integration tests: the extension in a real VS Code, against the real factory service.
import * as assert from "assert";
import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import type { Api } from "../../src/extension";

const WS = process.env.AEN_TEST_WORKSPACE!;
const REPO = process.env.AEN_TEST_REPO!;
const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, "../../../package.json"), "utf8"));
let api: Api;

function nextRender(file: string) {
  return new Promise<any>((resolve) => {
    const sub = api.preview.onDidRender.event((r) => {
      if (r.source === file && r.status !== "rendering") {
        sub.dispose();
        resolve(r);
      }
    });
  });
}

async function writeAndSave(file: string, text: string) {
  if (!fs.existsSync(file)) fs.writeFileSync(file, "");
  const doc = await vscode.workspace.openTextDocument(file);
  const editor = await vscode.window.showTextDocument(doc);
  await editor.edit((e) => e.replace(new vscode.Range(0, 0, doc.lineCount, 0), text));
  const rendered = nextRender(file);
  await doc.save();
  return rendered;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

suite("Aeneas Factory extension", () => {
  suiteSetup(async () => {
    const ext = vscode.extensions.getExtension(`${pkg.publisher}.${pkg.name}`)!;
    api = (await ext.activate()) as Api;
    assert.ok(await api.factory.client(), "the factory service is reachable");
  });

  test("registers every command it declares", async () => {
    const all = new Set(await vscode.commands.getCommands(true));
    const missing = pkg.contributes.commands.map((c: any) => c.command).filter((c: string) => !all.has(c));
    assert.deepStrictEqual(missing, []);
  });

  test("renders a D2 diagram on save, without adding it to the library", async () => {
    const src = path.join(WS, "flow.d2");
    const r = await writeAndSave(src, "idea -> sketch -> asset\n");
    assert.strictEqual(r.status, "done", r.error);
    const png = path.join(WS, "flow.png");
    assert.ok(fs.statSync(png).size > 1000);
    const rec = JSON.parse(fs.readFileSync(png + ".json", "utf8"));
    assert.strictEqual(rec.source, "idea -> sketch -> asset\n");
    const client = await api.factory.client();
    const inLibrary = await client.library({ project: WS, limit: 50 });
    assert.ok(!inLibrary.some((e) => e.path === fs.realpathSync(png) || e.path === png), "a save does not add to the library");
  });

  test("puts a rendering error on the line it names", async () => {
    const src = path.join(WS, "broken.dot");
    const r = await writeAndSave(src, "digraph {\n  a -> b\n  c -> -> d\n}\n");
    assert.strictEqual(r.status, "failed");
    const problems = vscode.languages.getDiagnostics(vscode.Uri.file(src));
    assert.strictEqual(problems.length, 1);
    assert.strictEqual(problems[0].source, "aeneas");
    assert.strictEqual(problems[0].range.start.line, 2, problems[0].message);
    // fixing it clears the problem
    const fixed = await writeAndSave(src, "digraph {\n  a -> b\n}\n");
    assert.strictEqual(fixed.status, "done", fixed.error);
    assert.strictEqual(vscode.languages.getDiagnostics(vscode.Uri.file(src)).length, 0);
  });

  test("previews ABC music: audio, MIDI and a waveform", async () => {
    const src = path.join(WS, "tune.abc");
    fs.copyFileSync(path.join(REPO, "docs/gallery/explicit/tavern.abc"), src);
    const rendered = nextRender(src);
    await vscode.commands.executeCommand("aeneas.openPreview", vscode.Uri.file(src));
    const r = await rendered;
    assert.strictEqual(r.status, "done", r.error);
    for (const f of ["tune.wav", "tune.mid", "tune_wave.png"]) assert.ok(fs.existsSync(path.join(WS, f)), f);
  });

  test("compiles Ink and leaves the unchanged source alone", async () => {
    const src = path.join(WS, "story.ink");
    const before = Date.now();
    const r = await writeAndSave(src, "Hello.\n* [Hi] Hi!\n  -> END\n* [Bye] Bye.\n  -> END\n");
    assert.strictEqual(r.status, "done", r.error);
    assert.ok(JSON.parse(fs.readFileSync(path.join(WS, "story.json"), "utf8").replace(/^\uFEFF/, "")).inkVersion);
    const doc = vscode.workspace.textDocuments.find((d) => d.fileName === src)!;
    assert.ok(!doc.isDirty);
    assert.ok(fs.statSync(src).mtimeMs <= before + 5000);
  });

  test("opens .glb and .wav files in its viewers", async () => {
    const glb = path.join(WS, "chest.glb");
    fs.copyFileSync(path.join(REPO, "docs/gallery/chest.glb"), glb);
    fs.copyFileSync(path.join(REPO, "docs/gallery/chest.glb.json"), glb + ".json");
    await vscode.commands.executeCommand("vscode.open", vscode.Uri.file(glb));
    await sleep(500);
    let input = vscode.window.tabGroups.activeTabGroup.activeTab?.input;
    assert.ok(input instanceof vscode.TabInputCustom && input.viewType === "aeneas.glb", "the 3D viewer is the default for .glb");
    await vscode.commands.executeCommand("vscode.open", vscode.Uri.file(path.join(WS, "tune.wav")));
    await sleep(500);
    input = vscode.window.tabGroups.activeTabGroup.activeTab?.input;
    assert.ok(input instanceof vscode.TabInputCustom && input.viewType === "aeneas.audio", "the audio viewer is the default for .wav");
  });

  test("shows provenance and lists jobs without errors", async () => {
    await vscode.commands.executeCommand("aeneas.showProvenance", vscode.Uri.file(path.join(WS, "chest.glb")));
    await vscode.commands.executeCommand("aeneas.refreshJobs");
    const items = api.jobs.getChildren();
    assert.ok(items.some((i) => String(i.label).startsWith("diagram")), "the renders appear in the Jobs view");
  });
});
