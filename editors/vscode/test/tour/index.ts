// A screenshot tour: walks a real VS Code window through the extension's views, one step each time
// the file AEN_TOUR_DIR/next appears. For checking the UI and making documentation pictures; not a test.
import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";

const DIR = process.env.AEN_TOUR_DIR!;
const WS = process.env.AEN_TEST_WORKSPACE!;
const open = (f: string) => vscode.commands.executeCommand("vscode.open", vscode.Uri.file(path.join(WS, f)));

const steps: Array<[string, () => Thenable<unknown> | Promise<unknown>]> = [
  ["provenance of a generated image", async () => {
    await open("chest.png");
    await vscode.commands.executeCommand("aeneas.showProvenance", vscode.Uri.file(path.join(WS, "chest.png")));
  }],
  ["provenance of a 3D model", async () => {
    await open("chest.glb");
    await vscode.commands.executeCommand("aeneas.showProvenance", vscode.Uri.file(path.join(WS, "chest.glb")));
  }],
  ["the whole provenance record (other views hidden)", async () => {
    await vscode.commands.executeCommand("aeneas.jobs.toggleVisibility");
    await vscode.commands.executeCommand("aeneas.library.toggleVisibility");
  }],
  ["live preview of ABC music", async () => {
    await vscode.commands.executeCommand("aeneas.jobs.toggleVisibility");
    await vscode.commands.executeCommand("aeneas.library.toggleVisibility");
    await vscode.window.showTextDocument(vscode.Uri.file(path.join(WS, "tavern.abc")));
    await vscode.commands.executeCommand("aeneas.openPreview");
  }],
  ["live preview of a D2 diagram", async () => {
    await vscode.window.showTextDocument(vscode.Uri.file(path.join(WS, "pipeline.d2")), { viewColumn: vscode.ViewColumn.One });
    await vscode.commands.executeCommand("aeneas.openPreview");
  }],
  ["library", () => vscode.commands.executeCommand("aeneas.library.focus")],
  ["jobs", () => vscode.commands.executeCommand("aeneas.jobs.focus")],
];

async function waitForNext() {
  const flag = path.join(DIR, "next");
  while (!fs.existsSync(flag)) await new Promise((r) => setTimeout(r, 300));
  fs.rmSync(flag);
}

export async function run() {
  await vscode.extensions.getExtension("aeneas-factory.aeneas-factory")!.activate();
  for (let i = 0; i < steps.length; i++) {
    await waitForNext();
    try {
      await steps[i][1]();
      fs.writeFileSync(path.join(DIR, `at-${i + 1}`), steps[i][0]);
    } catch (e) {
      fs.writeFileSync(path.join(DIR, `at-${i + 1}`), `failed: ${e}`);
    }
  }
  await waitForNext();
}
