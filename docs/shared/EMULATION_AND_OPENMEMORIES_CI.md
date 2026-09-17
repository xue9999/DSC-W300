# Emulation, optional upstreams and native probes

## Availability and pinned sources

```sh
python tools/cxd4108_emulator/qemu_launcher.py status
```

The status distinguishes source availability, pinned commits, executable availability and extracted evidence. Empty submodule directories are not cloned dependencies. Record observed boot results as a separate qualification milestone.

Optional source dependencies are pinned by Git and `.gitmodules`. To acquire them explicitly, use `git submodule update --init`; do not use `--remote` as a setup shortcut. Inspect upstream build instructions at the pinned revision before building QEMU. The required machine is the custom `cxd4108`, not merely any `qemu-system-arm` executable.

The launcher can print arguments for G3, W90 and T100. It does not provide a W300 hardware qualification. Flash/partition builders assemble local images; the factory-data helper creates synthetic emulator fixtures. Its byte labels and zero-filled templates are not device calibration data and must not be deployed to hardware.

## Native probe source

The following are macOS build examples, not commands to access a camera:

```sh
mkdir -p build
clang -fobjc-arc -framework Foundation -framework IOKit -framework IOUSBHost tools/w300_native_probe.m -o build/w300_native_probe
cc tools/w300_capture_inquiry.c $(pkg-config --cflags --libs libusb-1.0) -o build/w300_capture_inquiry
```

The first requires the matching macOS SDK; the second requires libusb development files and pkg-config. Builds have not been validated by the Windows cleanup. Their source opens USB interfaces and may transfer standard inquiry packets or change driver ownership. They are not equivalent to passive `ioreg` inventory and are not run by tests.

The Python transport probe is retained only as an unsupported entry point and a descriptor parser after removal of the unqualified service transport. Consult its explicit refusal message; do not interpret it as a successful hardware probe.

Ghidra binaries and local compiled programs are not retained in Git. Install a suitable tool separately if a later research task requires it.
