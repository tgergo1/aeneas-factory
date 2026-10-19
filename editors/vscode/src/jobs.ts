// The Jobs view, the status bar item, and notifications when jobs started here finish.
// Polls /health (which does not count as activity, so an idle service can still stop by itself) and
// asks for the job list only while something is queued or running, or when the view is opened.
import * as vscode from "vscode";
import { Factory, errorText } from "./context";
import { jobTitle, resultFile } from "./core/jobs";
import { Client, Health, Job } from "./core/service";

export { jobTitle, resultFile };

const ACTIVE = new Set(["queued", "running"]);

class JobItem extends vscode.TreeItem {
  constructor(readonly job: Job) {
    super(jobTitle(job), vscode.TreeItemCollapsibleState.None);
    const pct = Math.round(job.progress * 100);
    const icons: Record<string, string> = { queued: "clock", running: "sync~spin", done: "pass", failed: "error", cancelled: "circle-slash" };
    this.iconPath = new vscode.ThemeIcon(icons[job.status] ?? "circle");
    this.description = job.status === "running" ? `${pct}% · ${job.message}` : job.status === "failed" ? "failed" : job.status;
    this.tooltip = new vscode.MarkdownString(
      [`**${jobTitle(job)}**`, `status: ${job.status}`, job.message && `message: ${job.message}`, job.error && `error: ${job.error}`, `id: \`${job.id}\``]
        .filter(Boolean).join("\n\n"),
    );
    this.contextValue = ACTIVE.has(job.status) ? "job.active" : `job.${job.status}`;
    const file = resultFile(job);
    if (job.status === "done" && file) {
      this.command = { command: "aeneas.openJobResult", title: "Open Result", arguments: [job] };
      this.resourceUri = vscode.Uri.file(file);
    }
  }
}

export class Jobs implements vscode.TreeDataProvider<JobItem>, vscode.Disposable {
  private jobs: Job[] = [];
  private health: Health | undefined;
  private readonly changed = new vscode.EventEmitter<void>();
  readonly onDidChangeTreeData = this.changed.event;
  private readonly status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
  private readonly mine = new Map<string, (job: Job) => void>();
  private timer: NodeJS.Timeout | undefined;
  private view: vscode.TreeView<JobItem> | undefined;
  private disposed = false;

  constructor(private readonly factory: Factory) {
    this.status.command = "aeneas.menu";
    this.status.name = "Aeneas Factory";
    this.status.show();
    this.render();
    this.schedule(0);
  }

  attach(view: vscode.TreeView<JobItem>) {
    this.view = view;
    view.onDidChangeVisibility((e) => e.visible && this.refresh());
  }

  /** Follow a job started from this window; `onDone` runs when it finishes. */
  track(job: Job, onDone?: (job: Job) => void) {
    this.mine.set(job.id, onDone ?? (() => undefined));
    this.jobs = [job, ...this.jobs.filter((j) => j.id !== job.id)];
    this.changed.fire();
    this.render();
    this.schedule(300);
  }

  getTreeItem(item: JobItem) {
    return item;
  }

  getChildren(): JobItem[] {
    return this.jobs.map((j) => new JobItem(j));
  }

  async refresh() {
    const client = await this.factory.running();
    await this.poll(client, true);
  }

  async cancel(item: JobItem | Job) {
    const job = item instanceof JobItem ? item.job : item;
    try {
      await (await this.factory.client()).cancel(job.id);
      await this.refresh();
    } catch (e) {
      vscode.window.showErrorMessage(`Could not cancel: ${errorText(e)}`);
    }
  }

  private schedule(ms: number) {
    if (this.disposed) return;
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => this.tick(), ms);
  }

  private async tick() {
    let busy = false;
    try {
      const client = await this.factory.running();
      busy = await this.poll(client, false);
    } catch (e) {
      this.factory.log.warn(`polling the service: ${errorText(e)}`);
    }
    this.schedule(busy ? 1500 : 10_000);
  }

  private async poll(client: Client | undefined, forceList: boolean): Promise<boolean> {
    if (!client) {
      this.health = undefined;
      this.render();
      return this.mine.size > 0;
    }
    try {
      this.health = await client.health();
      this.factory.noteVersion(this.health.version);
    } catch {
      this.health = undefined;
    }
    const active = (this.health?.queued ?? 0) + (this.health?.running ?? 0);
    const listNow = forceList || active > 0 || this.mine.size > 0 || this.jobs.some((j) => ACTIVE.has(j.status)) || (this.view?.visible && this.jobs.length === 0);
    if (listNow) {
      try {
        this.jobs = await client.jobs(30);
        this.changed.fire();
        this.finishTracked();
      } catch (e) {
        this.factory.log.warn(`listing jobs: ${errorText(e)}`);
      }
    }
    this.render();
    return active > 0 || this.mine.size > 0;
  }

  private finishTracked() {
    for (const job of this.jobs) {
      const done = this.mine.get(job.id);
      if (done && !ACTIVE.has(job.status)) {
        this.mine.delete(job.id);
        done(job);
      }
    }
  }

  private render() {
    const running = this.jobs.find((j) => j.status === "running");
    const queued = this.jobs.filter((j) => j.status === "queued").length;
    if (!this.health) {
      this.status.text = "$(circle-slash) Aeneas";
      this.status.tooltip = "Aeneas Factory: the service is not running (it starts with the first command)";
    } else if (running) {
      this.status.text = `$(sync~spin) Aeneas ${Math.round(running.progress * 100)}%${queued ? ` +${queued}` : ""}`;
      this.status.tooltip = `${jobTitle(running)}: ${running.message}`;
    } else {
      this.status.text = "$(sparkle) Aeneas";
      const loaded = this.health.models_loaded.length ? `; loaded: ${this.health.models_loaded.join(", ")}` : "";
      this.status.tooltip = `Aeneas Factory ${this.health.version}: idle${loaded}`;
    }
    if (this.view) {
      const active = this.jobs.filter((j) => ACTIVE.has(j.status)).length;
      this.view.badge = active ? { value: active, tooltip: `${active} job(s) queued or running` } : undefined;
    }
  }

  dispose() {
    this.disposed = true;
    if (this.timer) clearTimeout(this.timer);
    this.status.dispose();
    this.changed.dispose();
  }
}
