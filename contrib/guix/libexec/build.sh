#!/usr/bin/env bash
# Runs inside the Guix container, with no network access: builds the release
# for $HOST from the source archive and what fetch.sh downloaded, and writes it
# and its SHA256SUMS.part to /outdir.
#
# Every release bundles a python-build-standalone CPython 3.12, Electrum-VTC's
# pure-python dependencies built here from their (hash-pinned) source, the
# binary wheels upstream Electrum also ships (PyQt6, cryptography, cffi), and a
# libsecp256k1 and vertcoinhash's verthash module compiled here for the target.
export LC_ALL=C
export TZ=UTC
set -o errexit -o pipefail -o nounset
umask 0022

: "${HOST:?}" "${NAME:?}" "${COMMIT:?}" "${SOURCE_DATE_EPOCH:?}" "${SRC_TAR:?}" "${JOBS:?}"
export SOURCE_DATE_EPOCH
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1
export PIP_NO_INDEX=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 PIP_NO_WARN_SCRIPT_LOCATION=1
export HOME=/tmp/home
mkdir -p "$HOME"

DL=/cache/dl
PIP=/cache/pip
REQS="python3 /libexec/reqs.py"
PY_MAJOR=3.12
PBS="cpython-3.12.15+20261021"
SECP_COMMIT=6e2c8bc4ecdc6e71dbe7a368f360d8d453ce435d
BINARIES=cffi,cryptography,pycparser,PyQt6,PyQt6-Qt6,PyQt6-sip

# Given a package name and an output name, return the path of that output in
# the container's profile (from Bitcoin Core's contrib/guix/libexec/prelude.bash)
store_path() {
    grep --extended-regexp "/[^-]{32}-${1}-[^-]+${2:+-${2}}" "${GUIX_ENVIRONMENT}/manifest" \
        | head --lines=1 \
        | sed --expression='s|\x29*$||' \
              --expression='s|^[[:space:]]*"||' \
              --expression='s|"[[:space:]]*$||'
}

