#!/bin/bash

# This script was tested on Linux and MacOS hosts, where it can be used
# to build verthash-dat creation binaries.
#
# It can also be used to cross-compile to Windows:
# $ sudo apt-get install mingw-w64
# For a Windows x86 (32-bit) target, run:
# $ GCC_TRIPLET_HOST="i686-w64-mingw32" ./contrib/make_verthash-dat.sh
# Or for a Windows x86_64 (64-bit) target, run:
# $ GCC_TRIPLET_HOST="x86_64-w64-mingw32" ./contrib/make_verthash-dat.sh
#
# To cross-compile to Linux x86:
# sudo apt-get install gcc-multilib g++-multilib
# $ AUTOCONF_FLAGS="--host=i686-linux-gnu CFLAGS=-m32 CXXFLAGS=-m32 LDFLAGS=-m32" ./contrib/make_verthash-dat.sh
set -e

. $(dirname "$0")/build_tools_util.sh || (echo "Could not source build_tools_util.sh" && exit 1)

here=$(dirname $(realpath "$0" 2> /dev/null || grealpath "$0"))
CONTRIB="$here"
PROJECT_ROOT="$CONTRIB/.."

pkgname="create-verthash-datafile"
info "Building $pkgname..."

(
    cd $CONTRIB
    if [ ! -d vertcoinhash-python ]; then
        git clone -b electrum-executables https://github.com/vertcoin-project/vertcoinhash-python.git
    fi

    info "Building create-verthash-datafile binary..."
    cd vertcoinhash-python
    if [ "$BUILD_TYPE" = "wine" ]; then
      ./build-windows.sh || fail "Could not build $pkgname.exe"
      cp -fpv "$here/vertcoinhash-python/$pkgname.exe" "$PROJECT_ROOT/electrum_vtc" || fail "Could not copy the $pkgname binary to its destination"
      info "$pkgname has been placed in the inner 'electrum_vtc' folder."
      if [ -n "$CACHEDIR" ] ; then
          cp -fpv "$here/vertcoinhash-python/$pkgname.exe" "$CACHEDIR" || fail "Could not copy the $pkgname.exe binary to $CACHEDIR"
      fi
    else
      make h1 || fail "Could not build $pkgname"
      cp -fpv "$here/vertcoinhash-python/$pkgname" "$PROJECT_ROOT/electrum_vtc" || fail "Could not copy the $pkgname binary to its destination"
      info "$pkgname has been placed in the inner 'electrum_vtc' folder."
    fi
)
