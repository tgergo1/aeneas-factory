// npm run tour -- <workspace>: start the screenshot tour (see tour/index.ts); `touch <dir>/next` to step.
import { runTests } from "@vscode/test-electron";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";

async function main() {
  const workspace = path.resolve(process.argv[2] ?? ".");
  const dir = process.env.AEN_TOUR_DIR ?? fs.mkdtempSync(path.join(os.tmpdir(), "aen-tour-"));
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "aen-vsc-"));
  fs.mkdirSync(path.join(profile, "u", "User"), { recursive: true });
  fs.writeFileSync(path.join(profile, "u", "User", "settings.json"), JSON.stringify({
    "workbench.startupEditor": "none", "chat.disableAIFeatures": true, "workbench.colorTheme": process.env.AEN_THEME ?? "Default Dark Modern",
    "workbench.editorAssociations": { "*.wav": "aeneas.audio" }, "update.mode": "none",
  }));
  console.log(`tour steps: touch ${dir}/next`);
  try {
    await runTests({
      vscodeExecutablePath: "/Applications/Visual Studio Code.app/Contents/MacOS/Code",
      extensionDevelopmentPath: path.resolve(__dirname, "../.."),
      extensionTestsPath: path.join(__dirname, "tour", "index"),
      launchArgs: [workspace, "--disable-extensions", "--user-data-dir", path.join(profile, "u"), "--extensions-dir", path.join(profile, "e"), "--disable-workspace-trust",
        // keep painting when the window is on another Space, so screenshots stay current
        "--disable-backgrounding-occluded-windows", "--disable-renderer-backgrounding"],
      extensionTestsEnv: { AEN_TOUR_DIR: dir, AEN_TEST_WORKSPACE: workspace },
    });
  } finally {
    fs.rmSync(profile, { recursive: true, force: true });
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
