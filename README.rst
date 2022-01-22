Electrum - Lightweight Vertcoin client
=====================================

Electrum-VTC is a rebase of `upstream Electrum`_ and pulls in updates regularly.

Donate VTC to support this work: `VertionJAZJ7ZMauEdXaagRb4XP7cw6FXV`_

This program uses the verthash datafile to verify block headers and expects :code:`verthash.dat` to be in the data directory or the directory that the program is run from.  Obtain the verthash datafile by running :code:`create-verthash-datafile`.  You may also copy :code:`verthash.dat` from Vertcoin-Core or `build from source`_.

Windows Data Directory
 - :code:`%APPDATA%\Electrum-VTC`
Linux Data Directory
 - :code:`~/.electrum-vtc`

If you would like hardware wallet support, see `this`_.

.. _upstream Electrum: https://github.com/spesmilo/electrum
.. _VertionJAZJ7ZMauEdXaagRb4XP7cw6FXV: https://bitinfocharts.com/vertcoin/address/VertionJAZJ7ZMauEdXaagRb4XP7cw6FXV
.. _build from source: https://github.com/vertcoin-project/vertcoinhash-python#building-verthashdat

How to verify GPG signatures
============================

GPG signatures are a proof that distributed files have been signed by the owner of the signing key. For example, if this website was compromised and the original Electrum files had been replaced, signature verification would fail, because the attacker would not be able to create valid signatures. (Note that an attacker would be able to create valid hashes, this is why we do not publish hashes of our binaries here, it does not bring any security).

In order to be able to verify GPG signatures, you need to import the public key of the signer. Electrum binaries are signed with `vertion's`_ `public key`_. On Linux, you can import that key using the following command: :code:`gpg --import 28E72909F1717FE9607754F8A7BEB2621678D37D.asc`. Here are tutorials for `Windows`_ and `MacOS`_.

.. _vertion's: https://github.com/vertiond
.. _public key: https://keys.openpgp.org/search?q=vertion@protonmail.com
.. _Windows: https://bitzuma.com/posts/how-to-verify-an-electrum-download-on-windows/
.. _MacOS: https://bitzuma.com/posts/how-to-verify-an-electrum-download-on-mac/

Notes for Windows users
=======================

Electrum binaries are often flagged by various anti-virus software. There is nothing we can do about it, so please stop reporting that to us. Anti-virus software uses heuristics in order to determine if a program is malware, and that often results in false positives. If you trust the developers of the project, you can verify the GPG signature of Electrum binaries, and safely ignore any anti-virus warnings. If you do not trust the developers of the project, you should build the binaries yourself, or run the software from source. Finally, if you are really concerned about malware, you should not use an operating system that relies on anti-virus software.

Old versions of Windows might need to install the KB2999226 Windows update.


Running from source
================
Electrum itself is pure Python, and so are most of the required dependencies,
but not everything. The following sections describe how to run from source, but here
is a TL;DR::

    sudo apt-get install libsecp256k1-0 python3-tk
    python3 -m pip install --user .[gui,crypto]


Not pure-python dependencies
----------------------------

If you want to use the Qt interface, install the Qt dependencies::

    sudo apt-get install python3-pyqt5

For elliptic curve operations, `libsecp256k1`_ is a required dependency::

    sudo apt-get install libsecp256k1-0

Alternatively, when running from a cloned repository, a script is provided to build
libsecp256k1 yourself::

    sudo apt-get install automake libtool
    ./contrib/make_libsecp256k1.sh

Due to the need for fast symmetric ciphers, `cryptography`_ is required.
Install from your package manager (or from pip)::

    sudo apt-get install python3-cryptography


If you would like hardware wallet support, see `this`_.

.. _libsecp256k1: https://github.com/bitcoin-core/secp256k1
.. _pycryptodomex: https://github.com/Legrandin/pycryptodome
.. _cryptography: https://github.com/pyca/cryptography
.. _this: https://github.com/spesmilo/electrum-docs/blob/master/hardware-linux.rst

Running from tar.gz
-------------------

If you downloaded the official package (tar.gz), you can run
Electrum from its root directory without installing it on your
system; all the pure python dependencies are included in the 'packages'
directory. To run Electrum from its root directory, just do::

    ./run_electrum

You can also install Electrum on your system, by running this command::

    sudo apt-get install python3-setuptools python3-pip
    python3 -m pip install --user .

This will download and install the Python dependencies used by
Electrum instead of using the 'packages' directory.
It will also place an executable named :code:`electrum` in :code:`~/.local/bin`,
so make sure that is on your :code:`PATH` variable.


Development version (git clone)
-------------------------------

Check out the code from GitHub::

    git clone git://github.com/vertcoin-project/electrum.git
    cd electrum
    git submodule update --init

Run install (this should install dependencies)::

    python3 -m pip install --user -e .


Create translations (optional)::

    sudo apt-get install python-requests gettext
    ./contrib/pull_locale

Finally, to start Electrum::

    ./run_electrum



Creating Binaries
=================

Linux (tarball)
---------------

See :code:`contrib/build-linux/sdist/README.md`.


Linux (AppImage)
----------------

See :code:`contrib/build-linux/appimage/README.md`.


Mac OS X / macOS
----------------

See :code:`contrib/osx/README.md`.


Windows
-------

See :code:`contrib/build-wine/README.md`.


Android
-------

See :code:`contrib/android/Readme.md`.


Contributing
============

Any help testing the software, reporting or fixing bugs, reviewing pull requests
and recent changes, writing tests, or helping with outstanding issues is very welcome.
Implementing new features, or improving/refactoring the codebase, is of course
also welcome, but to avoid wasted effort, especially for larger changes,
we encourage discussing these on the issue tracker or IRC first.

Besides `GitHub`_, most communication about Electrum development happens on IRC, in the
:code:`#electrum` channel on Libera Chat. The easiest way to participate on IRC is
with the web client, `web.libera.chat`_.


.. _web.libera.chat: https://web.libera.chat/#electrum
.. _GitHub: https://github.com/spesmilo/electrum
