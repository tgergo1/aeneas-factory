"""End-to-end check of the MCP server, the way an agent uses it: start `bin/aen mcp` over stdio,
list the tools, ask for capabilities, generate a small image and check that the result comes back
with a thumbnail. Needs the image models. Usage: .venv/bin/python scripts/mcp_smoke.py PROJECT_DIR"""
import asyncio
import json
import sys
import time
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parent.parent


async def main(project):
    params = StdioServerParameters(command=str(ROOT / "bin" / "aen"), args=["mcp"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()
            tools = sorted(t.name for t in (await s.list_tools()).tools)
            print("tools:", ", ".join(tools))
            caps = json.loads((await s.call_tool("capabilities", {"project_dir": project})).content[0].text)
            print("recipes:", ", ".join(caps["recipes"]), "| styles:", ", ".join(caps["styles"]),
                  "| downloaded:", ", ".join(m["id"] for m in caps["models"] if m["downloaded"]))
            t = time.time()
            r = await s.call_tool("generate_image", {"prompt": "a small clay pot on a plain white background",
                                                     "project_dir": project, "name": "mcp-smoke-pot", "size": 512,
                                                     "seed": 3, "wait_seconds": 110})
            kinds = [c.type for c in r.content]
            text = json.loads(r.content[0].text)
            while text.get("status") in ("queued", "running"):
                r = await s.call_tool("job_status", {"job_id": text["job_id"], "wait_seconds": 60})
                kinds, text = [c.type for c in r.content], json.loads(r.content[0].text)
            print(f"generate_image: {text['status']} in {time.time() - t:.0f} s, content: {kinds}")
            assert text["status"] == "done", text
            assert "image" in kinds, "no thumbnail came back"
            print("result:", text["result"]["path"])
            prov = json.loads((await s.call_tool("get_provenance", {"path": text["result"]["path"]})).content[0].text)
            print("provenance:", prov["models"][0]["id"], "seed", prov["seed"], "checks", prov["checks"])
            hits = json.loads((await s.call_tool("search_assets", {"query": "clay pot"})).content[0].text)
            print("search 'clay pot':", [Path(h["path"]).name for h in hits][:3])
            print("OK")


if __name__ == "__main__":
    asyncio.run(main(str(Path(sys.argv[1]).expanduser().resolve())))
