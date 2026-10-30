#!/usr/bin/env bash
#
# Signs Electrum-VTC's release APKs offline, and attaches published signatures
# to unsigned builds, with Debian's apksigner and apksigcopier
# (https://github.com/obfusk/apksigcopier) in a Debian image pinned by digest.
#
# The APKs build.sh builds with release-unsigned are reproducible. Signing one
# only adds an APK Signing Block, and apksigcopier copies that block, a detached
# signature, from one APK to another: an unsigned build of the release commit
# plus the published signature is the release APK, byte for byte. F-Droid checks
# a developer's signed APK against its own build of the app the same way.
#
#   apksig.sh sign KEYSTORE ALIAS UNSIGNED.apk...
#       Signs each NAME-release-unsigned.apk with the key ALIAS in KEYSTORE (its
#       password is asked for), and writes next to it NAME-release.apk and its
#       detached signature, NAME-release.apk.sig.tar. Prints the certificate's
#       SHA-256, which F-Droid's metadata names in AllowedAPKSigningKeys.
#
#   apksig.sh attach SIG.tar UNSIGNED.apk SIGNED.apk
#       Writes SIGNED.apk: UNSIGNED.apk with the detached signature SIG.tar, and
#       checks that it verifies.
#
#   apksig.sh compare SIGNED.apk UNSIGNED.apk
#       Checks that SIGNED.apk is UNSIGNED.apk plus a signature.
#
# Every path must be inside the current directory, which is mounted into the
# container. The key never leaves this machine: sign offline, publish the
# signed APKs and their .sig.tar files.

set -euo pipefail
export LC_ALL=C
# Git Bash would rewrite the container's paths into Windows ones
export MSYS_NO_PATHCONV=1

IMAGE=electrum-vtc-apksig
BASE="debian:13@sha256:2dc419c6d7fe3dad0a2f9fd469c34cc90b0f9ba642d8fde837fe3d7d34a0e7f1"

fail() { echo "apksig.sh: $*" >&2; exit 1; }

usage() {
    sed -n '13,24p' "$0" | sed 's/^# \{0,1\}//' >&2
    exit 1
}

# a path relative to the current directory, which the container sees as /w
inside() {
    local p
    p="$(realpath --relative-to=. -- "$1")"
    case "$p" in ../*|..|/*) fail "$1 is not inside $(pwd)" ;; esac
    echo "$p"
}

run() {
    docker image inspect "$IMAGE" >/dev/null 2>&1 || docker build --quiet -t "$IMAGE" - >/dev/null <<EOF
FROM $BASE
RUN apt-get update \
    && apt-get install -y --no-install-recommends apksigner apksigcopier \
    && rm -rf /var/lib/apt/lists/*
EOF
    local dir
    dir="$(pwd)"
    # Git Bash's /tmp, for one, is not where Docker would look
    command -v cygpath >/dev/null && dir="$(cygpath -m "$dir")"
    docker run --rm "${DOCKER_TTY[@]}" --user "$(id -u):$(id -g)" -e HOME=/tmp \
        -v "$dir:/w" -w /w "$IMAGE" "$@"
}

# signature directory <-> .sig.tar, which is the same bytes for the same files
TAR_SIG='tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner -cf'

DOCKER_TTY=()
[ $# -ge 1 ] || usage
cmd="$1"; shift
case "$cmd" in
    sign)
        [ $# -ge 3 ] || usage
        ks="$(inside "$1")"; alias="$2"; shift 2
        # the password prompt reads the terminal, or else standard input
        if [ -t 0 ]; then DOCKER_TTY=(-it); else DOCKER_TTY=(-i); fi
        for apk in "$@"; do
            unsigned="$(inside "$apk")"
            case "$unsigned" in
                *-release-unsigned.apk) signed="${unsigned%-release-unsigned.apk}-release.apk" ;;
                *) fail "$apk is not a NAME-release-unsigned.apk" ;;
            esac
            echo "== $signed"
            # The signed APK must be the unsigned one plus a signature: v2 and v3
            # only, as minSdkVersion is 26 (v1 would change the APK's entries, v4
            # writes a separate .idsig file), and the entries' alignment as built
            # (apksigner otherwise realigns native libraries to 16 KiB pages)
            run sh -euc '
                rm -rf "$3.sig" "$3.sig.tar" "$3"
                apksigner sign --ks "$1" --ks-key-alias "$2" --v1-signing-enabled false \
                    --v4-signing-enabled false --alignment-preserved true --in "$4" --out "$3"
                apksigner verify --print-certs "$3" | grep "SHA-256"
                apksigcopier compare "$3" --unsigned "$4"
                mkdir "$3.sig"
                apksigcopier extract "$3" "$3.sig"
                '"$TAR_SIG"' "$3.sig.tar" -C "$3.sig" .
                rm -rf "$3.sig"
                ' sh "$ks" "$alias" "$signed" "$unsigned"
            sha256sum -- "$signed" "$signed.sig.tar"
        done
        ;;
    attach)
        [ $# -eq 3 ] || usage
        sig="$(inside "$1")"; unsigned="$(inside "$2")"; signed="$(inside "$3")"
        run sh -euc '
            tmp="$(mktemp -d)"
            tar -xf "$1" -C "$tmp"
            rm -f "$3"
            apksigcopier patch "$tmp" "$2" "$3"
            apksigner verify --print-certs "$3" | grep "SHA-256"
            ' sh "$sig" "$unsigned" "$signed"
        sha256sum -- "$signed"
        ;;
    compare)
        [ $# -eq 2 ] || usage
        signed="$(inside "$1")"; unsigned="$(inside "$2")"
        run sh -euc '
            apksigner verify --print-certs "$1" | grep "SHA-256"
            apksigcopier compare "$1" --unsigned "$2"
            echo "$1 is $2 plus a signature"
            ' sh "$signed" "$unsigned"
        ;;
    *)
        usage
        ;;
esac
