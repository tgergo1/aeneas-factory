"""Keep the numbers in the docs in step with models.json, so sizes and licences never drift.

  python scripts/gen_docs.py          rewrite the generated sections of README.md
  python scripts/gen_docs.py --check  fail if README.md or docs/factory.svg disagree with models.json

README.md sections between <!-- models:start --> and <!-- models:end --> are generated."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
START, END = "<!-- models:start -->", "<!-- models:end -->"


def gb(n):
    return f"{n / 1e9:.1f} GB" if n >= 1e9 else f"{n / 1e6:.0f} MB"


def table(reg):
    rows = ["| Model | Group | Size | Does | Licence | Source |", "|---|---|---|---|---|---|"]
    for m in reg["models"]:
        size = sum(f["bytes"] for f in m["files"])
        opt = "" if m.get("default") else " (optional)"
        acc = " Download needs `ACCEPT=" + ",".join(a["key"] for a in m.get("accept", [])) + "`." if m.get("accept") else ""
        rows.append(f"| {m['name']} | {m['group']}{opt} | {gb(size)} | {m['summary']} | {m['licence']}.{acc} | "
                    f"[{m['upstream'].split('//')[-1]}]({m['upstream']}) |")
    core = sum(f["bytes"] for m in reg["models"] if m.get("default") for f in m["files"])
    extra = sum(f["bytes"] for m in reg["models"] if not m.get("default") for f in m["files"])
    rows.append("")
    rows.append(f"The four core models total **{gb(core)}**; the optional ones **{gb(extra)}**. Every file's URL "
                "(pinned to a commit or release), size and SHA-256 are in [`models.json`](models.json).")
    return "\n".join(rows)


def main():
    reg = json.loads((ROOT / "models.json").read_text())
    readme = (ROOT / "README.md").read_text()
    new = re.sub(re.escape(START) + ".*?" + re.escape(END), START + "\n" + table(reg) + "\n" + END, readme, flags=re.S)
    problems = []
    if "--check" in sys.argv:
        if new != readme:
            problems.append("README.md model table is out of date: run python scripts/gen_docs.py")
        svg = (ROOT / "docs" / "factory.svg").read_text()
        for m in reg["models"]:
            if m.get("default"):
                size = gb(sum(f["bytes"] for f in m["files"]))
                if size not in svg:
                    problems.append(f"docs/factory.svg does not show {m['id']} as {size}")
        for p in problems:
            print("FAIL", p)
        sys.exit(1 if problems else 0)
    (ROOT / "README.md").write_text(new)
    print("README.md updated")


if __name__ == "__main__":
    main()
