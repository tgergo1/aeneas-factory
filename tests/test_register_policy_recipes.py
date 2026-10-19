import re

import pytest

from aeneas import policy, recipes, registry, styles

PINNED = re.compile(r"https://huggingface\.co/[^/]+/[^/]+/resolve/[0-9a-f]{40}/|https://github\.com/[^/]+/[^/]+/releases/download/|https://raw\.githubusercontent\.com/[^/]+/[^/]+/[0-9a-f]{40}/|https://dl\.fbaipublicfiles\.com/")


def test_register_is_complete_and_pinned():
    ids = set()
    for m in registry.models():
        assert m["id"] not in ids
        ids.add(m["id"])
        for k in ("name", "group", "summary", "licence", "spdx", "commercial_output", "upstream", "path", "files"):
            assert k in m, (m["id"], k)
        assert m["path"] == f"models/{m['id']}"
        for f in m["files"]:
            assert f["bytes"] > 0 and re.fullmatch(r"[0-9a-f]{64}", f["sha256"]), (m["id"], f["path"])
            assert PINNED.match(f["url"]), f"{m['id']}: {f['url']} is not pinned to a commit or release"
        for r in m.get("requires", []):
            assert r in {x["id"] for x in registry.models()}
        for a in m.get("accept", []):
            assert {"key", "licence", "url", "files", "why"} <= set(a)


def test_dinov3_needs_acceptance():
    assert [a["key"] for a in registry.needs_acceptance("trellis2")] == ["dinov3"]


def test_selection_brings_requirements_first():
    assert registry.selection(["flux2-klein-4b"]) == ["z-image-turbo", "flux2-klein-4b"]


def test_policy(tmp_path):
    assert policy.check_models(["trellis2"], tmp_path / "x.glb")["policy"].startswith("none")
    policy.init(tmp_path)
    with pytest.raises(policy.PolicyError, match="DINOv3"):
        policy.check_models(["trellis2"], tmp_path / "sub" / "x.glb")
    policy.check_models(["z-image-turbo"], tmp_path / "x.png")
    f = tmp_path / ".aeneas" / "policy.toml"
    f.write_text(f.read_text().replace("allow_models = []", 'allow_models = ["trellis2"]'))
    policy.check_models(["trellis2"], tmp_path / "x.glb")
    with pytest.raises(policy.PolicyError):
        policy.check_licence("CC BY-SA 4.0", tmp_path)
    assert policy.check_licence("cc0", tmp_path) == "CC0-1.0"


@pytest.mark.parametrize("name", sorted(recipes.list_recipes()))
def test_recipes_validate(name):
    assert recipes.validate(recipes.find(name))


def test_placeholders_keep_types():
    env = {"inputs": {"n": 3, "s": "box"}, "steps": {"a": {"path": "/x.png"}}}
    assert recipes._fill("{n}", env) == 3
    assert recipes._fill("a {s} at {a.path}", env) == "a box at /x.png"
    with pytest.raises(recipes.RecipeError):
        recipes._fill("{b.path}", env)


def test_style_applies():
    st = styles.find("storybook")
    p, neg, model, refs, loras, _ = styles.apply_image(st, "a cottage", "blurry")
    assert p.startswith("a cottage") and "storybook" in p and "blurry" in neg and model == "z-image-turbo"
    assert set(styles.list_styles()) >= {"storybook", "photoreal"}


def test_scoring_models_are_ones_whose_cards_allow_this_use():
    ids = {m["id"] for m in registry.models()}
    assert "clip-vit-b32" not in ids  # OpenAI's card puts any deployed use out of scope
    assert {"siglip-base-p16", "clap-htsat"} <= ids
    from aeneas import scoring
    assert scoring.IMAGE_MODEL == "siglip-base-p16"
