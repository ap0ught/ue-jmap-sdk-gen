#!/usr/bin/env python3
"""sdkgen.py — orchestrate jmap -> C++ SDK generation and verification.

Subcommands
-----------
  generate   Run generator/jmap2sdk.py against a .jmap and write sdk/ (plus version.json)
  verify     Compile the generated SDK and probe a set of golden sizes/offsets from game.yaml
  update     Regenerate from a newer .jmap, diff metadata against the last version.json,
             verify, and report the change set

The generator itself is untouched; this wrapper adds:
  - version.json  (game build metadata captured at generate time)
  - temporary probe.cpp built from verify/probe.cpp.tmpl + game.yaml.verify
  - machine-readable change reports for the update-sdk GitHub Action
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(REPO, "generator", "jmap2sdk.py")
PROBE_TMPL = os.path.join(REPO, "verify", "probe.cpp.tmpl")

PREFIX = {
    "enums": "E",
    "structs": "F",
    "classes": "U",
}


def load_yaml(path):
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        sys.exit("PyYAML is required:  python3 -m pip install pyyaml")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")


def build_probe(config, out_sdk, probe_dir):
    """Render verify/probe.cpp.tmpl with the golden sizes/offsets from game.yaml."""
    with open(PROBE_TMPL, encoding="utf-8") as f:
        tmpl = f.read()

    defines = []
    assert_checks = []
    for kind in ("structs", "classes"):
        for name, size in (config.get("verify", {}).get(kind) or {}).items():
            cpp = PREFIX[kind] + name
            macro = "HAS_%s_%s" % (kind.upper(), name)
            defines.append("#define %s 1" % macro)
            assert_checks.append(
                "#ifdef %s\nstatic_assert(sizeof(SDK::%s) == %d, \"%s size\");\n#endif"
                % (macro, cpp, size, cpp))
    for name, offs in (config.get("verify", {}).get("offsets") or {}).items():
        for member, off in offs.items():
            assert_checks.append(
                "#ifdef %s\nstatic_assert(offsetof(SDK::F%s, %s) == %d, \"offset %s::%s\");\n#endif"
                % ("HAS_STRUCTS_" + name, name, member, off, name, member))

    probe = (tmpl
             .replace("//__CHECKS__", "\n".join(assert_checks))
             .replace("//__DEFINES__", "\n".join(defines)))
    path = os.path.join(probe_dir, "probe.cpp")
    with open(path, "w", encoding="utf-8") as f:
        f.write(probe)
    return path


def compile_headers(out_sdk):
    """g++ -std=c++17 -fsyntax-only Classes.hpp in the sdk dir."""
    classes = os.path.join(out_sdk, "Classes.hpp")
    if not os.path.isfile(classes):
        return False, "Classes.hpp missing"
    r = subprocess.run(["g++", "-std=c++17", "-fsyntax-only", "Classes.hpp"],
                       cwd=out_sdk, capture_output=True, text=True)
    if r.returncode != 0:
        return False, r.stderr.strip()
    return True, ""


def run_probe(out_sdk, probe_path, extra_args=None):
    """Compile+run the probe; returns (ok, text_or_error)."""
    exe = os.path.join(os.path.dirname(probe_path), "probe")
    args = ["g++", "-std=c++17", "-I", out_sdk, probe_path, "-o", exe]
    if extra_args:
        args += extra_args
    try:
        subprocess.run(args, check=True, capture_output=True, text=True)
    except FileNotFoundError:
        return False, "g++ not found (needed for verification)"
    except subprocess.CalledProcessError as e:
        return False, e.stderr.strip()
    r = subprocess.run([exe], capture_output=True, text=True)
    if r.returncode != 0:
        return False, r.stdout.strip() or r.stderr.strip()
    return True, r.stdout.strip()


def make_argparser():
    ap = argparse.ArgumentParser(description="jmap -> C++ SDK generator + verifier")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="generate sdk/ from a .jmap")
    g.add_argument("--jmap", required=True)
    g.add_argument("--config", default=os.path.join(REPO, "game.yaml"))
    g.add_argument("--out", default=os.path.join(REPO, "sdk"))
    g.add_argument("--modules", default="",
                   help="comma-separated module filter, e.g. P9Playable. empty = all")
    g.set_defaults(fn=cmd_generate)

    v = sub.add_parser("verify", help="compile + probe the generated SDK")
    v.add_argument("--sdk", default=os.path.join(REPO, "sdk"))
    v.add_argument("--config", default=os.path.join(REPO, "game.yaml"))
    v.add_argument("--jmap", default=None,
                   help="optional: extra headless checks (metadata match) against this dump")
    v.set_defaults(fn=cmd_verify)

    u = sub.add_parser("update", help="regenerate for a newer build + report changes")
    u.add_argument("--jmap", required=True)
    u.add_argument("--config", default=os.path.join(REPO, "game.yaml"))
    u.add_argument("--out", default=os.path.join(REPO, "sdk"))
    u.set_defaults(fn=cmd_update)

    return ap


def cmd_generate(args):
    config = load_yaml(args.config)
    cmd = [sys.executable, GEN, "--jmap", args.jmap, "--out", args.out]
    if args.modules:
        cmd += ["--modules", args.modules]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout, end="")
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        sys.exit(r.returncode)

    meta = load_json(args.jmap).get("metadata", {})
    save_json(os.path.join(args.out, "version.json"), {
        "game": config.get("game", ""),
        "engine": "%s.%s" % (meta.get("engine_version", {}).get("major", ""),
                             meta.get("engine_version", {}).get("minor", "")),
        "build": meta.get("build_change_list", ""),
        "source": meta.get("source", ""),
        "image_base": load_json(args.jmap).get("image_base_address", ""),
        "generator": "jmap2sdk.py",
    })
    print("wrote %s/version.json" % args.out)


def cmd_verify(args):
    config = load_yaml(args.config)
    ok, err = compile_headers(args.sdk)
    print("compile headers: %s" % ("OK" if ok else "FAIL"))
    if not ok:
        print(err)
        sys.exit(1)

    probe_dir = tempfile.mkdtemp(prefix="sdkprobe-")
    probe = build_probe(config, args.sdk, probe_dir)
    ok, out = run_probe(args.sdk, probe)
    print("layout probe: %s" % ("OK" if ok else "FAIL"))
    if not ok:
        print(out)
        sys.exit(1)
    if out:
        print(out)

    if args.jmap:
        meta = load_json(args.jmap).get("metadata", {})
        try:
            vj = load_json(os.path.join(args.sdk, "version.json"))
        except FileNotFoundError:
            vj = {}
        ok = (vj.get("build") == meta.get("build_change_list") and
              vj.get("engine") == "%s.%s" % (meta["engine_version"]["major"], meta["engine_version"]["minor"]))
        print("metadata match: %s" % ("OK" if ok else "MISMATCH (sdk is stale vs --jmap)"))
        if not ok:
            sys.exit(1)

    print("VERIFY PASS")


def cmd_update(args):
    config = load_yaml(args.config)
    prev = None
    try:
        prev = load_json(os.path.join(args.out, "version.json"))
    except FileNotFoundError:
        print("no previous sdk/version.json found; treating as first generation")

    cmd = [sys.executable, GEN, "--jmap", args.jmap, "--out", args.out]
    if config.get("modules"):
        cmd += ["--modules", ",".join(config["modules"])]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout, end="")
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        sys.exit(r.returncode)

    new_meta = load_json(args.jmap).get("metadata", {})
    new_json = {
        "game": config.get("game", ""),
        "engine": "%s.%s" % (new_meta.get("engine_version", {}).get("major", ""),
                             new_meta.get("engine_version", {}).get("minor", "")),
        "build": new_meta.get("build_change_list", ""),
        "source": new_meta.get("source", ""),
        "image_base": load_json(args.jmap).get("image_base_address", ""),
        "generator": "jmap2sdk.py",
    }
    save_json(os.path.join(args.out, "version.json"), new_json)

    changed = []
    if prev:
        for k in ("game", "engine", "build", "source", "image_base"):
            if prev.get(k) != new_json.get(k):
                changed.append("%s: %r -> %r" % (k, prev.get(k), new_json.get(k)))
    report = {
        "old": prev,
        "new": new_json,
        "changed": changed,
    }
    report_path = os.path.join(args.out, "update-report.json")
    save_json(report_path, report)
    print("wrote %s" % report_path)
    print("update report: " + (", ".join(changed) if changed else "no build metadata changes"))

    # verify the freshly generated tree
    ok, err = compile_headers(args.out)
    print("compile headers: %s" % ("OK" if ok else "FAIL"))
    if not ok:
        print(err)
        sys.exit(1)
    probe_dir = tempfile.mkdtemp(prefix="sdkprobe-")
    probe = build_probe(config, args.out, probe_dir)
    ok, out = run_probe(args.out, probe)
    print("layout probe: %s" % ("OK" if ok else "FAIL"))
    if not ok:
        print(out)
        sys.exit(1)
    if out:
        print(out)
    print("UPDATE VERIFY PASS")


if __name__ == "__main__":
    args = make_argparser().parse_args()
    args.fn(args)