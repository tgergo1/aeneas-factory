"""A project's licence policy: which licences may go into it, for generated and downloaded assets.

The policy lives in <project>/.aeneas/policy.toml and is found by walking up from the output folder:

  allowed = ["CC0-1.0", "MIT", "Apache-2.0", "OFL-1.1", "CC-BY-4.0", "CC-BY-3.0", "BSD-3-Clause", "Public-Domain"]
  allow_models = []      # models allowed although one of their licences is not in `allowed`
  deny_models = []       # models never to use in this project
  require_credit = true  # list CC BY material in the credits

Without a policy file everything is allowed, and the record says so.
"""
import tomllib
from pathlib import Path

from . import registry

TEMPLATE = '''# Licence policy for this project, read by aeneas-factory.
allowed = ["CC0-1.0", "MIT", "Apache-2.0", "OFL-1.1", "CC-BY-4.0", "CC-BY-3.0", "BSD-3-Clause", "Public-Domain"]
allow_models = []
deny_models = []
require_credit = true
'''

ALIASES = {"cc0": "CC0-1.0", "cc0-1.0": "CC0-1.0", "mit": "MIT", "apache-2.0": "Apache-2.0", "apache 2.0": "Apache-2.0",
           "ofl": "OFL-1.1", "ofl-1.1": "OFL-1.1", "cc-by-4.0": "CC-BY-4.0", "cc by 4.0": "CC-BY-4.0",
           "cc-by-3.0": "CC-BY-3.0", "cc by 3.0": "CC-BY-3.0", "bsd-3-clause": "BSD-3-Clause",
           "public domain": "Public-Domain", "public-domain": "Public-Domain", "pd": "Public-Domain",
           "cc-by-sa-4.0": "CC-BY-SA-4.0", "cc by-sa 4.0": "CC-BY-SA-4.0", "cc-by-nc-4.0": "CC-BY-NC-4.0",
           "openrail++": "LicenseRef-OpenRAIL++-M", "dinov3": "LicenseRef-DINOv3"}


class PolicyError(Exception):
    pass


def normalise(licence):
    if not licence:
        return "unknown"
    return ALIASES.get(licence.strip().lower(), licence.strip())


def project_root(path):
    """The folder holding .aeneas/, else the git root, else the folder itself."""
    p = Path(path).resolve()
    p = p if p.is_dir() else p.parent
    for d in [p, *p.parents]:
        if (d / ".aeneas").is_dir():
            return d
    for d in [p, *p.parents]:
        if (d / ".git").exists():
            return d
    return p


def load(path):
    root = project_root(path)
    f = root / ".aeneas" / "policy.toml"
    if not f.exists():
        return None, root
    pol = tomllib.loads(f.read_text())
    pol["allowed"] = [normalise(x) for x in pol.get("allowed", [])]
    pol["_file"] = str(f)
    return pol, root


def init(project_dir):
    d = Path(project_dir) / ".aeneas"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "policy.toml"
    if not f.exists():
        f.write_text(TEMPLATE)
    return f


def check_models(model_ids, out_path):
    """Raise PolicyError if a model may not be used for this output. Returns a short record."""
    pol, root = load(out_path)
    if pol is None:
        return {"policy": "none (no .aeneas/policy.toml in the project)"}
    for mid in model_ids:
        m = registry.model(mid)
        if mid in pol.get("deny_models", []):
            raise PolicyError(f"{mid} is denied by {pol['_file']}")
        bad = [l for l in m.get("spdx", []) if l not in pol["allowed"]]
        if bad and mid not in pol.get("allow_models", []):
            raise PolicyError(f"{mid} carries {', '.join(bad)}, not allowed by {pol['_file']}. "
                              f"Add it to allow_models there if you accept that.")
    return {"policy": pol["_file"], "allowed": pol["allowed"]}


def check_licence(licence, path):
    pol, _ = load(path)
    lic = normalise(licence)
    if pol is not None and lic not in pol["allowed"]:
        raise PolicyError(f"{licence} is not allowed by {pol['_file']}")
    return lic
