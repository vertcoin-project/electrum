# Electrum-VTC - Lightweight Vertcoin client

```
Licence: MIT Licence
Language: Python (>= 3.10)
Homepage: https://github.com/vertcoin-project/electrum
```

Electrum-VTC is [Electrum](https://github.com/spesmilo/electrum) for Vertcoin, rebased
on upstream Electrum's releases. [VERTCOIN.md](VERTCOIN.md) describes what it changes;
Lightning is not supported.

Donate VTC to support this work: [VertionJAZJ7ZMauEdXaagRb4XP7cw6FXV](https://bitinfocharts.com/vertcoin/address/VertionJAZJ7ZMauEdXaagRb4XP7cw6FXV)


## Getting started

_(If you've come here looking to simply run Electrum-VTC,
[download it from the releases](https://github.com/vertcoin-project/electrum/releases),
and see [VERIFYING.md](VERIFYING.md) to check what you downloaded.)_

Wallets and settings are kept in `~/.electrum-vtc` on Linux and macOS, and in
`%APPDATA%\Electrum-VTC` on Windows.

Electrum-VTC itself is pure Python, and so are most of the required dependencies,
but not everything. The following sections describe how to run from source, but here
is a TL;DR:

```
$ sudo apt-get install libsecp256k1-dev
$ ELECTRUM_ECC_DONT_COMPILE=1 python3 -m pip install --user ".[gui,crypto]"
```

### Not pure-python dependencies

#### Qt GUI

If you want to use the Qt interface, install the Qt dependencies:
```
$ sudo apt-get install python3-pyqt6
```

#### QR code scanning

QR code recognition uses QtMultimedia and [zxing-cpp](https://github.com/zxing-cpp/zxing-cpp/):
```
$ sudo apt-get install python3-pyqt6.qtmultimedia libzxing3 (or libzxing4)
```

#### libsecp256k1

For elliptic curve operations,
[libsecp256k1](https://github.com/bitcoin-core/secp256k1)
is a required dependency.

If you "pip install" Electrum-VTC, by default libsecp will get compiled locally,
as part of the `electrum-ecc` dependency. This can be opted-out of,
by setting the `ELECTRUM_ECC_DONT_COMPILE=1` environment variable.
For the compilation to work, besides a C compiler, you need at least:
```
$ sudo apt-get install automake libtool
```
If you opt out of the compilation, you need to provide libsecp in another way, e.g.:
```
$ sudo apt-get install libsecp256k1-dev
```

#### cryptography

Due to the need for fast symmetric ciphers,
[cryptography](https://github.com/pyca/cryptography) is required.
Install from your package manager (or from pip):
```
$ sudo apt-get install python3-cryptography
```

#### Verthash

Vertcoin's proof-of-work, Verthash, needs a 1.2 GiB data file, `verthash.dat`. Electrum-VTC
generates it on first start, or reuses one from Vertcoin Core's data directory.
[vertcoinhash](https://pypi.org/project/vertcoinhash/), which every release bundles,
generates it in seconds and hashes headers in C; without it, both are done in
pure Python, much more slowly:
```
$ python3 -m pip install --user vertcoinhash
```

#### hardware-wallet support

Trezor One and Model T, and Ledger with its Vertcoin app, are supported.
For their dependencies,
[see this](https://github.com/spesmilo/electrum-docs/blob/master/hardware-linux.rst).


### Running from tar.gz

If you downloaded the official package (tar.gz), you can run
Electrum-VTC from its root directory without installing it on your
system; all the pure python dependencies are included in the 'packages'
directory. To run Electrum-VTC from its root directory, just do:
```
$ ./run_electrum
```

You can also install Electrum-VTC on your system, by running this command:
```
$ sudo apt-get install python3-setuptools python3-pip
$ python3 -m pip install --user .
```

This will download and install the Python dependencies used by
Electrum-VTC instead of using the 'packages' directory.
It will also place an executable named `electrum-vtc` in `~/.local/bin`,
so make sure that is on your `PATH` variable.


### Development version (git clone)

_(For OS-specific instructions, see [here for Windows](contrib/build-wine/README_windows.md),
and [for macOS](contrib/osx/README_macos.md))_

Check out the code from GitHub:
```
$ git clone https://github.com/vertcoin-project/electrum.git electrum-vtc
$ cd electrum-vtc
$ git submodule update --init
```

Run install (this should install dependencies):
```
$ python3 -m pip install --user -e .
```

Create translations (optional):
```
$ sudo apt-get install gettext
$ ./contrib/locale/build_locale.sh electrum_vtc/locale/locale electrum_vtc/locale/locale
```

Finally, to start Electrum-VTC:
```
$ ./run_electrum
```

### Run tests

Run unit tests with `pytest`:
```
$ pytest tests -v
```
(can be parallelized with `-n auto` option, using [`pytest-xdist`](https://github.com/pytest-dev/pytest-xdist) plugin)

To run a single file, specify it directly like this:
```
$ pytest tests/test_bitcoin.py -v
```

## Creating Binaries

Every release file is built reproducibly:

- [Source tarball, Linux AppImage, Windows and macOS](contrib/guix/README.md), with Guix
- [Android](contrib/android/Readme.md), in upstream's Docker image


## Contributing

Bug reports and pull requests are welcome on the
[issue tracker](https://github.com/vertcoin-project/electrum/issues).
Problems that also affect Bitcoin's Electrum belong
[upstream](https://github.com/spesmilo/electrum), whose fixes Electrum-VTC picks up.

Translations come from upstream Electrum: please improve them on
[Crowdin](https://crowdin.com/project/electrum).
