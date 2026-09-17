"""Append new build artifacts without changing or silently refreshing existing pins."""
from pathlib import Path
import argparse
import hashlib
import json
import os

BUILD = Path(__file__).resolve().parent
MANIFEST = BUILD / "package_manifest.json"


def record(path):
    return {"path": path.relative_to(BUILD).as_posix(), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def local(relative):
    path = (BUILD / relative).resolve()
    assert path.is_relative_to(BUILD) and path != BUILD, relative
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", action="append", required=True)
    parser.add_argument("--delta", required=True)
    args = parser.parse_args()
    original = MANIFEST.read_bytes()
    data = json.loads(original)
    before = list(data["artifacts"])
    known = {row["path"]: row for row in before}
    assert len(known) == len(before), "duplicate existing pin"
    delta = local(args.delta)
    assert delta.suffix == ".json" and delta != MANIFEST
    paths = set()
    for relative in args.path:
        path = local(relative)
        assert path.exists(), relative
        for candidate in ([path] if path.is_file() else path.rglob("*")):
            if not candidate.is_file() or "__pycache__" in candidate.parts or candidate.suffix == ".pyc":
                continue
            candidate = candidate.resolve()
            assert candidate.is_relative_to(BUILD)
            if candidate not in (MANIFEST, delta):
                paths.add(candidate)
    added = []
    for path in sorted(paths):
        row = record(path)
        if row["path"] in known:
            assert row == known[row["path"]], "existing pin changed: " + row["path"]
        else:
            added.append(row)
    if not added:
        assert delta.is_file() and record(delta) == known[delta.relative_to(BUILD).as_posix()]
        print(json.dumps({"ok": True, "unchanged": True, "entries": len(before)}))
        return
    assert not delta.exists(), "use a new checkpoint; do not overwrite a previous delta"
    result = {
        "scope": "Additional offline protocol and acquisition artifacts; not W300 hardware qualification",
        "previous_entry_count": len(before),
        "previous_entries_sha256": hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest(),
        "selected_roots": args.path,
        "added_artifacts": added,
        "camera_communication_verified": False,
        "w300_language_write_verified": False,
    }
    delta.parent.mkdir(parents=True, exist_ok=True)
    delta.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    added.append(record(delta))
    data["artifacts"].extend(added)
    assert MANIFEST.read_bytes() == original, "manifest changed concurrently"
    temporary = BUILD / "package_manifest.append-stage.json"
    with temporary.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(data, indent=2) + "\n")
    assert json.loads(temporary.read_text())["artifacts"][:len(before)] == before
    os.replace(temporary, MANIFEST)
    saved = json.loads(MANIFEST.read_text())
    assert saved["artifacts"][:len(before)] == before
    assert len({row["path"] for row in saved["artifacts"]}) == len(saved["artifacts"])
    for row in added:
        assert record(local(row["path"])) == row
    print(json.dumps({"ok": True, "previous_entries_preserved": len(before),
                      "added_entries_verified": len(added), "entries": len(saved["artifacts"])}, indent=2))


if __name__ == "__main__":
    main()
