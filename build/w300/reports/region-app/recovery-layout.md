# Native regional-settings restoration

The app's v2 restoration uses the original four RegionSetting arguments through
the native command. It does not overwrite Hreg or UserInfo files. RegionSetting
resets preferences on both the forward change and restoration, so this is not a
complete preference rollback. Hardware recovery has not been demonstrated.

## File layout and completion markers

Pinned G3 `libBackupCore.so` `FileAccesser::getHeaderSize` at VA `0x8610`
returns zero for category 0 (store at `0x8634`). Read/write add that header size
to category offsets at `0x85F8..0x8600` / `0x8578..0x8580`. Therefore the known
G3 Hreg field offsets are physical file offsets `0x400`, `0x404`, `0x408`, `0x40C`.
T100's corresponding helper at `0x739C` is byte-identical.

`FileAccesserMeasures2BattOff::getDataOffset` at `0x8C58` selects completion-marker
offset `0x1F0` for category 0 at `0x8C94`. This helper names a marker position,
not an added file header. T100's helper at `0x7AAC` is byte-identical. Both retained
factory Hreg files are 2048 bytes and contain marker `0xAAAAAAAA`.

`read` at `0x8810` chooses primary when that marker is valid, otherwise spare.
`writeUser` at `0x895C` checks primary at `0x89A0..0x89A8`. With valid primary,
it writes spare at `0x89DC`, then primary at `0x8A2C`. With invalid primary, it
writes **only primary** at `0x8A7C`. `writeSafely` at `0x8AA8` clears the marker
at `0x8B24`, writes data at `0x8BC4`, then writes `0xAAAAAAAA` at `0x8C1C`.

Accordingly, the automatic path requires equal, complete original banks. A
restoration after an invalid-primary save is refused unless the spare already
exactly equals the original bank. Otherwise one native write cannot restore both
banks; the app does not silently send another. Valid-primary/invalid-spare follows
the native spare-first branch. These are static behavior constraints, not proof
of a completed physical recovery.

## Why there is no raw-file automatic rollback

G3 `libsencore` FileControl command 1 passes flags `0x1241` at `0xEEB0` and
constructs WriteDeviceData at `0xEEB8`: write-only, create, truncate, synchronous.
The constructor opens at `0xBBC4` before payload reception. Interruption can leave
a truncated file. `WriteDeviceData::Advance` at `0xAE54` loops writes at `0xAE90`,
does not handle zero progress, calls fsync at `0xAEC0`, then returns 1 without
propagating fsync failure. It bypasses BackupCore's live RAM shadow.

Native RegionSetting restoration uses the same shadow/write/flush path as the
forward operation. Immediate command success still does not prove durability;
both completion markers, field values, unrelated bytes, regional XML, stable
repeat reads, normal-mode return and a subsequent normal restart remain separate
checks.

## Reproduction and applicability

Run `inspect_recovery.py` from the repository environment. It checks the preserved
source pins, emits `recovery-native.txt`, and asserts both layout helpers are
byte-identical between retained G3 and T100 libraries. The automatic app currently
requires complete component hashes belonging to one coherent reference family.
These offsets are never approved from model name or field-name strings alone.
The T100 component collection lacks G3's separate `libsencore.so`, so it is an
informational partial reference, not an independently enabled full transport
profile. An actual W300 mismatch needs analysis before extending the reference.
