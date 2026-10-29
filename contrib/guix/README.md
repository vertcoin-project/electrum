# Reproducible builds with Guix

`contrib/guix/guix-build` builds the Electrum-VTC releases inside Guix containers.
They come from a fixed Guix commit, the commit's source, and downloads pinned by hash.

| `HOSTS` entry | Output |
|---|---|
| `sdist` | `Electrum-VTC-<version>.tar.gz`: the Python source distribution, with the pure-python dependencies in `packages/` and compiled translations |
| `x86_64-linux-gnu` | `electrum-vtc-<version>-x86_64.AppImage` |
| `x86_64-w64-mingw32` | `electrum-vtc-<version>-setup.exe` (NSIS installer), `electrum-vtc-<version>.exe` (standalone) and `electrum-vtc-<version>-portable.exe` |
| `x86_64-apple-darwin` | `electrum-vtc-<version>-x86_64-macos.zip` (`Electrum-VTC.app`) |
| `arm64-apple-darwin` | `electrum-vtc-<version>-arm64-macos.zip` (`Electrum-VTC.app`) |

```
./contrib/guix/guix-build                       # everything
HOSTS="sdist x86_64-linux-gnu" ./contrib/guix/guix-build
```

Outputs, and a `SHA256SUMS.part` for each host, are written to
`guix-build-<commit>/output/<host>/`. The build is of the committed tree, so commit first.

## Requirements

- Guix (the build uses `guix time-machine`, pinned to the commit in `guix-build`, which is Bitcoin Core v32.0's).
- For the macOS hosts, the Xcode 26.1.1 SDK that Bitcoin Core uses. Download it from
  `https://bitcoincore.org/depends-sources/sdks/Xcode-26.1.1-17B100-extracted-SDK-with-libcxx-headers.tar`
  (sha256 `9600fa93644df674ee916b5e2c8a6ba8dacf631996a65dc922d003b98b5ea3b1`), or extract it from
  `Xcode_26.1.1_Apple_silicon.xip` as described in Bitcoin Core's `contrib/macdeploy`. Then unpack it into a
  directory and pass that as `SDK_PATH`.

## How it works

1. **fetch** (`libexec/fetch.sh`) is the only step with network access. It downloads into `guix-cache/`:
   - the files in `downloads.txt`, each checked against its sha256: python-build-standalone CPython 3.12,
     libsecp256k1 v0.8.0, the AppImage runtime and the PyInstaller 6.13.0 source;
   - Python packages pinned in `contrib/deterministic-build/requirements*.txt`, using `--require-hashes`.
     Sdists come straight from PyPI's JSON API (`libexec/pypi_sdist.py`), so no package code runs while fetching.
2. **build** (`libexec/build.sh`), one container per host, without network:
   - compiles the translations with `msgfmt`;
   - builds every dependency in `requirements.txt` from source as pure python, without optional C
     extensions, as `contrib/make_packages.sh` does;
   - adds the binary wheels upstream Electrum ships too (PyQt6, PyQt6-Qt6, PyQt6-sip, cryptography, cffi);
   - compiles libsecp256k1, and vertcoinhash's `verthash` module, for the target:
     - Linux: Bitcoin Core's GCC 14 targeting glibc 2.31;
     - Windows: its MinGW-w64 toolchain;
     - macOS: clang/lld 19 against the SDK.

     vertcoinhash comes from the `contrib/vertcoinhash` submodule and is built with the sources and flags of
     its `setup.py`, for CPython's stable ABI as its wheels are. `electrum_vtc/verthash.py` then uses its C
     Verthash to check headers, and its C generator to create verthash.dat, instead of the pure-python ones.
3. **packaging**:
   - **AppImage**: CPython, packages and `electrum_vtc/` in an AppDir, packed with `mksquashfs`
     (fixed times, root owned) behind the type2 runtime.
   - **Windows**: the Windows CPython runs under Wine 11. PyInstaller's bootloader is rebuilt from source with
     MinGW-w64 and tagged with the commit, as upstream's `contrib/build-wine` does. Then `contrib/build-wine/pyinstaller.spec`
     makes the standalone, portable and installer exes, and NSIS (`contrib/build-wine/electrum.nsi`) makes the
     installer. The PE checksum is fixed as upstream does.
   - **macOS**: an `Electrum-VTC.app` with the macOS CPython in `Contents/Resources/python` and a launcher script.
     PyInstaller cannot cross-build for macOS, so the bundle is assembled directly. It is not code-signed or
     notarized (the Mach-O binaries keep their ad-hoc signatures), so on first launch macOS asks to confirm opening it.

## Differences from upstream Electrum's builds

- The interpreter is python-build-standalone CPython 3.12.15 everywhere, instead of CPython built from source
  (AppImage), python.org's MSIs (Windows) or python.org's macOS installer.
- Hardware wallet libraries (`requirements-hw.txt`), libusb, zbar and zxing are not bundled.
- The AppImage does not bundle libxcb/libxkbcommon-x11. On X11 the system needs `libxcb-cursor0`, as for any Qt 6 app.
- The AppImage type2 runtime is the pinned upstream release binary, not built from source.
