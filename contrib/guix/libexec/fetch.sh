#!/usr/bin/env bash
# Runs inside the Guix container, with network access: downloads everything
# the builds of $HOSTS need into /cache. The files in contrib/guix/downloads.txt
# are checked against their sha256, and pip checks every Python package against
# the hashes in contrib/deterministic-build/requirements*.txt (--require-hashes),
# so the cache can only hold what the commit names.
export LC_ALL=C
set -o errexit -o pipefail -o nounset
umask 0022

export HOME=/tmp/home
mkdir -p "$HOME" /tmp/work
tar -xf "${SRC_TAR:?}" -C /tmp/work
cd /tmp/work/src

export SSL_CERT_DIR="${GUIX_ENVIRONMENT}/etc/ssl/certs"
export SSL_CERT_FILE="${SSL_CERT_DIR}/ca-certificates.crt"
export PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1

REQ=contrib/deterministic-build
REQS="python3 /libexec/reqs.py"
mkdir -p /cache/dl /cache/pip /tmp/req

wants() {  # wants HOSTLIST: whether any of $HOSTS is in the comma separated HOSTLIST
    local h
    for h in $HOSTS; do
        case ",$1," in *",$h,"*) return 0 ;; esac
    done
    return 1
}

# --- pinned files
python3 - contrib/guix/downloads.txt <<'EOF'
import hashlib, os, sys, urllib.request
hosts = set(os.environ['HOSTS'].split())
for line in open(sys.argv[1]):
    if line.startswith('#') or not line.strip():
        continue
    sha, for_hosts, name, url = line.split()
    if not hosts & set(for_hosts.split(',')):
        continue
    path = os.path.join('/cache/dl', name)
    def ok():
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(1 << 20), b''):
                h.update(chunk)
        return h.hexdigest() == sha
    if os.path.exists(path) and ok():
        continue
    print(f'downloading {name}', flush=True)
    with urllib.request.urlopen(url, timeout=300) as r, open(path + '.part', 'wb') as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    os.replace(path + '.part', path)
    if not ok():
        os.unlink(path)
        sys.exit(f'sha256 mismatch for {name}')
EOF

pip_download() {  # pip_download DEST REQFILE [pip options]
    local dest="$1" req="$2"
    shift 2
    mkdir -p "$dest"
    python3 -m pip download --quiet --no-deps --require-hashes --dest "$dest" -r "$req" "$@"
}

# --- build backends for the pure-python packages (any host)
$REQS "$REQ/requirements-build-base.txt" > /tmp/req/build-base.txt
pip_download /cache/pip/build /tmp/req/build-base.txt --only-binary :all:

# --- Electrum-VTC's dependencies, as source, built pure-python by build.sh
$REQS "$REQ/requirements.txt" --exclude pip,setuptools,wheel > /tmp/req/runtime.txt
python3 /libexec/pypi_sdist.py /tmp/req/runtime.txt /cache/pip/sdist

# --- compiled packages, as binary wheels for each platform
BINARIES=cffi,cryptography,pycparser,PyQt6,PyQt6-Qt6,PyQt6-sip
$REQS "$REQ/requirements-binaries.txt" --only "$BINARIES" > /tmp/req/binaries.txt
# pip 24 does not expand PEP 600 manylinux tags, so the older ones are listed too
binary_wheels() {  # binary_wheels HOST PLATFORM...
    local host="$1" p platforms=()
    shift
    for p in "$@"; do platforms+=(--platform "$p"); done
    pip_download "/cache/pip/$host" /tmp/req/binaries.txt --only-binary :all: \
        "${platforms[@]}" --python-version 3.12 --implementation cp --abi cp312 --abi abi3 --abi none
}
wants x86_64-linux-gnu    && binary_wheels x86_64-linux-gnu manylinux_2_28_x86_64 manylinux_2_17_x86_64 manylinux2014_x86_64
wants x86_64-w64-mingw32  && binary_wheels x86_64-w64-mingw32 win_amd64
wants x86_64-apple-darwin && binary_wheels x86_64-apple-darwin macosx_11_0_x86_64
wants arm64-apple-darwin  && binary_wheels arm64-apple-darwin macosx_11_0_arm64

# --- PyInstaller's dependencies, as source (the file pins only their sdists),
# built pure-python by build.sh and installed into the Windows Python
if wants x86_64-w64-mingw32; then
    $REQS "$REQ/requirements-build-wine.txt" --exclude pip > /tmp/req/build-wine.txt
    python3 /libexec/pypi_sdist.py /tmp/req/build-wine.txt /cache/pip/sdist-wine
fi

echo "fetch done: $(find /cache -type f | wc -l) files in the cache"
