# Qml GUI

The Qml GUI is used with Electrum on Android devices, since Electrum 4.4.
To generate an APK file, follow these instructions.

(note: older versions of Electrum for Android used the "kivy" GUI)

## Android binary with Docker

✓ _These binaries should be reproducible, meaning you should be able to generate
   binaries that match the official releases._

- _Minimum supported target system (i.e. what end-users need): Android 8.0 (API 26)_

This assumes an Ubuntu (x86_64) host, but it should not be too hard to adapt to another
similar system.

1. Install Docker

    See [`contrib/docker_notes.md`](../docker_notes.md).

    (worth reading even if you already have docker)

2. Build binaries

    The build script takes a few arguments. To see syntax, run it without providing any:
    ```
    $ ./build.sh
    ```
    For development, consider e.g. `$ ./build.sh qml arm64-v8a debug`

    If you want reproducibility, try instead e.g.:
    ```
    $ ELECBUILD_COMMIT=HEAD ./build.sh qml all release-unsigned
    ```

3. The generated binary is in `./dist`.


## Signing a release (Electrum-VTC)

The release build (`.github/workflows/guix.yml`, on a tag) keeps every release file as an
artifact of its run, for 90 days, the APKs unsigned:
`electrum_vtc-<version>-<arch>-release-unsigned.apk`. Each file has a build attestation.
The maintainer signs the APKs offline and creates the release with all of them:
[`apksig.sh`](apksig.sh) signs an APK and extracts its APK Signing Block, its detached
signature, with [apksigcopier](https://github.com/obfusk/apksigcopier), in a Debian image
pinned by digest.

1. Download the run's files into `release/`, and check their attestations:
    ```
    $ gh run download RUN_ID --repo vertcoin-project/electrum --dir artifacts
    $ mkdir release && find artifacts -type f ! -name SHA256SUMS.part -exec cp -t release {} +
    $ for f in release/*; do gh attestation verify "$f" --repo vertcoin-project/electrum; done
    ```
2. Sign the APKs with the release key. Its password is asked for. This writes
   `…-release.apk` and its signature `…-release.apk.sig.tar` next to each one, and prints
   the certificate's SHA-256. The key and the APKs must be inside the current directory:
    ```
    $ contrib/android/apksig.sh sign electrum-vtc.keystore electrum-vtc release/*-release-unsigned.apk
    ```
3. List every file's hash in `SHA256SUMS`, and sign it:
    ```
    $ cd release && find . -maxdepth 1 -type f -printf '%P\n' | LC_ALL=C sort | xargs sha256sum -- > ../SHA256SUMS && mv ../SHA256SUMS .
    $ gpg --armor --detach-sign SHA256SUMS
    ```
4. Create the release with all of them, the unsigned APKs too: they are what the
   attestations name, and anyone can check that a signed APK is its unsigned one plus a
   signature (below).
    ```
    $ gh release create v4.8.3 --repo vertcoin-project/electrum --verify-tag --draft --title "Electrum-VTC 4.8.3" --notes-file NOTES.md ./*
    ```

The release key is created once (`keytool -genkeypair -keyalg RSA -keysize 4096
-validity 10000 …`), never leaves the maintainer's machine, and is backed up: Android only
installs updates signed with the key that signed the installed app.

The signed APK is the unsigned one plus an APK Signing Block: `apksig.sh` signs with v2
and v3 signatures only (`minSdkVersion` is 26) and keeps the entries' alignment as built.


## Verifying reproducibility and comparing against official binary

Every user can verify that the official binary was created from the source code in this
repository.

1. Build your own binary as described above, with `release-unsigned` and
   `ELECBUILD_COMMIT` set to the release tag's commit (the APK depends on the commit's
   time).
2. Check that the official APK is your build plus a signature:
    ```
    $ contrib/android/apksig.sh compare electrum_vtc-4.8.3-arm64-v8a-release.apk dist/electrum_vtc-4.8.3-arm64-v8a-release-unsigned.apk
    ```
   or put the published signature on your build: the result is the official APK, byte
   for byte.
    ```
    $ contrib/android/apksig.sh attach electrum_vtc-4.8.3-arm64-v8a-release.apk.sig.tar dist/electrum_vtc-4.8.3-arm64-v8a-release-unsigned.apk mine.apk
    $ sha256sum mine.apk electrum_vtc-4.8.3-arm64-v8a-release.apk
    ```
   Upstream's `apkdiff.py` (written by the Signal developers) also compares two APKs,
   ignoring their signatures:
    ```
    $ python3 contrib/android/apkdiff.py Electrum_apk_that_you_built.apk Electrum_apk_official_release.apk
    ```


