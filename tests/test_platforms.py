"""What differs between macOS, Linux and Windows: sandboxes, model variants, login items, launchers."""
import os

import pytest

from aeneas import host, registry, service


def test_bwrap_hides_home_and_network_for_programs(tmp_path):
    args = host.bwrap_args(tmp_path, loopback=True, readable=["/usr/bin/env"])
    assert args[0] == "bwrap" and args[-1] == "--"
    assert "--unshare-net" in args  # a private network namespace: its own loopback only
    triples = [args[i:i + 3] for i in range(len(args) - 2)]
    pairs = [args[i:i + 2] for i in range(len(args) - 1)]
    w = os.path.realpath(tmp_path)
    assert ["--tmpfs", str(host.HOME)] in pairs  # the home folder is replaced by an empty one
    assert ["--bind", w, w] in triples  # except the work folder, writable
    plain = host.bwrap_args(tmp_path)
    assert ["--tmpfs", str(host.HOME)] not in [plain[i:i + 2] for i in range(len(plain) - 1)]  # notation tools may read home


def test_sandboxed_reports_whether_it_isolates(tmp_path, monkeypatch):
    monkeypatch.setenv("AEN_NO_SANDBOX", "1")
    cmd, isolated = host.sandboxed(["echo", "hi"], tmp_path)
    assert cmd == ["echo", "hi"] and isolated is False


def test_programs_are_refused_without_a_sandbox(tmp_path, monkeypatch):
    from aeneas import explicit
    monkeypatch.setenv("AEN_NO_SANDBOX", "1")
    monkeypatch.delenv("AEN_ALLOW_UNSANDBOXED", raising=False)
    monkeypatch.setattr(explicit, "locate", lambda name: "/bin/true")
    with pytest.raises(explicit.SandboxUnavailable):
        explicit.command("sonic-pi", [], sandbox_dir=tmp_path, readable=[])
    assert explicit.command("dot", ["-V"], sandbox_dir=tmp_path) == ["/bin/true", "-V"]  # notation still runs


def test_each_machine_gets_its_own_sound_and_speech(monkeypatch):
    for os_name, arch, sound, speech in [("macos", "arm64", "moss-sfx", "kokoro-82m"), ("linux", "x64", "moss-sfx-gguf", "kokoro-torch"),
                                         ("windows", "x64", "moss-sfx-gguf", "kokoro-torch"), ("macos", "x64", "moss-sfx-gguf", "kokoro-torch")]:
        monkeypatch.setattr(host, "OS", os_name)
        monkeypatch.setattr(host, "ARCH", arch)
        assert registry.pick("moss-sfx", "moss-sfx-gguf") == sound
        assert registry.pick("kokoro-82m", "kokoro-torch") == speech
        sel = registry.selection(["all"])
        assert sound in sel and ({"moss-sfx", "moss-sfx-gguf"} - {sound}).isdisjoint(sel)


def test_systemd_unit_runs_the_service_without_idle_exit():
    unit = service.systemd_unit()
    assert "-m aeneas serve --idle-exit 0" in unit and "Restart=on-failure" in unit and "WantedBy=default.target" in unit


def test_apt_list_has_only_package_names():
    names = [l.split("#", 1)[0].strip() for l in open(os.path.join(os.path.dirname(__file__), "..", "deps", "apt.txt"))]
    names = [n for n in names if n]
    assert names and all(" " not in n and n == n.lower() for n in names)  # apt-get aborts on any unknown name


@pytest.mark.parametrize("name", ["apt", "dnf", "pacman", "brew-linux", "winget"])
def test_every_package_list_reads(name):
    path = os.path.join(os.path.dirname(__file__), "..", "deps", f"{name}.txt")
    lines = [l.split("#", 1)[0].strip() for l in open(path)]
    assert all(" " not in l for l in lines if l)