# Point the cross compiler at its own libc and nothing else
cross_paths() {
    local libc="$1" kernel="${2:-}" gcc_lib_store gcc_libs gcc_lib
    gcc_lib_store="$(store_path "gcc-cross-${HOST}" lib)"
    gcc_libs=( "${gcc_lib_store}/lib/gcc/${HOST}"/* )
    gcc_lib="${gcc_libs[0]}"
    export CROSS_C_INCLUDE_PATH="${gcc_lib}/include:${gcc_lib}/include-fixed:${libc}/include${kernel:+:${kernel}/include}"
    export CROSS_LIBRARY_PATH="${gcc_lib_store}/lib:${gcc_lib}:${libc}/lib"
    unset LIBRARY_PATH CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH CROSS_CPLUS_INCLUDE_PATH
    # Guix's ld wrapper otherwise adds an RPATH entry for every -L, pointing
    # the binary at /gnu/store
    export GUIX_LD_WRAPPER_DISABLE_RPATH=yes
}

# Set every file's time, so archives record no build time
normalize_times() {
    find "$@" -exec touch --no-dereference --date="@${SOURCE_DATE_EPOCH}" {} +
}

tar -xf "$SRC_TAR" -C /distsrc
SRC=/distsrc/src
cd "$SRC"
REQ=contrib/deterministic-build

echo "== translations"
rm -rf electrum_vtc/locale/llm_proofreader
for po in electrum_vtc/locale/locale/*/electrum.po; do
    dir="$(dirname "$po")/LC_MESSAGES"
    mkdir -p "$dir"
    # as contrib/locale/build_locale.sh, a language that does not compile is left out
    msgfmt --output-file="$dir/electrum.mo" "$po" || { echo "WARN: skipping $po"; rm -f "$dir/electrum.mo"; }
done

echo "== pure-python packages"
# The build backends, then every dependency in requirements.txt built from
# source without its optional C extensions, as in contrib/make_packages.sh
python3 -m venv /tmp/hostpy
HPY=/tmp/hostpy/bin/python
$REQS "$REQ/requirements-build-base.txt" > /tmp/req-build-base.txt
$HPY -m pip install --quiet --no-deps --require-hashes --only-binary :all: \
    --find-links "$PIP/build" -r /tmp/req-build-base.txt
export AIOHTTP_NO_EXTENSIONS=1 YARL_NO_EXTENSIONS=1 MULTIDICT_NO_EXTENSIONS=1 \
       FROZENLIST_NO_EXTENSIONS=1 PROPCACHE_NO_EXTENSIONS=1 ELECTRUM_ECC_DONT_COMPILE=1
$REQS "$REQ/requirements.txt" --exclude pip,setuptools,wheel > /tmp/req-runtime.txt
$HPY -m pip wheel --quiet --no-deps --no-build-isolation --no-binary :all: --require-hashes \
    --find-links "$PIP/sdist" -r /tmp/req-runtime.txt -w /tmp/wheels-pure
for whl in /tmp/wheels-pure/*.whl; do
    case "$(basename "$whl")" in
        *-py3-none-any.whl|*-py2.py3-none-any.whl) ;;
        *) echo "ERR: $(basename "$whl") is not pure-python" >&2; exit 1 ;;
    esac
done
sha256sum /tmp/wheels-pure/*.whl

# install_packages SITE_PACKAGES PIP_PLATFORM...: the pure-python packages and
# the binary wheels for that platform
install_packages() {
    local site="$1" p platforms=()
    shift
    for p in "$@"; do platforms+=(--platform "$p"); done
    mkdir -p "$site"
    $HPY -m pip install --quiet --no-deps --no-compile --target "$site" /tmp/wheels-pure/*.whl
    $REQS "$REQ/requirements-binaries.txt" --only "$BINARIES" > /tmp/req-binaries.txt
    $HPY -m pip install --quiet --no-deps --no-compile --require-hashes --only-binary :all: \
        "${platforms[@]}" --python-version 3.12 --implementation cp --abi cp312 --abi abi3 --abi none \
        --find-links "$PIP/$HOST" --target "$site" -r /tmp/req-binaries.txt
    # console scripts, with this build's interpreter in their #! line
    rm -rf "$site/bin"
}

# install_electrum SITE_PACKAGES LIBSECP VERTHASH_MODULE: the electrum_vtc
# package, compiled translations only, libsecp256k1 next to electrum_ecc, which
# loads it from its own directory, and the verthash module
install_electrum() {
    local site="$1" lib="$2" verthash="$3"
    cp -a "$SRC/electrum_vtc" "$site/"
    find "$site/electrum_vtc/locale" -type f ! -name '*.mo' -delete
    find "$site/electrum_vtc/locale" -depth -type d -empty -delete
    rm -f "$site"/electrum_vtc/*.dll "$site"/electrum_vtc/*.so* "$site"/electrum_vtc/*.dylib
    cp "$lib" "$site/electrum_ecc/"
    cp "$verthash" "$site/"
}

# Unused parts of the interpreter and of Qt, as contrib/build-linux/appimage/make_appimage.sh removes
# prune_python PYTHON_LIB_DIR(lib/python3.12 or Lib) QT_DIR(PyQt6/Qt6) QTLIB_GLOB
prune_python() {
    local pydir="$1" site="$2"
    rm -rf "$pydir"/{test,ensurepip,lib2to3,idlelib,turtledemo,tkinter}
    rm -rf "$pydir"/{ctypes,sqlite3,unittest}/test
    rm -rf "$pydir"/config-3.*
    rm -rf "$site"/{pip,setuptools,wheel,_distutils_hack}* "$site"/distutils-precedence.pth
    rm -rf "$site"/qrcode/tests
    local qt="$site/PyQt6/Qt6" component
    for component in connectivity declarative help location multimedia quickcontrols2 serialport webengine websockets xmlpatterns ; do
        rm -rf "$qt"/translations/qt${component}_* "$qt"/resources/qt${component}_*
    done
    rm -rf "$qt"/{qml,libexec}
    rm -rf "$site"/PyQt6/{pyrcc*,pylupdate*,uic}
    rm -rf "$qt"/plugins/{bearer,gamepads,geometryloaders,geoservices,playlistformats,position,renderplugins,sceneparsers,sensors,sqldrivers,texttospeech,webview}
    for component in Bluetooth Designer Help Location NetworkAuth Nfc Positioning PositioningQuick Sensors SerialPort Sql Test Web Xml Labs ShaderTools SpatialAudio ; do
        rm -rf "$qt"/lib/libQt6${component}* "$qt"/lib/Qt${component}.framework "$qt"/bin/Qt6${component}*.dll
        rm -rf "$site"/PyQt6/Qt${component}* "$site"/PyQt6/bindings/Qt${component}*
    done
    for component in Concurrent Qml Quick ; do
        rm -rf "$site"/PyQt6/Qt${component}* "$site"/PyQt6/bindings/Qt${component}*
    done
    rm -rf "$site"/PyQt6/Qt.{so,pyd,abi3.so}
    find "$pydir" -depth -name __pycache__ -type d -exec rm -rf {} +
}

# build_secp CONFIGURE_HOST [configure arguments]: libsecp256k1 as
# contrib/make_libsecp256k1.sh builds it; sets SECP_LIB to the library
build_secp() {
    local conf_host="$1"
    shift
    rm -rf /tmp/secp
    mkdir -p /tmp/secp
    tar -xzf "$DL/secp256k1-${SECP_COMMIT}.tar.gz" -C /tmp/secp --strip-components=1
    (
        cd /tmp/secp
        echo "LDFLAGS = -no-undefined" >> Makefile.am
        ./autogen.sh > /dev/null 2>&1
        ./configure --quiet --host="$conf_host" --prefix=/tmp/secp/dist \
            --enable-module-recovery --enable-module-extrakeys --enable-module-schnorrsig \
            --enable-experimental --enable-module-ecdh --disable-benchmark --disable-tests \
            --disable-exhaustive-tests --disable-static --enable-shared "$@"
        make -j"$JOBS" > /dev/null
        make install > /dev/null
    )
    local dlname
    dlname="$(sed -n "s/^dlname='\(.*\)'$/\1/p" /tmp/secp/dist/lib/libsecp256k1.la)"
    SECP_LIB="/tmp/secp/$(basename "$dlname")"
    cp -L "/tmp/secp/dist/lib/$dlname" "$SECP_LIB"
    echo "built $(basename "$SECP_LIB")"
}

# build_vertcoinhash CC CFLAGS SUFFIX LINK...: vertcoinhash's verthash module
# (its C Verthash and verthash.dat generator, which electrum_vtc/verthash.py
# uses when it imports) from the contrib/vertcoinhash submodule, with the
# sources and flags of its setup.py, against the stable ABI as its wheels are;
# sets VERTHASH_MOD to the module. Needs extract_python's headers in /tmp/pbs.
VERTHASH_SOURCES="scrypt.c Lyra2RE.c Sponge.c Lyra2.c sha3/blake.c sha3/groestl.c sha3/keccak.c
                  sha3/cubehash.c sha3/bmw.c sha3/skein.c h2.c tiny_sha3/sha3.c
                  verthashmodule.c verthash_datfile.c"
build_vertcoinhash() {
    local cc="$1" cflags="$2" suffix="$3" src obj objs=()
    shift 3
    rm -rf /tmp/vertcoinhash
    mkdir -p /tmp/vertcoinhash
    for src in $VERTHASH_SOURCES; do
        obj="/tmp/vertcoinhash/$(echo "$src" | tr / _).o"
        # shellcheck disable=SC2086
        (cd "$SRC/contrib/vertcoinhash" && $cc -O3 -fno-strict-aliasing -std=c99 -DNDEBUG \
            -DPy_LIMITED_API=0x030B0000 -I. -I./sha3 -I./tiny_sha3 \
            -ffile-prefix-map="$SRC/contrib/vertcoinhash"=. $cflags -c "$src" -o "$obj")
        objs+=("$obj")
    done
    VERTHASH_MOD="/tmp/vertcoinhash/verthash${suffix}"
    # shellcheck disable=SC2086
    $cc "$@" -o "$VERTHASH_MOD" "${objs[@]}"
    echo "built $(basename "$VERTHASH_MOD")"
}

# check_elf FILE: it needs only libraries every glibc system has, nothing newer
# than glibc 2.31, and has no search path
check_elf() {
    local needed newest lib
    needed="$("${HOST}-readelf" -d "$1" | sed -n 's/.*(NEEDED).*\[\(.*\)\]/\1/p' | tr '\n' ' ')"
    for lib in $needed; do
        case "$lib" in
            libc.so.6|libm.so.6|libgcc_s.so.1|ld-linux-x86-64.so.2) ;;
            *) echo "ERR: $(basename "$1") needs $lib" >&2; exit 1 ;;
        esac
    done
    if "${HOST}-readelf" -d "$1" | grep -E 'RPATH|RUNPATH'; then echo "ERR: search path in $1" >&2; exit 1; fi
    newest="$("${HOST}-readelf" -V --wide "$1" | grep -o 'GLIBC_[0-9.]*' | sort -uV | tail -1)"
    printf '%s\n' "$newest" GLIBC_2.31 | sort -CV || { echo "ERR: $(basename "$1") needs $newest" >&2; exit 1; }
    echo "$(basename "$1"): needs $needed, newest symbol $newest"
}

# extract_python TARBALL DEST: python-build-standalone's install_only layout is python/...
extract_python() {
    rm -rf /tmp/pbs
    mkdir -p /tmp/pbs "$2"
    tar -xzf "$DL/$1" -C /tmp/pbs
    cp -a /tmp/pbs/python/. "$2/"
}

mkdir -p /outdir
case "$HOST" in
    sdist)
        echo "== sdist"
        # as contrib/build-linux/sdist/make_sdist.sh: pure-python dependencies
        # bundled in packages/, source and compiled translations included
        $HPY -m pip install --quiet --no-deps --no-compile --target packages /tmp/wheels-pure/*.whl
        rm -rf packages/bin
        normalize_times .
        $HPY setup.py --quiet sdist --format=gztar --dist-dir=/tmp/sdist1
        # setuptools' tar.gz is not reproducible; repack it
        mkdir -p /tmp/sdist2
        tar -xzf /tmp/sdist1/*.tar.gz -C /tmp/sdist2
        mv /tmp/sdist2/* "/tmp/sdist2/Electrum-VTC-${NAME}"
        normalize_times /tmp/sdist2
        out="Electrum-VTC-${NAME}.tar.gz"
        tar --sort=name --owner=0 --group=0 --numeric-owner --mode='u+rw,go+r-w,a+X' \
            -C /tmp/sdist2 -cf - "Electrum-VTC-${NAME}" | gzip -9n > "/outdir/$out"
        outputs=("$out")
        ;;

    x86_64-linux-gnu)
        echo "== libsecp256k1 ($HOST)"
        cross_paths "$(store_path "glibc-cross-${HOST}")" "$(store_path "linux-libre-headers-cross-${HOST}")"
        build_secp "$HOST" CC="${HOST}-gcc"
        "${HOST}-strip" -R .note.gnu.build-id -R .comment "$SECP_LIB"
        check_elf "$SECP_LIB"

        echo "== AppDir"
        APPDIR=/tmp/Electrum-VTC.AppDir
        extract_python "${PBS}-x86_64-unknown-linux-gnu-install_only.tar.gz" "$APPDIR/usr"

        echo "== vertcoinhash's verthash module ($HOST)"
        build_vertcoinhash "${HOST}-gcc" "-fPIC -I/tmp/pbs/python/include/python${PY_MAJOR}" .abi3.so \
            -shared -Wl,-O1 -Wl,--as-needed -Wl,-z,relro -Wl,-z,now
        "${HOST}-strip" --strip-unneeded -R .note.gnu.build-id -R .comment "$VERTHASH_MOD"
        check_elf "$VERTHASH_MOD"

        site="$APPDIR/usr/lib/python${PY_MAJOR}/site-packages"
        install_packages "$site" manylinux_2_28_x86_64 manylinux_2_17_x86_64 manylinux2014_x86_64
        install_electrum "$site" "$SECP_LIB" "$VERTHASH_MOD"
        cp run_electrum "$APPDIR/usr/bin/electrum-vtc"
        cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
APPDIR="$(dirname "$(readlink -f "$0")")"
exec "${APPDIR}/usr/bin/python3" -s "${APPDIR}/usr/bin/electrum-vtc" "$@"
EOF
        chmod 0755 "$APPDIR/AppRun" "$APPDIR/usr/bin/electrum-vtc"
        cp electrum-vtc.desktop "$APPDIR/electrum-vtc.desktop"
        cp electrum_vtc/gui/icons/electrum.png "$APPDIR/electrum.png"
        ln -s electrum.png "$APPDIR/.DirIcon"
        prune_python "$APPDIR/usr/lib/python${PY_MAJOR}" "$site"
        rm -rf "$APPDIR"/usr/{include,share} "$APPDIR"/usr/lib/{libtcl*,libtk*,tcl*,tk*,itcl*,thread*,pkgconfig}
        normalize_times "$APPDIR"

        echo "== AppImage"
        out="electrum-vtc-${NAME}-x86_64.AppImage"
        # mksquashfs takes the filesystem and file times from SOURCE_DATE_EPOCH
        mksquashfs "$APPDIR" /tmp/app.squashfs -quiet -no-progress -noappend -root-owned -no-xattrs \
            -comp zstd -Xcompression-level 19 -b 1M -processors "$JOBS"
        cat "$DL/runtime-x86_64" /tmp/app.squashfs > "/outdir/$out"
        chmod 0755 "/outdir/$out"
        outputs=("$out")
        ;;

    x86_64-w64-mingw32)
        echo "== libsecp256k1 ($HOST)"
        cross_paths "$(store_path mingw-w64-x86_64-winpthreads)"
        build_secp "$HOST" CC="${HOST}-gcc" LDFLAGS="-Wl,--no-insert-timestamp"
        "${HOST}-strip" "$SECP_LIB"

        echo "== Windows Python, under Wine"
        export WINEPREFIX=/tmp/wine WINEDEBUG=-all WINEDLLOVERRIDES="mscoree,mshtml=" WINEARCH=win64
        unset DISPLAY
        wineboot --init > /dev/null 2>&1 || true
        wineserver --wait || true
        PYHOME="$WINEPREFIX/drive_c/python3"
        extract_python "${PBS}-x86_64-pc-windows-msvc-install_only.tar.gz" "$PYHOME"
        WINEPY=(wine "$PYHOME/python.exe" -B)
        "${WINEPY[@]}" -c "import sys; print('Windows', sys.version)"

        echo "== vertcoinhash's verthash module ($HOST)"
        # MS_WIN64: Python's Windows pyconfig.h only sets 64-bit sizes for MSVC otherwise.
        # Linking python3.dll, the stable ABI's DLL, as vertcoinhash's wheel does.
        build_vertcoinhash "${HOST}-gcc" "-DMS_WIN64 -I/tmp/pbs/python/include" .pyd \
            -shared -static-libgcc -Wl,--no-insert-timestamp -L/tmp/pbs/python -lpython3
        "${HOST}-strip" --strip-unneeded "$VERTHASH_MOD"
        echo "$(basename "$VERTHASH_MOD"): imports $("${HOST}-objdump" -p "$VERTHASH_MOD" | sed -n 's/^\s*DLL Name: //p' | tr '\n' ' ')"
        "${WINEPY[@]}" -c "import sys; sys.path.insert(0, r'Z:/tmp/vertcoinhash'); import verthash; print('imports', verthash.__file__, hasattr(verthash, 'create_datafile'))"

        echo "== PyInstaller, with its bootloader built from source"
        # as contrib/build-wine/prepare-wine.sh: our own bootloader, tagged with
        # the commit, so each release's differs from the stock one
        rm -rf /tmp/pyinstaller
        mkdir -p /tmp/pyinstaller
        tar -xzf "$DL/pyinstaller-6.13.0.tar.gz" -C /tmp/pyinstaller --strip-components=1
        rm -fv /tmp/pyinstaller/PyInstaller/bootloader/Windows-*/run*.exe
        echo "const char *electrum_tag = \"tagged by Electrum-VTC@${COMMIT}\";" >> /tmp/pyinstaller/bootloader/src/pyi_main.c
        (
            cd /tmp/pyinstaller/bootloader
            CC="${HOST}-gcc" AR="${HOST}-ar" WINRC="${HOST}-windres" STRIP="${HOST}-strip" \
            CFLAGS="-static" LDFLAGS="-Wl,--no-insert-timestamp" \
                python3 ./waf all > /tmp/waf.log 2>&1 \
                || { tail -40 /tmp/waf.log; exit 1; }
        )
        [ -e /tmp/pyinstaller/PyInstaller/bootloader/Windows-64bit-intel/runw.exe ] || { echo "ERR: no runw.exe" >&2; exit 1; }
        # its dependencies, and the setuptools/wheel it builds with, are pure
        # python: build them here from source, then install them under Wine
        $REQS "$REQ/requirements-build-wine.txt" --exclude pip > /tmp/req-build-wine.txt
        $HPY -m pip wheel --quiet --no-deps --no-build-isolation --no-binary :all: --require-hashes \
            --find-links "$PIP/sdist-wine" -r /tmp/req-build-wine.txt -w /tmp/wheels-wine
        "${WINEPY[@]}" -m pip install --quiet --no-deps --no-index $(for w in /tmp/wheels-wine/*.whl; do echo "Z:$w"; done)
        "${WINEPY[@]}" -m pip install --quiet --no-deps --no-build-isolation --no-index "Z:/tmp/pyinstaller"

        echo "== Electrum-VTC and its dependencies"
        site="$PYHOME/Lib/site-packages"
        install_packages "$site" win_amd64
        install_electrum "$site" "$SECP_LIB" "$VERTHASH_MOD"
        PROJECT="$WINEPREFIX/drive_c/electrum"
        cp -a "$SRC" "$PROJECT"
        cp "$SECP_LIB" "$PROJECT/electrum_vtc/"
        # no prune_python here: PyInstaller only bundles what is imported, and
        # pkg_resources, which the spec bundles, loads its vendored packages
        # (jaraco, ...) from setuptools/_vendor

        echo "== pyinstaller"
        (
            cd "$PROJECT/contrib/build-wine"
            ELECTRUM_CMDLINE_NAME="electrum-vtc-${NAME}" ELECTRUM_PROJECT_ROOT="C:/electrum" \
                "${WINEPY[@]}" -m PyInstaller --noconfirm --clean --log-level WARN pyinstaller.spec
            normalize_times dist
            echo "== NSIS installer"
            makensis -V2 -DPRODUCT_VERSION="${NAME}" electrum.nsi
            mv dist/electrum-vtc-setup.exe "dist/electrum-vtc-${NAME}-setup.exe"
        )
        outputs=("electrum-vtc-${NAME}-setup.exe" "electrum-vtc-${NAME}.exe" "electrum-vtc-${NAME}-portable.exe")
        for exe in "${outputs[@]}"; do
            # dist/electrum_vtc/ is the installer's one-folder app, whose exe has
            # the standalone one's name; the standalone and portable ones are onefile
            src="$(find "$PROJECT/contrib/build-wine/dist" -name "$exe" -type f -not -path '*/dist/electrum_vtc/*' | head -1)"
            [ -n "$src" ] || { echo "ERR: pyinstaller made no $exe" >&2; find "$PROJECT/contrib/build-wine/dist" -name '*.exe' >&2; exit 1; }
            # pad to 8 bytes and fix the PE checksum, as build-electrum-git.sh does,
            # so a signature can later be attached and detached reproducibly
            python3 - "$src" "/outdir/$exe" <<'EOF'
import sys
src, dst = sys.argv[1:]
binary = bytearray(open(src, 'rb').read())
pe_offset = int.from_bytes(binary[0x3c:0x3c+4], byteorder="little")
checksum_offset = pe_offset + 88
binary += bytes(8 - len(binary) % 8)
checksum = 0
for i in range(len(binary) // 4):
    if i == checksum_offset // 4:
        continue
    dword = int.from_bytes(binary[i*4:i*4+4], byteorder="little")
    checksum = (checksum & 0xffffffff) + dword + (checksum >> 32)
    if checksum > 2 ** 32:
        checksum = (checksum & 0xffffffff) + (checksum >> 32)
checksum = (checksum & 0xffff) + (checksum >> 16)
checksum = (checksum) + (checksum >> 16)
checksum = checksum & 0xffff
checksum += len(binary)
binary[checksum_offset:checksum_offset+4] = int.to_bytes(checksum, length=4, byteorder="little")
open(dst, 'wb').write(binary)
EOF
        done
        ;;

    *-apple-darwin)
        case "$HOST" in
            x86_64-apple-darwin) arch=x86_64; conf_host=x86_64-apple-darwin; platform=macosx_11_0_x86_64 ;;
            arm64-apple-darwin)  arch=arm64;  conf_host=aarch64-apple-darwin; platform=macosx_11_0_arm64 ;;
        esac
        echo "== libsecp256k1 ($HOST)"
        # only the SDK's headers and libraries, none of the profile's
        unset LIBRARY_PATH CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH OBJC_INCLUDE_PATH OBJCPLUS_INCLUDE_PATH
        # -fuse-ld is in CC because libtool drops it from LDFLAGS when linking the dylib,
        # and LD is set so libtool does not take the profile's GNU ld for the linker
        darwin_cc="clang --target=${arch}-apple-macos11 -mmacos-version-min=11.0 -isysroot /sdk -nostdlibinc -iwithsysroot/usr/include -iframeworkwithsysroot/System/Library/Frameworks -fuse-ld=lld"
        # lld signs arm64 binaries ad hoc, which macOS requires; strip would break that
        build_secp "$conf_host" CC="$darwin_cc" \
            LD=ld64.lld AR=llvm-ar RANLIB=llvm-ranlib NM=llvm-nm STRIP=true OTOOL=llvm-otool LIPO=llvm-lipo NMEDIT=true DSYMUTIL=true
        llvm-objdump --macho --private-headers "$SECP_LIB" | grep -A3 -E 'LC_BUILD_VERSION|LC_CODE_SIGNATURE' | head -12

        echo "== Electrum-VTC.app"
        APP=/tmp/mac/Electrum-VTC.app
        mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
        extract_python "${PBS}-${conf_host}-install_only.tar.gz" "$APP/Contents/Resources/python"

        echo "== vertcoinhash's verthash module ($HOST)"
        build_vertcoinhash "$darwin_cc" "-I/tmp/pbs/python/include/python${PY_MAJOR}" .abi3.so \
            -bundle -undefined dynamic_lookup
        llvm-objdump --macho --private-headers "$VERTHASH_MOD" | grep -A3 -E 'LC_BUILD_VERSION|LC_CODE_SIGNATURE' | head -12

        site="$APP/Contents/Resources/python/lib/python${PY_MAJOR}/site-packages"
        install_packages "$site" "$platform"
        install_electrum "$site" "$SECP_LIB" "$VERTHASH_MOD"
        cp run_electrum "$APP/Contents/Resources/electrum-vtc"
        cp electrum_vtc/gui/icons/electrum.icns "$APP/Contents/Resources/electrum.icns"
        cat > "$APP/Contents/MacOS/Electrum-VTC" <<'EOF'
#!/bin/sh
CONTENTS="$(cd "$(dirname "$0")/.." && pwd)"
exec "${CONTENTS}/Resources/python/bin/python3" -s "${CONTENTS}/Resources/electrum-vtc" "$@"
EOF
        chmod 0755 "$APP/Contents/MacOS/Electrum-VTC" "$APP/Contents/Resources/electrum-vtc"
        version_short="$(sed -n "s/^ELECTRUM_VERSION = '\([^']*\)'.*/\1/p" electrum_vtc/version.py)"
        cat > "$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleDevelopmentRegion</key>
	<string>English</string>
	<key>CFBundleDisplayName</key>
	<string>Electrum-VTC</string>
	<key>CFBundleExecutable</key>
	<string>Electrum-VTC</string>
	<key>CFBundleIconFile</key>
	<string>electrum.icns</string>
	<key>CFBundleIdentifier</key>
	<string>org.vertcoin.electrum-vtc</string>
	<key>CFBundleInfoDictionaryVersion</key>
	<string>6.0</string>
	<key>CFBundleName</key>
	<string>Electrum-VTC</string>
	<key>CFBundlePackageType</key>
	<string>APPL</string>
	<key>CFBundleShortVersionString</key>
	<string>${version_short}</string>
	<key>CFBundleVersion</key>
	<string>${version_short}</string>
	<key>CFBundleURLTypes</key>
	<array>
		<dict>
			<key>CFBundleURLName</key>
			<string>vertcoin</string>
			<key>CFBundleURLSchemes</key>
			<array>
				<string>vertcoin</string>
			</array>
		</dict>
	</array>
	<key>LSMinimumSystemVersion</key>
	<string>11</string>
	<key>NSCameraUsageDescription</key>
	<string>Electrum-VTC would like to access the camera to scan for QR codes</string>
	<key>NSHighResolutionCapable</key>
	<true/>
	<key>NSSupportsAutomaticGraphicsSwitching</key>
	<true/>
</dict>
</plist>
EOF
        prune_python "$APP/Contents/Resources/python/lib/python${PY_MAJOR}" "$site"
        rm -rf "$APP"/Contents/Resources/python/{include,share} \
               "$APP"/Contents/Resources/python/lib/{libtcl*,libtk*,tcl*,tk*,itcl*,thread*,pkgconfig}

        echo "== zip"
        out="electrum-vtc-${NAME}-${arch}-macos.zip"
        cd /tmp/mac
        normalize_times Electrum-VTC.app
        find Electrum-VTC.app | sort | zip -X -q -y -9 "/outdir/$out" -@
        cd "$SRC"
        outputs=("$out")
        ;;

    *)
        echo "ERR: unsupported host $HOST" >&2
        exit 1
        ;;
esac

cd /outdir
sha256sum "${outputs[@]}" > SHA256SUMS.part
cat SHA256SUMS.part