## F-Droid

F-Droid builds every app from source on its own build server. With
[reproducible builds](https://f-droid.org/docs/Reproducible_Builds/) it publishes the
developer's signed APK instead of signing its own build: it builds the APK, copies the
signature of the APK named in `Binaries` onto it with apksigcopier, and publishes it if
that verifies, which needs its build to be byte for byte the release's unsigned APK. Apps
installed from F-Droid and from the GitHub releases can then update each other.

The app's metadata (`metadata/org.vertcoin.electrum_vtc.yml` in
[fdroiddata](https://gitlab.com/fdroid/fdroiddata)) names the release APKs and the
release certificate. One `Builds` entry per architecture, as each APK has its own
`versionCode` (`get_apk_versioncode.py`: 45408032, 45408033 and 45408034 for 4.8.3's
armeabi-v7a, arm64-v8a and x86_64):

```yaml
AllowedAPKSigningKeys: <the certificate's SHA-256, as apksig.sh sign prints it>

Builds:
  - versionName: 4.8.3
    versionCode: 45408033
    commit: v4.8.3
    binary: https://github.com/vertcoin-project/electrum/releases/download/v%v/electrum_vtc-%v-arm64-v8a-release.apk
    # sudo, prebuild, build, output: F-Droid's recipe for the build
```

Notes:
- F-Droid's build server does not run Docker: its recipe has to reproduce what
  `build.sh` does in `Dockerfile` (the same Debian packages, NDK, SDK, buildozer and
  python-for-android commits), and every dependency is built from source, without
  prebuilt binaries. This is the part to work out with F-Droid's maintainers.
- The `versionCode` comes from `ELECTRUM_VERSION`, which a release candidate shares with
  its release (and `get_apk_versioncode.py` ignores alpha and beta suffixes): only
  releases may go to F-Droid.
- Alternatively, a self-hosted F-Droid repository (`fdroid init`, `fdroid update`) can
  serve the signed release APKs as they are, without F-Droid reproducing them.


## FAQ

### I changed something but I don't see any differences on the phone. What did I do wrong?
You probably need to clear the cache: `rm -rf .buildozer/android/platform/build-*/{build,dists}`

Or more extreme, to nuke all build-related dirs: `rm -rf .buildozer_qml/ packages/ contrib/android/.cache/`

Having a several months old build cache might also cause confusing build failures,
in such a case, worth a try clearing it.


### How do I deploy on connected phone for quick testing?
Assuming `adb` is installed:
```
$ adb -d install -r dist/Electrum-*-arm64-v8a-debug.apk
$ adb shell monkey -p org.electrum.electrum 1
```
Note `adb install` can take a `--user {userId}` option to install the app for a specific profile.
Without that, the default is to install to *all* profiles.


### How do I get an interactive shell inside docker?
```
$ docker run -it --rm \
    -v $PWD:/home/user/wspace/electrum \
    -v $PWD/.buildozer/.gradle:/home/user/.gradle \
    --workdir /home/user/wspace/electrum \
    electrum-android-builder-img
```


### How do I get more verbose logs for the build?
See `log_level` in `buildozer.spec`


### How can I see logs at runtime?
This should work OK for most scenarios:
```
adb logcat | grep python
```
Better `grep` but fragile because of `cut`:
```
adb logcat | grep -F "`adb shell ps | grep org.electrum.electrum | cut -c14-19`"
```


### The Qml GUI can be run directly on Linux Desktop. How?
Install requirements:
```
python3 -m pip install ".[qml_gui]"
```

Run electrum with the `-g` switch: `electrum -g qml`

Notes:

- Installing these deps from your OS package manager should also work,
  except many don't distribute pyqt6 yet.
  For pyqt5 on debian-based distros, this used to look like this:
  ```
  sudo apt-get install python3-pyqt5 python3-pyqt5.qtquick python3-pyqt5.qtmultimedia
  sudo apt-get install python3-pil
  sudo apt-get install qml-module-qtquick-controls2 qml-module-qtquick-layouts \
      qml-module-qtquick-window2 qml-module-qtmultimedia \
      libqt5multimedia5-plugins qml-module-qt-labs-folderlistmodel
  ```


### debug vs release build
If you just follow the instructions above, you will build the apk
in debug mode. The most notable difference is that the apk will be
signed using a debug keystore. If you are planning to upload
what you build to e.g. the Play Store, you should create your own
keystore, back it up safely, and run `./build.sh` in `release` mode.

See e.g. [kivy wiki](https://github.com/kivy/kivy/wiki/Creating-a-Release-APK)
and [android dev docs](https://developer.android.com/studio/build/building-cmdline#sign_cmdline).

### Access datadir on Android from desktop (e.g. to copy wallet file)
Note that this only works for debug builds! Otherwise the security model
of Android does not let you access the internal storage of an app without root.
(See [this](https://stackoverflow.com/q/9017073))
To pull a file:
```
$ adb shell
adb$ run-as org.electrum.electrum ls /data/data/org.electrum.electrum/files/data
adb$ exit
$ adb exec-out run-as org.electrum.electrum cat /data/data/org.electrum.electrum/files/data/wallets/my_wallet > my_wallet
```
To push a file:
```
$ adb push ~/wspace/tmp/my_wallet /data/local/tmp
$ adb shell
adb$ ls -la /data/local/tmp
adb$ run-as org.electrum.testnet.electrum cp /data/local/tmp/my_wallet /data/data/org.electrum.testnet.electrum/files/data/testnet/wallets/
adb$ run-as org.electrum.testnet.electrum chmod -R 700 /data/data/org.electrum.testnet.electrum/files/data/testnet/wallets
adb$ run-as org.electrum.testnet.electrum chmod -R u-x,u+X /data/data/org.electrum.testnet.electrum/files/data/testnet/wallets
adb$ rm /data/local/tmp/my_wallet
```

Or use Android Studio: "Device File Explorer", which can download/upload data directly from device (via adb).

#### Device with multiple user profiles

There are further complications if using an Android device
[with multiple user profiles](https://source.android.com/docs/devices/admin/multi-user-testing)
(typical for GrapheneOS/etc).

Run `$ adb shell pm list users` to get a list of all existing users, and take note of the user ids.

Instead of `/data/data/{app.path}`, private app data is stored at `/data/user/{userId}/{app.path}`.

Further, instead of `adb$ run-as org.electrum.electrum`,
you need `adb$ run-as org.electrum.electrum --user {userId}`.

### How to investigate diff between binaries if reproducibility fails?
```
cd dist/
unzip Electrum-*.apk1 -d apk1
mkdir apk1/assets/private_mp3/
tar -xzvf apk1/assets/private.tar --directory apk1/assets/private_mp3/
mkdir apk1/lib/_libpybundle/
tar -xzvf apk1/lib/*/libpybundle.so --directory apk1/lib/_libpybundle/

unzip Electrum-*.apk2 -d apk2
mkdir apk2/assets/private_mp3/
tar -xzvf apk2/assets/private.tar --directory apk2/assets/private_mp3/
mkdir apk2/lib/_libpybundle/
tar -xzvf apk2/lib/*/libpybundle.so --directory apk2/lib/_libpybundle/

sudo chown --recursive "$(id -u -n)":"$(id -u -n)" apk1/ apk2/
chmod -R +Xr  apk1/ apk2/

unzip apk1/lib/_libpybundle/_python_bundle/stdlib.zip -d apk1/lib/_libpybundle/_python_bundle/stdlib
unzip apk2/lib/_libpybundle/_python_bundle/stdlib.zip -d apk2/lib/_libpybundle/_python_bundle/stdlib

sudo chown --recursive "$(id -u -n)":"$(id -u -n)" apk1/ apk2/
chmod -R +Xr  apk1/ apk2/
$(cd apk1; find -type f -exec sha256sum '{}' \; > ./../sha256sum1)
$(cd apk2; find -type f -exec sha256sum '{}' \; > ./../sha256sum2)
diff sha256sum1 sha256sum2 > d
cat d
```

### How to install apks built by the CI on my phone?

The CI (GitHub Actions) builds apks on a nightly schedule.
See the [`builds` workflow](https://github.com/spesmilo/electrum/actions/workflows/builds.yml).
Open the run of interest and download the `electrum-android-*` artifact.
The apk is built in `debug` mode, and is signed using an ephemeral RSA key.

For tech demo purposes, you can directly install this apk on your phone.
However, if you already have electrum installed on your phone, Android's TOFU signing model
will not let you upgrade that to the CI apk due to mismatching signing keys. As the CI key
is ephemeral, it is not even possible to upgrade from an older CI apk to a newer CI apk.

However, it is possible to resign the apk manually with one's own key, using
e.g. [`apksigner`](https://developer.android.com/studio/command-line/apksigner),
mutating the apk in place, after which it should be possible to upgrade:
```
apksigner sign --ks ~/wspace/electrum/contrib/android/android_debug.keystore Electrum-*-arm64-v8a-debug.apk
```
