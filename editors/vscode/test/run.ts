// Runs the integration tests inside a real VS Code (the installed one, or a downloaded one with
// AEN_VSCODE=download), with a throwaway profile and no other extensions. The test workspace is under
// ~/.aeneas because the factory service writes only under the home folder.
import { runTests } from "@vscode/test-electron";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";

// The installed VS Code on each OS; elsewhere @vscode/test-electron downloads one (AEN_VSCODE=download forces that).
const INSTALLED = ({
  darwin: "/Applications/Visual Studio Code.app/Contents/MacOS/Code",
  linux: "/usr/share/code/code",
  win32: path.join(process.env.LOCALAPPDATA ?? "", "Programs", "Microsoft VS Code", "Code.exe"),
} as Record<string, string>)[process.platform] ?? "";

async function main() {
  if (process.platform === "linux" && !process.env.DISPLAY && !process.env.WAYLAND_DISPLAY) {
    console.error("No display: run the integration tests under a virtual one, e.g. xvfb-run -a npm test");
    process.exit(2);
  }
  const root = path.resolve(__dirname, "../..");
  const workspace = fs.mkdtempSync(path.join(os.homedir(), ".aeneas", "vscode-test-"));
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "aen-vsc-")); // short: VS Code's socket path must stay short
  const useInstalled = process.env.AEN_VSCODE !== "download" && fs.existsSync(INSTALLED);
  try {
    await runTests({
      vscodeExecutablePath: useInstalled ? INSTALLED : undefined,
      extensionDevelopmentPath: root,
      extensionTestsPath: path.join(__dirname, "suite", "index"),
      launchArgs: [workspace, "--disable-extensions", "--user-data-dir", path.join(profile, "u"), "--extensions-dir", path.join(profile, "e"), "--skip-welcome", "--skip-release-notes", "--disable-workspace-trust"],
      extensionTestsEnv: { AEN_TEST_WORKSPACE: workspace, AEN_TEST_REPO: path.resolve(root, "../..") },
    });
  } finally {
    fs.rmSync(workspace, { recursive: true, force: true });
    fs.rmSync(profile, { recursive: true, force: true });
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
