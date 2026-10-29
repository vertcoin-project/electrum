# Electrum-VTC

Electrum-VTC is [Electrum](https://github.com/spesmilo/electrum) with Vertcoin
chain parameters, Kimoto Gravity Well difficulty and Verthash proof-of-work.
This branch rebases the Vertcoin changes onto upstream **4.8.3**.

## 1. Differences: vertcoin-project/electrum v4.2.2 vs spesmilo/electrum 4.2.2

`v4.2.2` is upstream tag `4.2.2` plus 15 `vtc:` commits. Excluding the
directory rename, server list and checkpoints, they change about 60 files.

| Commit | What it did |
|---|---|
| `44b4a3d2f` rename inner electrum directory | `electrum/` → `electrum_vtc/` so it can be installed next to Electrum. |
| `6af12281a` adjust for renamed inner directory | Imports, `setup.py`, `run_electrum`, plugin loader, `.desktop` file → `electrum-vtc`. |
| `b3590f179` chain parameters | P2PKH 71, P2SH 5, bech32 `vtc`/`tvtc`/`vtcr`, VTC genesis hashes, ports 55001/55002, BIP44 coin type 28, GitHub URLs. Signet/simnet commented out. Testnet servers and checkpoints were left as Bitcoin's. |
| `884e9ce8a` Kimoto Gravity Well | Python KGW (floating-point `PastDifficultyAverage`), Litecoin-style retarget below 26754, forced bits at 208301, 1080000+10 and 1500000+10. `verify_header` takes bits, checks are skipped for most of the checkpoint region. |
| `1cf71235e` PoW and verthash datafile | PoW via C extensions `lyra2re_hash`, `lyra2re2_hash`, `lyra2re3_hash`, `vtc_scrypt_new`, `verthash` (pip `vertcoinhash`). At *import time* `blockchain.py` searched cwd, Vertcoin Core, Vertcoin-OCM and Electrum-VTC data dirs for `verthash.dat`, read the whole 1.2 GiB into RAM, checked its sha256, and otherwise ran a bundled `create-verthash-datafile` executable behind tkinter dialogs. `contrib/make_verthash-dat.sh` built that executable from `vertcoinhash-python`. Data dir `~/.electrum-vtc` / `%APPDATA%\Electrum-VTC`. |
| `9d0c89a80` feerates, max supply, derivation path | Supply 84M. Relay fee 100000 sat/kvB, max relay 5000000, static fee levels 100k–300k, high-fee warning 60000000. BIP39 paths `m/x'/28'/…`. `WIF_SCRIPT_TYPES['p2pkh'] = 71` (accepts Electrum-VTC 2.x WIF `0xC7` keys but **rejects standard `0x80` Vertcoin Core WIF**). Ledger `m/128'`. |
| `ce68cf78b` servers and checkpoints | 3 VTC ElectrumX servers; 861 checkpoints (to height 1,735,775) whose targets are all the placeholder `0x1e0ffff0`. |
| `4fbc0a1e3` submodules | Submodule paths for the renamed dir. |
| `57ebf648b`, `58c6c902a`, `c29d16657` build scripts | Build `create-verthash-datafile` and Tcl/Tk on all hosts; rename AppImage/Windows/macOS artifacts to Electrum-VTC; release script; `pubkeys/vertion.asc`. |
| `e633124d3` brand as Electrum-VTC | VTC units (`VTC`, `mVTC`, default 8 decimals), `vertcoin:` URI scheme, Vertcoin block explorers, Electrum-VTC in Qt titles and messages. |
| `0a91f4a91` plugin branding / disable | Rebranded hardware-wallet plugin descriptions; disabled coldcard, cosigner pool, digitalbitbox, keepkey, safe_t, trustedcoin. |
| `bd8174070` disable LN, updates, fiat, invoices | `has_lightning`/`can_have_lightning` → False, Channels tab, update check, Lightning and Fiat settings tabs and invoice import/export hidden; crash reporter no longer sends. |
| `0b1d93884` version, release notes | `ELECTRUM_VERSION = 'v4.2.2'`. |

## 2. This port onto 4.8.3

Branch `vtc-4.8.3` starts from upstream tag `4.8.3`:

1. **Rename** `electrum/` → `electrum_vtc/`. This was redone with a script on 4.8.3, not cherry-picked.
2. **Chain parameters** in 4.8.3's `chains/<net>/` layout. Bitcoin-only networks (testnet4, signet, mutinynet, simnet) are removed. Testnet now uses VTC's server (`electrumx-tvtc.javerity.com`) and no checkpoints. Mainnet has **1341 checkpoints up to height 2,703,455**, generated from vertcoind by `contrib/vtc/make_checkpoints.py` with real targets.
3. **Difficulty and PoW** (`blockchain.py`, `verthash.py`):
   - KGW is an exact integer port of `KimotoGravityWell()` from vertcoin-core `pow.cpp`: CBigNum truncating division, compact encoding, both pow limits, fork-block stops. It matched mainnet `nBits` on 133,501 checked heights, including the 26754, 1,080,000 and 1,500,000 boundaries and the last 106k blocks.
   - 4.8.3 only downloads headers above the max checkpoint. Below it, headers are only checked to link up to the checkpointed hashes. Above it, every header's `nBits` (KGW) and Verthash PoW are verified. The 2 checkpointed chunks that KGW needs as history are fetched before syncing.
   - The scrypt and Lyra2RE C extensions are no longer needed: every pre-Verthash block is far below the max checkpoint.
   - **Verthash is native Python.** `verthash.dat` is generated in about 100 s with a pure-Python port of `verthash_datfile.cpp` / verthash-go `graph.go`. The result is checked against sha256 `a55531e8…aa48`. An existing file in the Electrum-VTC, Vertcoin Core or Vertcoin-OCM data dir (or the `verthash_datafile` config path) is reused. The file is memory-mapped and checked once per mtime. A pure-Python Verthash hash takes about 16 ms per header.
   - Chainwork is summed per header, since KGW retargets every block.
   - Header chunks are verified off the asyncio event loop.
4. **Fees, supply, derivation paths**: carried over. WIF now uses the standard `0x80` prefix, the same as Vertcoin Core, and still accepts Electrum-VTC 2.x `0xC7` keys as p2pkh.
5. **Branding**: data dir, units, URI scheme, explorers, Qt titles and strings. The help-menu "Bitcoin Paper" entry is removed.
6. **Disabled**: Lightning (no lnworker is ever created), update checks, crash-report sending, the Fiat tab.

### Not carried over

These were treated as out of scope:

- The Docker-based build scripts (`contrib/build-linux`, `contrib/build-wine`, `contrib/osx`), `create-verthash-datafile` packaging and Tcl/Tk. Releases are built with Guix instead (see below). Only `make_libsecp256k1.sh` and `make_osx.sh` were updated for the renamed directory.
- Kivy GUI: upstream removed it. The QML/Android GUI is renamed but not branded or tested.
- Hardware-wallet plugin branding and disabling, and the Ledger `m/128'` path.
- Tests: `tests/` imports were renamed, but the tests have not been updated for VTC.
- Invoice import/export hiding.

## Verification (2026-10-28)

Test setup: vertcoind (bitcoin v32 rebase) in WSL with `-txindex`, ElectrumX 2.0 (`COIN=Vertcoin`), and Electrum-VTC on Windows (Python 3.14) with a fresh data dir and `--oneserver`. Results:

- The generated `verthash.dat` has the expected sha256 and is byte-identical to vertcoind's.
- The client reused Vertcoin Core's `verthash.dat` and fetched the 2 KGW-history chunks. It verified the 2,574 headers above the checkpoint (KGW and Verthash) and reached the tip at 2,706,029 in about 40 s. The tip hash matched vertcoind's `getblockhash`.
- A watch-only wallet SPV-verified its history, including a transaction below the max checkpoint. Its balance matched `scantxoutset` exactly.
- Tampered checkpoint chunks, nonces and nBits are rejected.

## Release builds (Guix)

`contrib/guix/guix-build` builds all release targets in Guix containers; see [contrib/guix/README.md](contrib/guix/README.md):
- the sdist;
- the x86_64 AppImage;
- the Windows setup, standalone and portable exes;
- the x86_64 and arm64 macOS `Electrum-VTC.app` zips.

At commit `30503e3` (2026-10-28), two clean builds of all five targets produced identical sha256s. Tested results:
- The AppImage (in WSL Ubuntu) generated `verthash.dat` natively and synced to the tip against the local ElectrumX.
- The Windows standalone exe synced to the tip on Windows 11.
- The sdist installs with `pip install 'Electrum-VTC-….tar.gz[crypto]'`.
- The macOS apps were only checked structurally (architectures, ad-hoc signatures); they have not been run on a Mac.

## Running against a local ElectrumX

```
python run_electrum --oneserver --server 127.0.0.1:55001:t
```

On first start, if no `verthash.dat` is found, Electrum-VTC generates one in its data dir before verifying headers.

To refresh the checkpoints from a synced node:

```
python3 contrib/vtc/make_checkpoints.py --rpcurl http://user:pass@127.0.0.1:5888/ --out electrum_vtc/chains/mainnet/checkpoints.json
```
