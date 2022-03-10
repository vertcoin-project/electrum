# Kivy GUI

The Kivy GUI is used with Electrum on Android devices.
To generate an APK file, follow these instructions.

## Android binary with Docker

✓ _These binaries should be reproducible.

This assumes an Ubuntu (x86_64) host, but it should not be too hard to adapt to another
similar system.

1. Install Docker

    See `contrib/docker_notes.md`.

2. Build binaries (Note that this only works for debug builds! Otherwise the security model of Android does not let you access the internal storage of an app without root)

    ```
    $ ./build.sh debug
    ```
   If you want reproducibility, try instead e.g.:
    ```
    $ ELECBUILD_COMMIT=HEAD ELECBUILD_NOCACHE=1 ./build.sh debug
    ```

3. The generated binary is in `./dist`.


4. Install [adb](https://developer.android.com/studio/command-line/adb)


5. Install .apk to connected phone

   ```
   $ adb -d install -r fresh_clone/electrum/dist/Electrum-*-arm64-v8a-debug.apk
   ```

6. Open Electrum app on phone.  It will close after a few seconds.  Now that the app internal storage is created, we can copy verthash.dat.

   ```
   $ adb push verthash.dat /data/local/tmp
   $ adb shell run-as org.electrum.electrum cp /data/local/tmp/verthash.dat /data/data/org.electrum.electrum/files/app
   ```

## FAQ

### I changed something but I don't see any differences on the phone. What did I do wrong?
You probably need to clear the cache: `rm -rf .buildozer/android/platform/build-*/{build,dists}`


### How do I deploy on connected phone for quick testing?
Assuming `adb` is installed:
```
$ adb -d install -r dist/Electrum-*-arm64-v8a-debug.apk
$ adb shell monkey -p org.electrum.electrum 1
```


### How do I get an interactive shell inside docker?
```
$ sudo docker run -it --rm \
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


### Kivy can be run directly on Linux Desktop. How?
Install Kivy.

Build atlas: `(cd contrib/android/; make theming)`

Run electrum with the `-g` switch: `electrum -g kivy`


### Access datadir on Android from desktop (e.g. to copy wallet file)
Note that this only works for debug builds! Otherwise the security model
of Android does not let you access the internal storage of an app without root.
(See [this](https://stackoverflow.com/q/9017073))
```
$ adb shell
$ run-as org.electrum.electrum ls /data/data/org.electrum.electrum/files/data
$ run-as org.electrum.electrum cp /data/data/org.electrum.electrum/files/data/wallets/my_wallet /sdcard/some_path/my_wallet
```
