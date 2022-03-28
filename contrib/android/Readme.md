# Kivy GUI

The Kivy GUI is used with Electrum on Android devices.
To generate an APK file, follow these instructions.

## Android binary with Docker

✓ _These binaries should be reproducible, meaning you should be able to generate
   binaries that match the official releases._

This assumes an Ubuntu (x86_64) host, but it should not be too hard to adapt to another
similar system.

1. Install Docker

    See `contrib/docker_notes.md`.

2. Build binaries (Note that this only works for debug builds! Otherwise the security model of Android does not let you access the internal storage of an app without root)

    The build script takes a few arguments. To see syntax, run it without providing any:
    ```
    $ ./build.sh debug
    ```
    For development, consider e.g. `$ ./build.sh kivy arm64-v8a debug`

    If you want reproducibility, try instead e.g.:
    ```
    $ ELECBUILD_COMMIT=HEAD ELECBUILD_NOCACHE=1 ./build.sh debug
    ```
    
    Note: `build.sh` takes an optional parameter which can be
    `release`, `release-unsigned`, or `debug` (default).


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

### debug vs release build
If you just follow the instructions above, you will build the apk
in debug mode. The most notable difference is that the apk will be
signed using a debug keystore. If you are planning to upload
what you build to e.g. the Play Store, you should create your own
keystore, back it up safely, and run `./contrib/make_apk release`.

See e.g. [kivy wiki](https://github.com/kivy/kivy/wiki/Creating-a-Release-APK)
and [android dev docs](https://developer.android.com/studio/build/building-cmdline#sign_cmdline).

### Access datadir on Android from desktop (e.g. to copy wallet file)
Note that this only works for debug builds! Otherwise the security model
of Android does not let you access the internal storage of an app without root.
(See [this](https://stackoverflow.com/q/9017073))
```
$ adb shell
$ run-as org.electrum.electrum ls /data/data/org.electrum.electrum/files/data
$ run-as org.electrum.electrum cp /data/data/org.electrum.electrum/files/data/wallets/my_wallet /sdcard/some_path/my_wallet
```

### How to investigate diff between binaries if reproducibility fails?
```
cd dist/
unzip Electrum-*.apk1 -d apk1
mkdir apk1/assets/private_mp3/
tar -xzvf apk1/assets/private.mp3 --directory apk1/assets/private_mp3/

unzip Electrum-*.apk2 -d apk2
mkdir apk2/assets/private_mp3/
tar -xzvf apk2/assets/private.mp3 --directory apk2/assets/private_mp3/

sudo chown --recursive "$(id -u -n)" apk1/ apk2/
chmod -R +Xr  apk1/ apk2/
$(cd apk1; find -type f -exec sha256sum '{}' \; > ./../sha256sum1)
$(cd apk2; find -type f -exec sha256sum '{}' \; > ./../sha256sum2)
diff sha256sum1 sha256sum2 > d
cat d
```
