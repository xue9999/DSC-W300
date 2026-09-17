"""Recover one complete G3 module from the pinned ext2 image, offline only.

Reuse the repository's ext2 metadata reader, supplying the missing indirect-block
traversal locally. Original parser and preserved extraction are never modified.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
pins = {r["path"]: r for r in json.loads((ROOT / "evidence/artifact_manifest.json").read_text())["artifacts"]}


def preserved(relative):
    data = (ROOT / relative).read_bytes()
    pin = pins[relative]
    assert len(data) == pin["bytes"] and hashlib.sha256(data).hexdigest() == pin["sha256"]
    return data


parser_path = ROOT / "tools/g3_firmware_parser.py"
assert hashlib.sha256(parser_path.read_bytes()).hexdigest() == "34e565247558771d5866f087568f207a6f6efe57392d8f3a267c7c9a56a09987"
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("g3_static_parser", parser_path)
parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser)


class CompleteReader(parser.Ext2Unpacker):
    def block(self, number):
        assert 0 < number < self.blocks_count
        start = number * self.block_size
        assert start + self.block_size <= len(self.data), (number, "outside image")
        return self.data[start:start + self.block_size]

    def pointers(self, number, depth):
        if not number:
            # A null indirect pointer represents an entire sparse subtree.
            yield from (0 for _ in range((self.block_size // 4) ** depth))
        elif depth == 0:
            yield number
        else:
            values = struct.unpack("<%dI" % (self.block_size // 4), self.block(number))
            for value in values:
                yield from self.pointers(value, depth - 1)

    def _read_inode_data(self, mode, size, blocks_raw):
        if mode & 0o170000 == 0o120000 and size <= 60:
            return blocks_raw[:size]
        roots = struct.unpack("<15I", blocks_raw)
        result = bytearray()
        used = []
        for index, number in enumerate(roots):
            depth = max(index - 11, 0)
            for block in self.pointers(number, depth):
                take = min(size - len(result), self.block_size)
                if take <= 0:
                    self.last_blocks = used
                    return bytes(result)
                result.extend(self.block(block)[:take] if block else b"\0" * take)
                used.append({"block": block, "bytes": take, "indirection_depth": depth})
        assert len(result) == size, "inode size not completely covered"
        self.last_blocks = used
        return bytes(result)


relative = "evidence/extracted_g3/archives_unpacked/linuxset1/initrd.img"
image = preserved(relative)
reader = CompleteReader(image)
inode = 2
for part in ("bin", "unified_drv.ko"):
    matches = [entry for entry in reader._walk_dir(inode) if entry[1] == part]
    assert len(matches) == 1, part
    inode = matches[0][0]
mode, _, size, blocks = reader._get_inode(inode)
assert mode & 0o170000 == 0o100000
full = reader._read_inode_data(mode, size, blocks)
used = reader.last_blocks
original_relative = "evidence/extracted_g3/rootfs/initrd/bin/unified_drv.ko"
old = preserved(original_relative)
old_reader = parser.Ext2Unpacker(image)
legacy_result = old_reader._read_inode_data(mode, size, blocks)
assert legacy_result == old, "retained extraction differs from existing parser output"
assert len(old) == (12 + reader.block_size // 4) * reader.block_size
assert len(full) == size and len(full) > len(old) and full.startswith(old)
assert any(row["indirection_depth"] == 2 for row in used)
assert all(row["block"] for row in used), "unexpected sparse block in this exact module"

# Validate the complete ELF's declared sections and each relocation's symbol index.
assert full[:6] == b"\x7fELF\x01\x01"
h = struct.unpack_from("<HHIIIIIHHHHHH", full, 16)
assert h[0] == 1 and h[1] == 40
sections = [struct.unpack_from("<10I", full, h[5] + i * h[10]) for i in range(h[11])]
for section in sections:
    if section[1] != 8:
        assert section[4] + section[5] <= len(full)
relocations = 0
for section in sections:
    if section[1] != 9:
        continue
    symbols = sections[section[6]]
    assert section[9] == 8 and symbols[9] == 16
    for at in range(section[4], section[4] + section[5], 8):
        _, info = struct.unpack_from("<II", full, at)
        assert info >> 8 < symbols[5] // symbols[9]
        relocations += 1

destination = HERE / "unified_drv.complete.ko"
destination.write_bytes(full)
result = {
    "scope": "Read-only reconstruction from actual ext2 data blocks; no firmware/module execution",
    "image": {"path": relative, "sha256": hashlib.sha256(image).hexdigest()},
    "metadata_reader": {"path": "tools/g3_firmware_parser.py", "sha256": hashlib.sha256(parser_path.read_bytes()).hexdigest()},
    "inode": inode, "inode_declared_size": size, "block_size": reader.block_size,
    "preserved_extraction": {"path": original_relative, "bytes": len(old), "sha256": hashlib.sha256(old).hexdigest()},
    "complete_output": {"path": destination.name, "bytes": len(full), "sha256": hashlib.sha256(full).hexdigest()},
    "legacy_parser_output_equals_preserved_extraction": True,
    "complete_output_has_preserved_prefix": True,
    "source_extraction_limit_bytes": (12 + reader.block_size // 4) * reader.block_size,
    "data_blocks": used,
    "all_declared_elf_sections_present": True,
    "validated_relocation_entries": relocations,
    "camera_commands_sent": False,
    "firmware_executed": False,
}
(HERE / "recovery-evidence.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"ok": True, "old_bytes": len(old), "complete_bytes": len(full),
                  "prefix_identical": True, "all_elf_sections_present": True,
                  "relocations": relocations}, indent=2))
