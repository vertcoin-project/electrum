# Verifying an Electrum-VTC release

The following commands use v4.8.3: put in the tag and file names of the release you downloaded.
A release candidate's desktop files are named after the commit as well, as in
`electrum-vtc-4.8.3-514c1628a46f-setup.exe`. On Windows, Git Bash runs them.

## 1. Checksums signed by the release key

`SHA256SUMS` lists every file's SHA-256, and `SHA256SUMS.asc` is signed by
[my PGP key](https://github.com/vertiond.gpg), fingerprint
`28E7 2909 F171 7FE9 6077  54F8 A7BE B262 1678 D37D`.

```
curl -sL https://github.com/vertiond.gpg | gpg --import
gpg --verify SHA256SUMS.asc SHA256SUMS
sha256sum -c --ignore-missing SHA256SUMS
```

## 2. Build attestations

Every file except for the signed APKs has a [build attestation](https://github.com/vertcoin-project/electrum/attestations):
a record in Sigstore's public log that GitHub Actions built it, from the release's tag, with `.github/workflows/guix.yml`.
With the [GitHub CLI](https://cli.github.com):

```
gh attestation verify electrum-vtc-4.8.3-setup.exe --repo vertcoin-project/electrum \
    --signer-workflow vertcoin-project/electrum/.github/workflows/guix.yml --source-ref refs/tags/v4.8.3
```

## 3. The Android APKs

The APKs are signed by the Electrum-VTC release key, whose certificate's SHA-256 is

```
2b0d2b59a3141c9e24976840fa985f350ab3f3148f506c5af2e47238d09f63be
```

`apksigner verify --print-certs electrum_vtc-4.8.3-arm64-v8a-release.apk` prints it, and so
does [AppVerifier](https://github.com/soupslurpr/AppVerifier) on a phone. Android will
only install updates signed by the same key.

Each signed APK is the attested unsigned APK plus a signature, which
`electrum_vtc-4.8.3-<arch>-release.apk.sig.tar` holds by itself.
[apksigcopier](https://github.com/obfusk/apksigcopier) checks that nothing else differs:

```
apksigcopier compare electrum_vtc-4.8.3-arm64-v8a-release.apk --unsigned electrum_vtc-4.8.3-arm64-v8a-release-unsigned.apk
```

## 4. Build it yourself

Every file is bit by bit reproducible when built from the tag's source.
First get the source, and check the tag's signature, by the same PGP key:

```
git clone https://github.com/vertcoin-project/electrum.git electrum-vtc && cd electrum-vtc
git checkout v4.8.3 && git verify-tag v4.8.3
```

**Desktop and source files**, with [Guix](https://guix.gnu.org) on x86_64 Linux
(the macOS builds also need Apple's SDK: see [contrib/guix/README.md](contrib/guix/README.md)):

```
HOSTS="sdist x86_64-linux-gnu x86_64-w64-mingw32" ./contrib/guix/guix-build
cat guix-build-*/output/*/SHA256SUMS.part
```

The hashes must match those in `SHA256SUMS`.

**APKs**, with Docker (about 40 GB of disk, and an hour or more per architecture):

```
ELECBUILD_COMMIT=HEAD ./contrib/android/build.sh qml arm64-v8a release-unsigned
sha256sum dist/electrum_vtc-4.8.3-arm64-v8a-release-unsigned.apk
```

That hash must match the unsigned APK's in `SHA256SUMS`. Then add the published signature
to your build: the result is the release APK, byte for byte.

```
cp ~/Downloads/electrum_vtc-4.8.3-arm64-v8a-release.apk.sig.tar .
./contrib/android/apksig.sh attach electrum_vtc-4.8.3-arm64-v8a-release.apk.sig.tar \
    dist/electrum_vtc-4.8.3-arm64-v8a-release-unsigned.apk mine.apk
sha256sum mine.apk
```
