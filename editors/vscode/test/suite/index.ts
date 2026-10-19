import * as fs from "fs";
import Mocha from "mocha";
import * as path from "path";

export function run(): Promise<void> {
  const mocha = new Mocha({ ui: "tdd", color: true, timeout: 90_000 });
  for (const f of fs.readdirSync(__dirname)) if (f.endsWith(".test.js")) mocha.addFile(path.join(__dirname, f));
  return new Promise((resolve, reject) => mocha.run((failures) => (failures ? reject(new Error(`${failures} test(s) failed`)) : resolve())));
}
