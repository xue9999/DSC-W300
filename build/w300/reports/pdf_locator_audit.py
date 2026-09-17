"""Reproduce the W300 PDF object/locator audit without executing PDF actions.

This is the retained form of the successful inline pypdf audit. It writes only
the requested derived JSON report; the source PDF is read-only. No USB access.
"""

import argparse
import collections
import hashlib
import json
import re
from pathlib import Path

from pypdf import PdfReader
from pypdf.generic import (
    ArrayObject,
    ByteStringObject,
    DictionaryObject,
    IndirectObject,
    StreamObject,
    TextStringObject,
)


INTERESTING = {
    "/Filespec", "/FileSpec", "/Launch", "/URI", "/JavaScript", "/JS",
    "/EmbeddedFiles", "/EF", "/GoToR", "/GoToE", "/SubmitForm", "/ImportData",
}
# Bounded alternatives prevent excessive backtracking over binary stream data.
LOCATOR_PATTERN = re.compile(
    r"https?://[^\s<>()]{1,250}|"
    r"[A-Za-z0-9_.:/ -]{1,120}\.(?:exe|zip|rar|vbe|vbs|dll|dat)",
    re.I,
)


def serialize_value(obj):
    if isinstance(obj, IndirectObject):
        return {"ref": [obj.idnum, obj.generation]}
    if isinstance(obj, (TextStringObject, ByteStringObject)):
        return str(obj)[:5000]
    if isinstance(obj, ArrayObject):
        return [serialize_value(item) for item in obj]
    if isinstance(obj, DictionaryObject):
        return {
            str(key): serialize_value(value)
            for key, value in obj.items()
            if str(key) not in ["/Parent", "/Kids", "/Resources"]
        }
    if isinstance(obj, (int, float, bool, str)) or obj is None:
        return obj
    return str(obj)


def audit(source):
    reader = PdfReader(source, strict=False)
    hits = []
    s_fields = []
    streams = []
    errors = []
    count = 0

    def walk(obj, location):
        # Every indirect object is inspected separately via the complete xref.
        if isinstance(obj, IndirectObject):
            return
        if isinstance(obj, DictionaryObject):
            if "/S" in obj:
                s_fields.append({"location": location, "action": serialize_value(obj)})
            if any(
                str(key) in INTERESTING
                or (isinstance(value, str) and str(value) in INTERESTING)
                for key, value in obj.items()
            ):
                hits.append({"location": location, "object": serialize_value(obj)})
            if "/F" in obj and isinstance(
                obj["/F"], (str, TextStringObject, ByteStringObject, DictionaryObject)
            ):
                hits.append({"location": location, "file_field": serialize_value(obj["/F"])})
            for key, value in obj.items():
                walk(value, location + str(key))
        elif isinstance(obj, ArrayObject):
            for index, value in enumerate(obj):
                walk(value, location + "/" + str(index))
        elif isinstance(obj, (TextStringObject, ByteStringObject)):
            text = str(obj)
            if LOCATOR_PATTERN.search(text):
                hits.append({"location": location, "string": text[:5000]})

    object_ids = {
        (number, generation)
        for generation, objects in reader.xref.items()
        for number in objects
        if number
    }
    object_ids.update((number, 0) for number in reader.xref_objStm)
    for number, generation in sorted(object_ids):
        try:
            obj = reader.get_object(IndirectObject(number, generation, reader))
            count += 1
            walk(obj, f"{number} {generation} R")
            if isinstance(obj, StreamObject) and obj.get("/Subtype") != "/Image":
                text = obj.get_data().decode("latin1")
                matches = LOCATOR_PATTERN.findall(text)
                if matches:
                    streams.append({"object": [number, generation], "matches": matches[:100]})
        except Exception as exc:
            errors.append({"object": [number, generation], "error": str(exc)})

    # A numeric /S, e.g. in the linearization hint stream, is not an action.
    actions = [entry for entry in s_fields if str(entry["action"].get("/S", "")).startswith("/")]
    non_actions = [entry for entry in s_fields if not str(entry["action"].get("/S", "")).startswith("/")]
    return {
        "source": str(source),
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "pages": len(reader.pages),
        "indirect_objects_inspected": count,
        "action_counts": dict(collections.Counter(str(entry["action"].get("/S")) for entry in actions)),
        "external_reference_hits": hits,
        "non_image_stream_locator_matches": streams,
        "actions": actions,
        "parse_errors": errors,
        "non_action_s_fields": non_actions,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("sources/sony_dsc-w300_adjustment_ver1.3.pdf"))
    parser.add_argument("--output", type=Path, default=Path("build/w300/reports/w300-package-locators.json"))
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        parser.error("Source and output must be different files.")
    result = audit(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=True), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "actions"}, indent=2))
    return 1 if result["parse_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
