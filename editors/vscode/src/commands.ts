// Commands that make things: each asks for what it needs, queues a job on the service and opens the
// result when it is ready. Outputs go to <project>/generated/<kind>/, as with the MCP server.
import * as path from "path";
import * as vscode from "vscode";
import { Factory, activeResource, errorText } from "./context";
import { outputPath } from "./core/outputs";
import { Job } from "./core/service";
import { Jobs, jobTitle, resultFile } from "./jobs";

const IMAGE_EXT = /\.(png|jpe?g|webp)$/i;
const VOICES = ["af_heart", "af_bella", "am_michael", "am_adam", "bf_emma", "bm_george"];

export class Commands {
  constructor(private readonly factory: Factory, private readonly jobs: Jobs) {}

  /** Queue an operation and open its result when it is done. */
  async submit(op: string, args: Record<string, unknown>, opts: { library?: boolean; quiet?: boolean } = {}): Promise<Job | undefined> {
    try {
      const client = await this.factory.client();
      const job = await client.submitOp(op, args, { library: opts.library });
      this.jobs.track(job, (j) => this.finished(j, opts.quiet));
      if (!opts.quiet) vscode.window.setStatusBarMessage(`Aeneas: queued ${jobTitle(job)}`, 4000);
      return job;
    } catch (e) {
      vscode.window.showErrorMessage(`Aeneas: ${errorText(e)}`);
      return undefined;
    }
  }

  async finished(job: Job, quiet = false) {
    const file = resultFile(job);
    if (job.status === "done" && file) {
      if (quiet) return;
      const pick = await vscode.window.showInformationMessage(`Ready: ${path.basename(file)}`, "Open", "Show Provenance", "Reveal");
      if (pick === "Open") await openResult(job);
      if (pick === "Show Provenance") await vscode.commands.executeCommand("aeneas.showProvenance", vscode.Uri.file(file));
      if (pick === "Reveal") await vscode.commands.executeCommand("revealInExplorer", vscode.Uri.file(file));
    } else if (job.status === "failed") {
      const pick = await vscode.window.showErrorMessage(`Aeneas: ${jobTitle(job)} failed: ${job.error ?? "unknown error"}`, "Show Log");
      if (pick === "Show Log") this.factory.log.show();
      this.factory.log.error(`${job.id} ${jobTitle(job)}: ${job.error}`);
    }
  }

  private async ask(prompt: string, placeHolder: string, value?: string): Promise<string | undefined> {
    const v = await vscode.window.showInputBox({ prompt, placeHolder, value, ignoreFocusOut: true });
    return v?.trim() || undefined;
  }

  private async pick<T extends string>(title: string, items: Array<{ label: T; description?: string; detail?: string }>): Promise<T | undefined> {
    return (await vscode.window.showQuickPick(items, { title, ignoreFocusOut: true }))?.label;
  }

  private async candidates(): Promise<number | undefined> {
    const c = await this.pick("How many to make?", [
      { label: "1", description: "one result" },
      { label: "3", description: "three, failures dropped, the best by prompt match kept (slower)" },
    ]);
    return c ? Number(c) : undefined;
  }

  private async imageArg(uri?: vscode.Uri): Promise<string | undefined> {
    const u = uri ?? activeResource();
    if (u && IMAGE_EXT.test(u.fsPath)) return u.fsPath;
    const picked = await vscode.window.showOpenDialog({ canSelectMany: false, filters: { Images: ["png", "jpg", "jpeg", "webp"] }, defaultUri: u });
    return picked?.[0]?.fsPath;
  }

  async generateImage() {
    const project = await this.factory.requireProject();
    if (!project) return;
    const prompt = await this.ask("Describe the image", "a weathered wooden treasure chest, a single object on a plain white background");
    if (!prompt) return;
    const model = await this.pick("Model", [
      { label: "z-image-turbo", description: "default: photographic and illustrative, 8 steps" },
      { label: "flux2-klein-4b", description: "4 steps; also edits from references" },
    ]);
    if (!model) return;
    const candidates = await this.candidates();
    if (!candidates) return;
    await this.submit("image", { prompt, model, candidates, out: outputPath("image", project, prompt, this.factory.outputFolder()) });
  }

  async editImage(uri?: vscode.Uri) {
    const src = await this.imageArg(uri);
    const project = src && (await this.factory.requireProject(vscode.Uri.file(src)));
    if (!src || !project) return;
    const prompt = await this.ask(`What should change in ${path.basename(src)}?`, "paint the planks deep blue, keep everything else");
    if (!prompt) return;
    await this.submit("edit", { prompt, src, out: outputPath("edit", project, prompt, this.factory.outputFolder()) });
  }

  async makeTexture() {
    const project = await this.factory.requireProject();
    if (!project) return;
    const prompt = await this.ask("Describe the surface", "weathered oak planks seen from directly above");
    if (!prompt) return;
    const candidates = await this.candidates();
    if (!candidates) return;
    await this.submit("texture", { prompt, candidates, out: outputPath("texture", project, prompt, this.factory.outputFolder()) });
  }

