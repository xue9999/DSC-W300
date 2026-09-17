# RegionSetting: a concrete comparative route to English

T100 and G3 implement a dedicated RegionSetting service operation with four
32-bit values: region, initial language, available languages and video signal.
This is a concrete candidate for W300 investigation. The W300 implementation
and original-board eligibility remain unverified; no camera command was sent.

## Candidate and its meaning

The shared custom-region mechanism uses region `255`. English is language mask
`0x100`; Japanese is `0x8000`. Candidate arguments `[255, 0x100, 0x8100, 0]`
therefore request English initially, English and Japanese available, and NTSC.
Use the observed original video setting when qualifying a target device.
The encoder [packet.py](packet.py) produces bytes offline and has no USB access.
It deliberately supports only the two independently checked language bits.

An alternative shared predefined choice is region 2 or 3, which selects
`RegionInfo_ENG_2_NT.xml` in both comparison firmwares. Do not infer that W300
destination U2 equals enum 2: the W300 manual establishes U2's English/NTSC
behavior but does not establish the raw enum. The custom candidate avoids that
particular mapping assumption, while still requiring W300 qualification.

## Protocol evidence

The [pinned T100/G3 comparison](../t100-language-comparison/README.md) provides
the extracted source pins and XS decoder. G3 `senserCmdTable.xsb` CODE
`0x79E..0x7BF` and T100 `senserModule.xsb` `0x12406..0x12427` register
`ADJUST_CNTL`, `HOST`, command `0x55`. Both require exactly four arguments;
G3 parsing is `0x7E5..0x829`, T100 `0x12128..0x12172`.

In pinned G3 `PExtSenser.so`, embedded grammar symbol `PExtSenserGrammar`
at VA `0x1C47C` points to CODE VA `0x1B95B`, length 2793. CODE `0x205/0x217`
assigns `0x0040` to ADJUST_CNTL; `0x6A4/0x6B4` assigns `0x3F` to HOST.
Native `handle_input` at `0xE400` divides byte length by four at `0xE4C0`;
callback `0xABC0..0xABF4` loads 32-bit words and converts them to XS integers.
The internal 0x8C-byte FIFO record is not a USB packet.

G3 `libsencore::AdjustControlFunc` at `0xD7F8` reads a four-byte command
prefix: block byte at offset 0 (`0xD858`), command halfword at offset 2
(`0xD868`). `HostCommunicationCommand` at `0xA2A4` copies that prefix and
passes the remaining payload onward. Combine this with the independently
verified [12-byte little-endian Senser header](../g3-host-interface/README.md):

| Field | Value |
|---|---|
| Payload size, uint32 LE | 20, excluding the 12-byte Senser header |
| Function, uint16 LE | `0x40` |
| Sequence, uint16 LE | Current transport sequence, not always zero |
| Four transport flag bytes | Zero in this request vector |
| Block, reserved, command | `3F 00 55 00` |
| Four uint32 LE arguments | `FF`, `100`, `8100`, `0` (hex values) |

Sequence-zero offline vector, 32 bytes:

```text
1400000040000000000000003f005500ff000000000100000081000000000000
```

This specifies the application request, not mode entry, authentication,
USB endpoint selection, transfer padding or a complete host session.

## Application behavior and persistence

Both `regionInfo.xsb` implementations compare region with 255 at CODE
`0x446..0x44C`. Other regions select a predefined XML filename. Arguments
1..3 do not determine that XML but all four arguments are subsequently saved.
Do not use arbitrary placeholders for predefined mode.

Custom mode converts the exact initial-language mask to a name. Availability
0..4 in T100, or 0..5 in G3, selects a predefined group; other values become
group 99 plus a decoded mask. A mask with no recognized languages fails.
Signal must be 0 or 1; actual XML establishes NTSC and PAL respectively.
The helper additionally requires that availability include the initial language.

G3 overrides its broad base region map later: the effective implementation is
installed at CODE `0x1257` and accepts only 0, 2, 3, 4, 5, 7, 9, 12, 13, 14.
T100 supports the broader 0..19 mapping. T100 region 5 selects ENG group 3;
G3 selects group 5. This proves that same-platform region policies can differ.

Region conversion replaces region configuration and deletes user settings
files. G3 deletes `/boot/dsc/UserInfo.xml` and its backup, and the service caller
resets/reinitializes Registry state. It is not a language-only preference edit.
The four category-0 field IDs are `0x40000`, `0x40400`, `0x40800`, `0x40C00`;
DestinationID `0x10400` is separate and is not one of those four explicit writes.
Backing files are `/boot/factory/Hreg.bin` and `/boot/factory/Hreg2.bak`.
An absence of an explicit DestinationID write is not proof of no other effects.

G3 native persistence trace, preserved in [native-trace.txt](native-trace.txt):

- `PExtBackup::xs_backup_flush` calls `Bkup_flush_async` at `0x2964`.
- `libAppBackupApi::Bkup_flush_async` posts an event at `0x3DC8` and returns
  its request ID. Worker vtable slot `0xD5EC` resolves to `postEvent` at `0x45E8`;
  `BackupMessageThread::postMessage` copies/enqueues the event at `0xC760/0xC76C`.
- `BackupWorker::handleMessage` later handles type 5 and calls
  `CommonMethod::flush` at `0x4664`, then invokes its callback at `0x46BC`.
  The region script's `onFlushComplete` body is empty (`0x67C..0x686`).
- `CommonMethod::flush` passes the whole category to `BasicMethod::flush`.
  Thus service success does not establish completed durable persistence.
- `libBackupCore::backupWrite` calls write at `0xAA58`, stores its result,
  calls fsync at `0xAA64`, but evaluates the saved write result. Its returned
  status alone therefore does not establish successful fsync.

## How this becomes a W300 method

The next device session must first identify the original camera and establish
its service transport. Acquire its matching `regionInfo.xsb`, service command
table/module and backup libraries through the qualified file-read route or a
W300 dump. Compare the exact command registration and custom-region branch;
check board restrictions in the actual W300 caller and upstream dispatcher.

Before a write, preserve the original Hreg pair, region XML and UserInfo pair,
and establish a tested restoration method for those files/category. A general
adjustment backup is not yet proven to cover them. Record destination, serial,
calibration baseline and video setting. After the separately authorized write,
read back all four fields and generated configuration, allow persistence to
finish, restart normally, and verify English, Japanese availability, unchanged
identity/calibration and normal camera functions. Inspect the actual saved
files rather than interpreting the immediate service reply as commit success.

Hardware is required for that validation. The offline result is an identified
operation, semantic candidate and reproducible packet vector; persistent English
on the original W300 has not yet been demonstrated.
