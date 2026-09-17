# G3 kernel-event to Senif callback bridge

Editorial revision 3; underlying measurements and captured results retain their recorded scope.

This bounded static audit closes the previously missing **event translation** in the retained G3 code. Once the Senser function is registered, created and enabled, kernel event 7 with payload index 0 reaches the registered Senif callback with event value 1. The same route maps payload index 1 to callback value 2. The callback registered by `PExtSenser.so` is `Senser::Extension::active_event_handler`; the preceding normal-entry report already binds value 1 to its `NinThread` startup.

This is conditional native-code evidence for **G3**, not successful USB communication, normal-mode lifecycle qualification, W300 compatibility or a language-setting operation. The upstream application still has to initialize/register/create this function in the relevant mode. The script callback that changes mode after authentication is outside this audit.

## Concrete chain

All library addresses are G3 ELF virtual addresses. Kernel addresses are `.text` offsets in the relocatable module. None is an address for a W300 command.

1. `libusb.so::usb_senif_init` at `0xDC60` saves the caller's callbacks at Senif `+0xC` and saves that Senif pointer at private-state `+0`. The existing `g3-normal-entry` report proves that `PExtSenser.so` supplies table `0x1C540`, whose two relocated entries point to `Extension::active_event_handler` at `0xB504`.
2. The real `usb_senif_user_ops` table at `0x18868` points to `0xDD60`. This registration function calls `usbif_register_gadget` with function ID **11** and callback record `0x18870`; its eight relocated callback entries point to `0xDE64`. It stores the private-state pointer at the returned gadget object's `+0xCC`. `CUsbSvc::new_gadget` dispatches FID 11 through its jump-table entry `0x823C` to `0x8270`, where it constructs `CUsbGadgetSen`.
3. `registerGadget` copies the 40-byte callback record into its registration entry at `+0xC`. Later `CUsbGadget::createGadget` copies that record to the gadget at `+0x94`. Thus gadget callbacks at `+0x9C` and `+0xA0` both resolve to `0xDE64`. The service creation path at `0xA164–0xA184` enables events for that gadget handle before calling its creation method. This is a conditional code path, not proof that the application enters it in normal MSC mode.
4. `CUsbGadgetSen::on_create` builds the `0x4034E000` probe structure. Its first word is the gadget pointer/handle; the word at `+0x20` is the callback pointer obtained through GOT `0x19060`, whose `R_ARM_GLOB_DAT` target is `CUsbGadgetSen::proc_kevent` at `0xCEC0`. The retained complete kernel module preserves these fields when it copies the probe structure. Its matched-request path loads the handle from `+0` and callback from `+0x20`, then calls `usb_event_add_queue` with event **7**, size **4**, and matched setup-pattern index **0** or **1**. The exact setup patterns were established in `g3-usb-descriptor`.
5. Published G3 GPL `usb_event.c` shows the queue layout: 32-bit handle, 32-bit callback, one-byte event ID, one-byte payload size, alignment to four bytes, then payload and trailing alignment. For this event the header is 12 bytes and payload is four bytes. It only queues to an opened event device with an enabled handle. `usb_event_read` copies queued bytes to userspace. These source semantics corroborate the ABI; this audit does not equate the published source byte-for-byte with the running kernel.
6. Actual `libusb.so::usb_event_start` opens **`/dev/usb/event`** and creates a thread at `0xA82C`. The thread calls `read`, parses the queue header and invokes the recovered callback at `0xAC74`, with `r0=handle`, `r1=event ID`, `r2=payload size`, `r3=payload pointer`. These field offsets agree with the published ABI.
7. `CUsbGadgetSen::proc_kevent` requires event **7** and payload size **4**. Payload value **0** loads callback `gadget+0x9C` and passes gadget event **2**. Payload value **1** loads callback `gadget+0xA0` and passes gadget event **3**. The function also routes kernel event 1 through the latter branch; qualify the matching host-side exit sequence from its full transaction flow.
8. The callback at `0xDE64` follows gadget `+0xCC` to the private state, then its first word to the Senif object and `Senif+0xC` to the actual callbacks. Gadget event **2** selects callback slot 0 and supplies **Senif event 1**, plus the I/O table at `0x18898`, length **16**. Gadget event **3** selects callback slot 1 and supplies **Senif event 2**, reusing the I/O table saved at Senif `+8`. The final callback invocation is at `0xDF64`.

| Kernel event | Four-byte payload | Gadget event | Senif callback event |
|---:|---:|---:|---:|
| 7 | 0 (StartSenser pattern) | 2 | 1 |
| 7 | 1 (StopSenser pattern) | 3 | 2 |

The chain therefore supplies concrete intermediate dispatch links to the already identified product-zero `Extension` object. It does not prove the full first-stage authentication exchange or subsequent re-enumeration.

## Inputs, checks and reproduction

`reproduce_events.py` reads the retained `libusb.so` and `PExtSenser.so` using the existing manifest-pinned ELF reader. It checks relocations, actual callback pointers, function-ID dispatch, selected instruction words, queue thread target/path and callback argument flow. It independently checks the relevant words in the hash-pinned complete recovered module `g3-module-recovery/unified_drv.complete.ko`. That module was reconstructed from the existing retained filesystem image; it is not a newly acquired Sony payload.

The GPL queue sources were extracted from the already pinned official G3 kernel archive by `prepare_event_source.py`. Their sizes/hashes are retained in `gpl-event-source.json`. No download, firmware execution, kernel installation or USB operation is performed by the replay.

Run from the repository root:

```powershell
& '.\build\w300\venv\Scripts\python.exe' '.\build\w300\reports\g3-entry-events\reproduce_events.py'
```

The script completed successfully and prints `ok: true`, the two event translations and `w300_qualified: false`. It writes `event-evidence.json` and the bounded final disassembly `event-chain.asm.txt`. `inspect_events.py` and the other selected listings support exploration; the final replay is the authoritative bounded check for this report. One initial checker run failed because a hand-transcribed ARM `mov r3,#7` word had its register nibble in the wrong place; correcting the expected word to the actual decoded instruction resolved that analysis-script error. No firmware bytes were changed.

## Remaining boundary

Still unproven: the application/mode lifecycle that makes the Senser function active during ordinary G3 mass-storage operation, the script action after `onComplete`, the full live authentication exchange, normal-mode return and all corresponding proprietary behavior in W300. This evidence reduces a specific G3 protocol-analysis gap. It does not create or authorize an operational W300 service/write adapter, supply destination bytes, resolve original-board eligibility or establish recovery.