  async imageTo3d(uri?: vscode.Uri) {
    const src = await this.imageArg(uri);
    const project = src && (await this.factory.requireProject(vscode.Uri.file(src)));
    if (!src || !project) return;
    const res = await this.pick("Resolution", [
      { label: "512", description: "about 5 minutes" },
      { label: "1024", description: "about 24 minutes, finer detail" },
    ]);
    if (!res) return;
    await this.submit("model3d", { src, res, out: outputPath("model3d", project, path.parse(src).name, this.factory.outputFolder()) });
  }

  async generateSound() {
    const project = await this.factory.requireProject();
    if (!project) return;
    const prompt = await this.ask("Describe the sound", "an old wooden door creaks open slowly, then thuds shut");
    if (!prompt) return;
    const seconds = await this.ask("Length in seconds (up to 30)", "5", "5");
    if (!seconds || !(Number(seconds) > 0)) return;
    const candidates = await this.candidates();
    if (!candidates) return;
    await this.submit("sfx", { prompt, seconds: Number(seconds), candidates, out: outputPath("sfx", project, prompt, this.factory.outputFolder()) });
  }

  async generateSpeech() {
    const project = await this.factory.requireProject();
    if (!project) return;
    const text = await this.ask("What should be said?", "Welcome to the village.");
    if (!text) return;
    const voice = await this.pick("Voice", VOICES.map((v) => ({ label: v, description: v[0] === "a" ? "American English" : "British English" })));
    if (!voice) return;
    await this.submit("speech", { text, voice, out: outputPath("speech", project, text, this.factory.outputFolder()) });
  }

  async upscale(uri?: vscode.Uri) {
    const src = await this.imageArg(uri);
    const project = src && (await this.factory.requireProject(vscode.Uri.file(src)));
    if (!src || !project) return;
    await this.submit("upscale", { src, out: outputPath("upscale", project, path.parse(src).name + "-4x", this.factory.outputFolder()) });
  }

  async removeBackground(uri?: vscode.Uri) {
    const src = await this.imageArg(uri);
    const project = src && (await this.factory.requireProject(vscode.Uri.file(src)));
    if (!src || !project) return;
    await this.submit("matte", { src, out: outputPath("matte", project, path.parse(src).name + "-cutout", this.factory.outputFolder()) });
  }

  async runRecipe() {
    const project = await this.factory.requireProject();
    if (!project) return;
    let recipes;
    try {
      recipes = (await (await this.factory.client()).capabilities(project)).recipes;
    } catch (e) {
      vscode.window.showErrorMessage(`Aeneas: ${errorText(e)}`);
      return;
    }
    const name = await this.pick("Recipe", Object.entries(recipes).map(([label, r]) => ({ label, detail: r.description })));
    if (!name) return;
    const inputs: Record<string, string> = {};
    for (const [key, help] of Object.entries(recipes[name].inputs)) {
      const v = await vscode.window.showInputBox({ title: `${name}: ${key}`, prompt: help || key, placeHolder: "empty for the recipe's default", ignoreFocusOut: true });
      if (v === undefined) return;
      if (v.trim()) inputs[key] = v.trim();
    }
    try {
      const client = await this.factory.client();
      const job = await client.submitRecipe(name, inputs, path.join(project, this.factory.outputFolder(), name));
      this.jobs.track(job, (j) => this.finished(j));
      vscode.window.setStatusBarMessage(`Aeneas: queued recipe ${name}`, 4000);
    } catch (e) {
      vscode.window.showErrorMessage(`Aeneas: ${errorText(e)}`);
    }
  }

  async menu() {
    const items: Array<vscode.QuickPickItem & { command: string }> = [
      { label: "$(file-media) Generate Image…", command: "aeneas.generateImage" },
      { label: "$(edit) Edit Image by Instruction…", command: "aeneas.editImage" },
      { label: "$(symbol-color) Make Seamless Texture…", command: "aeneas.makeTexture" },
      { label: "$(package) Make 3D Model from Image…", command: "aeneas.imageTo3d" },
      { label: "$(unmute) Generate Sound Effect…", command: "aeneas.generateSound" },
      { label: "$(comment) Generate Speech…", command: "aeneas.generateSpeech" },
      { label: "$(zoom-in) Upscale Image 4x…", command: "aeneas.upscale" },
      { label: "$(screen-cut) Remove Background…", command: "aeneas.removeBackground" },
      { label: "$(checklist) Run Recipe…", command: "aeneas.runRecipe" },
      { label: "$(play) Render This Source", command: "aeneas.render", detail: "diagrams, SVG, ABC music, Ink and Yarn dialogue" },
      { label: "$(info) Show Provenance", command: "aeneas.showProvenance" },
      { label: "$(law) Write Project Credits", command: "aeneas.credits" },
      { label: "$(output) Show Log", command: "aeneas.showLog" },
    ];
    const pick = await vscode.window.showQuickPick(items, { title: "Aeneas Factory" });
    if (pick) await vscode.commands.executeCommand(pick.command);
  }
}

export async function openResult(job: Job) {
  const file = resultFile(job);
  if (file) await vscode.commands.executeCommand("vscode.open", vscode.Uri.file(file));
}
