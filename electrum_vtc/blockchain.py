# Electrum - lightweight Bitcoin client
# Copyright (C) 2012 thomasv@ecdsa.org
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
import hashlib
import os
import platform
import subprocess
import sys
import threading
import time
from typing import Optional, Dict, Mapping, Sequence

from . import util
from .bitcoin import hash_encode, int_to_hex, rev_hex
from .crypto import sha256d
from . import constants
from .util import bfh, bh2u, with_lock
from .simple_config import SimpleConfig
from .logging import get_logger, Logger

import lyra2re_hash
import lyra2re2_hash
import lyra2re3_hash
import vtc_scrypt_new

import verthash

import tkinter as tk
from tkinter import messagebox

# Script paths and execution
SCRIPT_FILE = os.path.abspath(os.path.realpath(__file__))
SCRIPT_FNAME = os.path.basename(SCRIPT_FILE)
SCRIPT_NAME, SCRIPT_EXT = os.path.splitext(SCRIPT_FNAME)
SCRIPT_DIR = os.path.dirname(SCRIPT_FILE)

verthash_exe_fname = 'create-verthash-datafile.exe' if platform.system() == 'Windows' else 'create-verthash-datafile'
create_verthash_exe = os.path.join(SCRIPT_DIR, verthash_exe_fname)

config = SimpleConfig()
electrum_dir = config.electrum_path()
default_verthash_datafile = os.path.join(electrum_dir, 'verthash.dat')
vertcoin_dir = config.vertcoin_path()
ocm_dir = config.ocm_path()

verthash_datafile_dir = None
verthash_datafile = None
verthash_data = None

_logger = get_logger(__name__)

def create_verthash_datafile(create_verthash_exe, output_file=default_verthash_datafile, overwrite=False):
    if os.path.isfile(output_file):
        if overwrite:
            os.remove(output_file)
        else:
            _logger.info("In call to create_verthash_datafile, output file already exists: {}".format(output_file))
            return output_file
    cmd_args = [create_verthash_exe]
    cmd_args.extend(['-o', default_verthash_datafile])
    print(cmd_args)

    root = tk.Tk()
    width = 620
    height = 30
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width/2) - (width/2)
    y = (screen_height/2) - (height/2)
    root.geometry('%dx%d+%d+%d' % (width, height, x, y))
    root.resizable(False, False)
    root.title("Electrum-VTC")

    l = tk.Label(root, text="Creating Verthash Datafile - may take several minutes".format(electrum_dir))
    l.config(font=("Roboto", 12))
    l.pack()

    try:
        root.update()
        subprocess.call(cmd_args)
        root.destroy()
    except KeyboardInterrupt:
        os.remove(output_file)
        sys.exit(0)
    return output_file

existing_verthash_datafile = None

possible_data_dirs = [os.getcwd(), vertcoin_dir, ocm_dir, electrum_dir]
for verthash_datafile_dir in possible_data_dirs:
    verthash_datafile = os.path.join(verthash_datafile_dir, 'verthash.dat')
    if os.path.isfile(verthash_datafile):
        _logger.info("Checking verthash.dat: {}".format(verthash_datafile_dir))
        with open(verthash_datafile, 'rb') as f:
            verthash_data = f.read()
        verthash_sum = hashlib.sha256(verthash_data).hexdigest()
        _logger.info("sha256sum verthash.dat {}".format(verthash_sum))
        if verthash_sum == 'a55531e843cd56b010114aaf6325b0d529ecf88f8ad47639b6ededafd721aa48':
            _logger.info("Good checksum")
            existing_verthash_datafile = verthash_datafile
            break
        else:
            _logger.warning("Bad checksum: {}".format(verthash_datafile))
            if verthash_datafile_dir == electrum_dir:
                _logger.info("Bad sha256sum")
                err = tk.Tk()
                err.withdraw()
                messagebox.showwarning("Electrum-VTC", "Bad verthash datafile: {}".format(verthash_datafile_dir))
                err.update()

if existing_verthash_datafile is not None:
    verthash_datafile = existing_verthash_datafile
else:
    if os.path.isfile(create_verthash_exe):
        verthash_datafile = default_verthash_datafile
        verthash_datafile_dir = os.path.dirname(verthash_datafile)
        err = tk.Tk()
        err.withdraw()
        messagebox.showinfo("Electrum-VTC", "Click OK to create verthash.dat to {}".format(verthash_datafile_dir))
        err.update()
        _logger.info("Creating verthash.dat: {}".format(verthash_datafile_dir))
        create_verthash_datafile(create_verthash_exe, output_file=verthash_datafile, overwrite=True)
        with open(verthash_datafile, 'rb') as f:
            verthash_data = f.read()
        verthash_sum = hashlib.sha256(verthash_data).hexdigest()
        _logger.info("sha256sum verthash.dat {}".format(verthash_sum))
        if verthash_sum != 'a55531e843cd56b010114aaf6325b0d529ecf88f8ad47639b6ededafd721aa48':
            _logger.info("Bad checksum - Restart Electrum-VTC".format(verthash_sum))
            err = tk.Tk()
            err.withdraw()
            messagebox.showwarning("Bad verthash datafile", "Restart Electrum-VTC".format(verthash_datafile_dir))
            err.update()
            sys.exit(1)
        else:
            _logger.info("Good checksum")
    else:
        print("create-verthash-datafile executable needed")
        print("Run ./contrib/make_verthash-dat.sh")
        sys.exit(0)

verthash_datafile_dir = os.path.dirname(verthash_datafile)

def verthash_hash(dat):
    return verthash.getPoWHash(dat, verthash_data)

HEADER_SIZE = 80  # bytes

# see https://github.com/vertcoin-project/vertcoin-core/blob/master/src/chainparams.cpp#L82
MAX_TARGET = 0X7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
PRE_VERTHASH_MAX_TARGET = 0x00000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF


class MissingHeader(Exception):
    pass

class InvalidHeader(Exception):
    pass

def serialize_header(header_dict: dict) -> str:
    s = int_to_hex(header_dict['version'], 4) \
        + rev_hex(header_dict['prev_block_hash']) \
        + rev_hex(header_dict['merkle_root']) \
        + int_to_hex(int(header_dict['timestamp']), 4) \
        + int_to_hex(int(header_dict['bits']), 4) \
        + int_to_hex(int(header_dict['nonce']), 4)
    return s

def deserialize_header(s: bytes, height: int) -> dict:
    if not s:
        raise InvalidHeader('Invalid header: {}'.format(s))
    if len(s) != HEADER_SIZE:
        raise InvalidHeader('Invalid header length: {}'.format(len(s)))
    hex_to_int = lambda s: int.from_bytes(s, byteorder='little')
    h = {}
    h['version'] = hex_to_int(s[0:4])
    h['prev_block_hash'] = hash_encode(s[4:36])
    h['merkle_root'] = hash_encode(s[36:68])
    h['timestamp'] = hex_to_int(s[68:72])
    h['bits'] = hex_to_int(s[72:76])
    h['nonce'] = hex_to_int(s[76:80])
    h['block_height'] = height
    return h

def hash_header(header: dict) -> str:
    if header is None:
        return '0' * 64
    if header.get('prev_block_hash') is None:
        header['prev_block_hash'] = '00'*32
    return hash_raw_header(serialize_header(header))


def hash_raw_header(header: str) -> str:
    return hash_encode(sha256d(bfh(header)))

def pow_hash_header(header):
    height = header.get('block_height')
    header_bytes = bfh(serialize_header(header))
    if height >= 1500000:
        return hash_encode(verthash_hash(header_bytes))
    if height > 1080000:
        return hash_encode(lyra2re3_hash.getPoWHash(header_bytes))
    elif height >= 347000:
        return hash_encode(lyra2re2_hash.getPoWHash(header_bytes))
    elif height >= 208301:
        return hash_encode(lyra2re_hash.getPoWHash(header_bytes))
    else:
        return hash_encode(vtc_scrypt_new.getPoWHash(header_bytes))

# key: blockhash hex at forkpoint
# the chain at some key is the best chain that includes the given hash
blockchains = {}  # type: Dict[str, Blockchain]
blockchains_lock = threading.RLock()  # lock order: take this last; so after Blockchain.lock


def read_blockchains(config: 'SimpleConfig'):
    best_chain = Blockchain(config=config,
                            forkpoint=0,
                            parent=None,
                            forkpoint_hash=constants.net.GENESIS,
                            prev_hash=None)
    blockchains[constants.net.GENESIS] = best_chain
    # consistency checks
    if best_chain.height() > constants.net.max_checkpoint():
        header_after_cp = best_chain.read_header(constants.net.max_checkpoint()+1)
        if not header_after_cp or not best_chain.can_connect(header_after_cp, check_height=False):
            _logger.info("[blockchain] deleting best chain. cannot connect header after last cp to last cp.")
            os.unlink(best_chain.path())
            best_chain.update_size()
    # forks
    fdir = os.path.join(util.get_headers_dir(config), 'forks')
    util.make_dir(fdir)
    # files are named as: fork2_{forkpoint}_{prev_hash}_{first_hash}
    l = filter(lambda x: x.startswith('fork2_') and '.' not in x, os.listdir(fdir))
    l = sorted(l, key=lambda x: int(x.split('_')[1]))  # sort by forkpoint

    def delete_chain(filename, reason):
        _logger.info(f"[blockchain] deleting chain {filename}: {reason}")
        os.unlink(os.path.join(fdir, filename))

    def instantiate_chain(filename):
        __, forkpoint, prev_hash, first_hash = filename.split('_')
        forkpoint = int(forkpoint)
        prev_hash = (64-len(prev_hash)) * "0" + prev_hash  # left-pad with zeroes
        first_hash = (64-len(first_hash)) * "0" + first_hash
        # forks below the max checkpoint are not allowed
        if forkpoint <= constants.net.max_checkpoint():
            delete_chain(filename, "deleting fork below max checkpoint")
            return
        # find parent (sorting by forkpoint guarantees it's already instantiated)
        for parent in blockchains.values():
            if parent.check_hash(forkpoint - 1, prev_hash):
                break
        else:
            delete_chain(filename, "cannot find parent for chain")
            return
        b = Blockchain(config=config,
                       forkpoint=forkpoint,
                       parent=parent,
                       forkpoint_hash=first_hash,
                       prev_hash=prev_hash)
        # consistency checks
        h = b.read_header(b.forkpoint)
        if first_hash != hash_header(h):
            delete_chain(filename, "incorrect first hash for chain")
            return
        if not b.parent.can_connect(h, check_height=False):
            delete_chain(filename, "cannot connect chain to parent")
            return
        chain_id = b.get_id()
        assert first_hash == chain_id, (first_hash, chain_id)
        blockchains[chain_id] = b

    for filename in l:
        instantiate_chain(filename)


def get_best_chain() -> 'Blockchain':
    return blockchains[constants.net.GENESIS]

# block hash -> chain work; up to and including that block
_CHAINWORK_CACHE = {
    "0000000000000000000000000000000000000000000000000000000000000000": 0,  # virtual block at height -1
}  # type: Dict[str, int]


def init_headers_file_for_best_chain():
    b = get_best_chain()
    filename = b.path()
    length = HEADER_SIZE * len(constants.net.CHECKPOINTS) * 2016
    if not os.path.exists(filename) or os.path.getsize(filename) < length:
        with open(filename, 'wb') as f:
            if length > 0:
                f.seek(length - 1)
                f.write(b'\x00')
        util.ensure_sparse_file(filename)
    with b.lock:
        b.update_size()


class Blockchain(Logger):
    """
    Manages blockchain headers and their verification
    """

    def __init__(self, config: SimpleConfig, forkpoint: int, parent: Optional['Blockchain'],
                 forkpoint_hash: str, prev_hash: Optional[str]):
        assert isinstance(forkpoint_hash, str) and len(forkpoint_hash) == 64, forkpoint_hash
        assert (prev_hash is None) or (isinstance(prev_hash, str) and len(prev_hash) == 64), prev_hash
        # assert (parent is None) == (forkpoint == 0)
        if 0 < forkpoint <= constants.net.max_checkpoint():
            raise Exception(f"cannot fork below max checkpoint. forkpoint: {forkpoint}")
        Logger.__init__(self)
        self.config = config
        self.forkpoint = forkpoint  # height of first header
        self.parent = parent
        self._forkpoint_hash = forkpoint_hash  # blockhash at forkpoint. "first hash"
        self._prev_hash = prev_hash  # blockhash immediately before forkpoint
        self.lock = threading.RLock()
        self.update_size()

    @property
    def checkpoints(self):
        return constants.net.CHECKPOINTS

    def get_max_child(self) -> Optional[int]:
        children = self.get_direct_children()
        return max([x.forkpoint for x in children]) if children else None

    def get_max_forkpoint(self) -> int:
        """Returns the max height where there is a fork
        related to this chain.
        """
        mc = self.get_max_child()
        return mc if mc is not None else self.forkpoint

    def get_direct_children(self) -> Sequence['Blockchain']:
        with blockchains_lock:
            return list(filter(lambda y: y.parent==self, blockchains.values()))

    def get_parent_heights(self) -> Mapping['Blockchain', int]:
        """Returns map: (parent chain -> height of last common block)"""
        with self.lock, blockchains_lock:
            result = {self: self.height()}
            chain = self
            while True:
                parent = chain.parent
                if parent is None: break
                result[parent] = chain.forkpoint - 1
                chain = parent
            return result

    def get_height_of_last_common_block_with_chain(self, other_chain: 'Blockchain') -> int:
        last_common_block_height = 0
        our_parents = self.get_parent_heights()
        their_parents = other_chain.get_parent_heights()
        for chain in our_parents:
            if chain in their_parents:
                h = min(our_parents[chain], their_parents[chain])
                last_common_block_height = max(last_common_block_height, h)
        return last_common_block_height

    @with_lock
    def get_branch_size(self) -> int:
        return self.height() - self.get_max_forkpoint() + 1

    def get_name(self) -> str:
        return self.get_hash(self.get_max_forkpoint()).lstrip('0')[0:10]

    def check_header(self, header: dict) -> bool:
        header_hash = hash_header(header)
        height = header.get('block_height')
        return self.check_hash(height, header_hash)

    def check_hash(self, height: int, header_hash: str) -> bool:
        """Returns whether the hash of the block at given height
        is the given hash.
        """
        assert isinstance(header_hash, str) and len(header_hash) == 64, header_hash  # hex
        try:
            return header_hash == self.get_hash(height)
        except Exception:
            return False

    def fork(parent, header: dict) -> 'Blockchain':
        if not parent.can_connect(header, check_height=False):
            raise Exception("forking header does not connect to parent chain")
        forkpoint = header.get('block_height')
        self = Blockchain(config=parent.config,
                          forkpoint=forkpoint,
                          parent=parent,
                          forkpoint_hash=hash_header(header),
                          prev_hash=parent.get_hash(forkpoint-1))
        self.assert_headers_file_available(parent.path())
        open(self.path(), 'w+').close()
        self.save_header(header)
        # put into global dict. note that in some cases
        # save_header might have already put it there but that's OK
        chain_id = self.get_id()
        with blockchains_lock:
            blockchains[chain_id] = self
        return self

    @with_lock
    def height(self) -> int:
        return self.forkpoint + self.size() - 1

    @with_lock
    def size(self) -> int:
        return self._size

    @with_lock
    def update_size(self) -> None:
        p = self.path()
        self._size = os.path.getsize(p)//HEADER_SIZE if os.path.exists(p) else 0

    @classmethod
    def verify_header(cls, header: dict, prev_hash: str, bits, target: int, check_bits_target=True, expected_header_hash: str=None) -> None:
        _hash = hash_header(header)
        if expected_header_hash and expected_header_hash != _hash:
            raise Exception("hash mismatches with expected: {} vs {}".format(expected_header_hash, _hash))
        if prev_hash != header.get('prev_block_hash'):
            raise Exception("prev hash mismatch: %s vs %s" % (prev_hash, header.get('prev_block_hash')))
        if constants.net.TESTNET:
            return
        if check_bits_target:
            if bits != header.get('bits'):
                raise Exception("bits mismatch: %s vs %s" % (bits, header.get('bits')))

            _powhash = pow_hash_header(header)
            block_hash_as_num = int.from_bytes(bfh(_powhash), byteorder='big')
            if block_hash_as_num > target:
                raise Exception(f"insufficient proof of work: {block_hash_as_num} vs target {target}")

    def should_check_bits_target(self, height):
        index = height // 2016
        return (index > len(self.checkpoints) + 1) or \
               (index < len(self.checkpoints) and height % 2016 == 0)

    def verify_chunk(self, index: int, data: bytes) -> None:
        num = len(data) // HEADER_SIZE
        start_height = index * 2016
        prev_hash = self.get_hash(start_height - 1)
        target = self.get_target(index-1)
        headers = {}
        for i in range(num):
            height = start_height + i
            try:
                expected_header_hash = self.get_hash(height)
            except MissingHeader:
                expected_header_hash = None
            raw_header = data[i*HEADER_SIZE : (i+1)*HEADER_SIZE]
            header = deserialize_header(raw_header, index*2016 + i)
            headers[header.get('block_height')] = header

            bits, target = None, None
            check_bits_target = self.should_check_bits_target(index * 2016 + i)
            if(check_bits_target):
                bits, target = self.get_target(index * 2016 + i, headers)

            self.verify_header(header, prev_hash, bits, target, check_bits_target, expected_header_hash)
            prev_hash = hash_header(header)

    @with_lock
    def path(self):
        d = util.get_headers_dir(self.config)
        if self.parent is None:
            filename = 'blockchain_headers'
        else:
            assert self.forkpoint > 0, self.forkpoint
            prev_hash = self._prev_hash.lstrip('0')
            first_hash = self._forkpoint_hash.lstrip('0')
            basename = f'fork2_{self.forkpoint}_{prev_hash}_{first_hash}'
            filename = os.path.join('forks', basename)
        return os.path.join(d, filename)

    @with_lock
    def save_chunk(self, index: int, chunk: bytes):
        assert index >= 0, index
        chunk_within_checkpoint_region = index < len(self.checkpoints)
        # chunks in checkpoint region are the responsibility of the 'main chain'
        if chunk_within_checkpoint_region and self.parent is not None:
            main_chain = get_best_chain()
            main_chain.save_chunk(index, chunk)
            return

        delta_height = (index * 2016 - self.forkpoint)
        delta_bytes = delta_height * HEADER_SIZE
        # if this chunk contains our forkpoint, only save the part after forkpoint
        # (the part before is the responsibility of the parent)
        if delta_bytes < 0:
            chunk = chunk[-delta_bytes:]
            delta_bytes = 0
        truncate = not chunk_within_checkpoint_region
        self.write(chunk, delta_bytes, truncate)
        self.swap_with_parent()

    def swap_with_parent(self) -> None:
        with self.lock, blockchains_lock:
            # do the swap; possibly multiple ones
            cnt = 0
            while True:
                old_parent = self.parent
                if not self._swap_with_parent():
                    break
                # make sure we are making progress
                cnt += 1
                if cnt > len(blockchains):
                    raise Exception(f'swapping fork with parent too many times: {cnt}')
                # we might have become the parent of some of our former siblings
                for old_sibling in old_parent.get_direct_children():
                    if self.check_hash(old_sibling.forkpoint - 1, old_sibling._prev_hash):
                        old_sibling.parent = self

    def _swap_with_parent(self) -> bool:
        """Check if this chain became stronger than its parent, and swap
        the underlying files if so. The Blockchain instances will keep
        'containing' the same headers, but their ids change and so
        they will be stored in different files."""
        if self.parent is None:
            return False
        if self.parent.get_chainwork() >= self.get_chainwork():
            return False
        self.logger.info(f"swapping {self.forkpoint} {self.parent.forkpoint}")
        parent_branch_size = self.parent.height() - self.forkpoint + 1
        forkpoint = self.forkpoint  # type: Optional[int]
        parent = self.parent  # type: Optional[Blockchain]
        child_old_id = self.get_id()
        parent_old_id = parent.get_id()
        # swap files
        # child takes parent's name
        # parent's new name will be something new (not child's old name)
        self.assert_headers_file_available(self.path())
        child_old_name = self.path()
        with open(self.path(), 'rb') as f:
            my_data = f.read()
        self.assert_headers_file_available(parent.path())
        assert forkpoint > parent.forkpoint, (f"forkpoint of parent chain ({parent.forkpoint}) "
                                              f"should be at lower height than children's ({forkpoint})")
        with open(parent.path(), 'rb') as f:
            f.seek((forkpoint - parent.forkpoint)*HEADER_SIZE)
            parent_data = f.read(parent_branch_size*HEADER_SIZE)
        self.write(parent_data, 0)
        parent.write(my_data, (forkpoint - parent.forkpoint)*HEADER_SIZE)
        # swap parameters
        self.parent, parent.parent = parent.parent, self  # type: Optional[Blockchain], Optional[Blockchain]
        self.forkpoint, parent.forkpoint = parent.forkpoint, self.forkpoint
        self._forkpoint_hash, parent._forkpoint_hash = parent._forkpoint_hash, hash_raw_header(bh2u(parent_data[:HEADER_SIZE]))
        self._prev_hash, parent._prev_hash = parent._prev_hash, self._prev_hash
        # parent's new name
        os.replace(child_old_name, parent.path())
        self.update_size()
        parent.update_size()
        # update pointers
        blockchains.pop(child_old_id, None)
        blockchains.pop(parent_old_id, None)
        blockchains[self.get_id()] = self
        blockchains[parent.get_id()] = parent
        return True

    def get_id(self) -> str:
        return self._forkpoint_hash

    def assert_headers_file_available(self, path):
        if os.path.exists(path):
            return
        elif not os.path.exists(util.get_headers_dir(self.config)):
            raise FileNotFoundError('Electrum headers_dir does not exist. Was it deleted while running?')
        else:
            raise FileNotFoundError('Cannot find headers file but headers_dir is there. Should be at {}'.format(path))

    @with_lock
    def write(self, data: bytes, offset: int, truncate: bool=True) -> None:
        filename = self.path()
        self.assert_headers_file_available(filename)
        with open(filename, 'rb+') as f:
            if truncate and offset != self._size * HEADER_SIZE:
                f.seek(offset)
                f.truncate()
            f.seek(offset)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        self.update_size()

    @with_lock
    def save_header(self, header: dict) -> None:
        delta = header.get('block_height') - self.forkpoint
        data = bfh(serialize_header(header))
        # headers are only _appended_ to the end:
        assert delta == self.size(), (delta, self.size())
        assert len(data) == HEADER_SIZE
        self.write(data, delta*HEADER_SIZE)
        self.swap_with_parent()

    @with_lock
    def read_header(self, height: int) -> Optional[dict]:
        if height < 0:
            return
        if height < self.forkpoint:
            return self.parent.read_header(height)
        if height > self.height():
            return
        delta = height - self.forkpoint
        name = self.path()
        self.assert_headers_file_available(name)
        with open(name, 'rb') as f:
            f.seek(delta * HEADER_SIZE)
            h = f.read(HEADER_SIZE)
            if len(h) < HEADER_SIZE:
                raise Exception('Expected to read a full header. This was only {} bytes'.format(len(h)))
        if h == bytes([0])*HEADER_SIZE:
            return None
        return deserialize_header(h, height)

    def header_at_tip(self) -> Optional[dict]:
        """Return latest header."""
        height = self.height()
        return self.read_header(height)

    def is_tip_stale(self) -> bool:
        STALE_DELAY = 8 * 60 * 60  # in seconds
        header = self.header_at_tip()
        if not header:
            return True
        # note: We check the timestamp only in the latest header.
        #       The Bitcoin consensus has a lot of leeway here:
        #       - needs to be greater than the median of the timestamps of the past 11 blocks, and
        #       - up to at most 2 hours into the future compared to local clock
        #       so there is ~2 hours of leeway in either direction
        if header['timestamp'] + STALE_DELAY < time.time():
            return True
        return False

    def get_hash(self, height: int) -> str:
        def is_height_checkpoint():
            within_cp_range = height <= constants.net.max_checkpoint()
            at_chunk_boundary = (height+1) % 2016 == 0
            return within_cp_range and at_chunk_boundary

        if height == -1:
            return '0000000000000000000000000000000000000000000000000000000000000000'
        elif height == 0:
            return constants.net.GENESIS
        elif is_height_checkpoint():
            index = height // 2016
            h, t = self.checkpoints[index]
            return h
        else:
            header = self.read_header(height)
            if header is None:
                raise MissingHeader(height)
            return hash_header(header)

    def convbits(self, new_target):
        c = ("%064x" % int(new_target))[2:]
        while c[:2] == '00' and len(c) > 6:
            c = c[2:]
        bitsN, bitsBase = len(c) // 2, int('0x' + c[:6], 16)
        if bitsBase >= 0x800000:
            bitsN += 1
            bitsBase >>= 8
        new_bits = bitsN << 24 | bitsBase
        return new_bits

    def convbignum(self, bits):
        bitsN = (bits >> 24) & 0xff
        if not (bitsN >= 0x03 and bitsN <= 0x1e):
            raise BaseException("First part of bits should be in [0x03, 0x1e]")
        bitsBase = bits & 0xffffff
        if not (bitsBase >= 0x8000 and bitsBase <= 0x7fffff):
            raise BaseException("Second part of bits should be in [0x8000, 0x7fffff]")
        target = bitsBase << (8 * (bitsN-3))
        return target

    def KimotoGravityWell(self, height, chain={}):
        BlocksTargetSpacing = 2.5 * 60  # 2.5 minutes
        TimeDaySeconds = 60 * 60 * 24
        PastSecondsMin = TimeDaySeconds * 0.25
        PastSecondsMax = TimeDaySeconds * 7
        PastBlocksMin = PastSecondsMin / BlocksTargetSpacing
        PastBlocksMax = PastSecondsMax / BlocksTargetSpacing

        BlockReadingIndex = height - 1
        BlockLastSolvedIndex = height - 1
        TargetBlocksSpacingSeconds = BlocksTargetSpacing
        PastRateAdjustmentRatio = 1.0
        bnProofOfWorkLimit = 0X7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
        bnPreVerthashProofOfWorkLimit = 0x00000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF

        if (BlockLastSolvedIndex <= 0 or BlockLastSolvedIndex < PastSecondsMin):
            new_target = bnProofOfWorkLimit
            new_bits = self.convbits(new_target)
            return new_bits, new_target

        last = chain.get(BlockLastSolvedIndex)
        if last == None:
            last = self.read_header(BlockLastSolvedIndex)

        for i in range(1, int(PastBlocksMax)+1):
            PastBlocksMass = i

            reading = chain.get(BlockReadingIndex)
            if reading == None:
                reading = self.read_header(BlockReadingIndex)
                chain[BlockReadingIndex] = reading

            if (reading == None or last == None):
                raise BaseException("Could not find previous blocks when calculating difficulty reading: " + str(BlockReadingIndex) + ", last: " + str(BlockLastSolvedIndex) + ", height: " + str(height))

            if (i == 1):
                PastDifficultyAverage = self.convbignum(reading.get('bits'))
            else:
                PastDifficultyAverage = float((self.convbignum(reading.get('bits')) - PastDifficultyAveragePrev) / float(i)) + PastDifficultyAveragePrev

            PastDifficultyAveragePrev = PastDifficultyAverage

            PastRateActualSeconds = last.get('timestamp') - reading.get('timestamp')
            PastRateTargetSeconds = TargetBlocksSpacingSeconds * PastBlocksMass
            PastRateAdjustmentRatio = 1.0
            if (PastRateActualSeconds < 0):
                PastRateActualSeconds = 0.0

            if (PastRateActualSeconds != 0 and PastRateTargetSeconds != 0):
                PastRateAdjustmentRatio = float(PastRateTargetSeconds) / float(PastRateActualSeconds)

            EventHorizonDeviation = 1 + (0.7084 * pow(float(PastBlocksMass)/float(144), -1.228))
            EventHorizonDeviationFast = EventHorizonDeviation
            EventHorizonDeviationSlow = float(1) / float(EventHorizonDeviation)

            if (PastBlocksMass >= PastBlocksMin):
                if ((PastRateAdjustmentRatio <= EventHorizonDeviationSlow) or (PastRateAdjustmentRatio >= EventHorizonDeviationFast)):
                    break

            if (BlockReadingIndex < 1 or (BlockReadingIndex in (1080000, 1500000) and not constants.net.TESTNET)):
                break

            BlockReadingIndex = BlockReadingIndex - 1

        bnNew = PastDifficultyAverage
        if (PastRateActualSeconds != 0 and PastRateTargetSeconds != 0):
            bnNew *= float(PastRateActualSeconds)
            bnNew /= float(PastRateTargetSeconds)

        if BlockLastSolvedIndex >= 1500000:
            if bnNew > bnProofOfWorkLimit:
                bnNew = bnProofOfWorkLimit
        elif bnNew > bnPreVerthashProofOfWorkLimit:
            bnNew = bnPreVerthashProofOfWorkLimit

        # new target
        new_target = bnNew
        new_bits = self.convbits(new_target)

        #print_msg("bits", new_bits , "(", hex(new_bits),")")
        #print_msg ("PastRateAdjustmentRatio=",PastRateAdjustmentRatio,"EventHorizonDeviationSlow",EventHorizonDeviationSlow,"PastSecondsMin=",PastSecondsMin,"PastSecondsMax=",PastSecondsMax,"PastBlocksMin=",PastBlocksMin,"PastBlocksMax=",PastBlocksMax)
        return new_bits, new_target


    def get_target(self, height, chain={}):
        if constants.net.TESTNET:
            return 0, 0
        if height <= 0 or height == 208301:
            return 0x1e0ffff0, 0x00000FFFF0000000000000000000000000000000000000000000000000000000
        if height == 468741:
            bits = 469820683
            bitsBase = bits & 0xffffff
            bitsN = (bits >> 24) & 0xff
            target = bitsBase << (8 * (bitsN - 3))
            return bits, target
        if height >= 1080000 and height < 1080010:
            bits = 0x1b0ffff0
            return bits, self.convbignum(bits)
        if height >= 1500000 and height < 1500010:
            bits = 0x1c07fff8
            return bits, self.convbignum(bits)
        index = height // 2016
        if index < len(self.checkpoints):
            h, t = self.checkpoints[index]
            return t
        if height < 26754:
            # Litecoin: go back the full period unless it's the first retarget
            first = self.read_header((height - 2016 - 1 if height > 2016 else 0))
            last = self.read_header(height - 1)
            if last is None:
                last = chain.get(height - 1)
            assert last is not None
            # bits to target
            bits = last.get('bits')
            bitsN = (bits >> 24) & 0xff
            if not (bitsN >= 0x03 and bitsN <= 0x1e):
                raise BaseException("First part of bits should be in [0x03, 0x1e]")
            bitsBase = bits & 0xffffff
            if not (bitsBase >= 0x8000 and bitsBase <= 0x7fffff):
                raise BaseException("Second part of bits should be in [0x8000, 0x7fffff]")
            target = bitsBase << (8 * (bitsN-3))
            if height % 2016 != 0:
                return bits, target
            # new target
            nActualTimespan = last.get('timestamp') - first.get('timestamp')
            nTargetTimespan = 84 * 60 * 60
            nActualTimespan = max(nActualTimespan, nTargetTimespan // 4)
            nActualTimespan = min(nActualTimespan, nTargetTimespan * 4)
            new_target = min(PRE_VERTHASH_MAX_TARGET, (target*nActualTimespan) // nTargetTimespan)
            # convert new target to bits
            c = ("%064x" % int(new_target))[2:]
            while c[:2] == '00' and len(c) > 6:
                c = c[2:]
            bitsN, bitsBase = len(c) // 2, int('0x' + c[:6], 16)
            if bitsBase >= 0x800000:
                bitsN += 1
                bitsBase >>= 8
            new_bits = bitsN << 24 | bitsBase
            return new_bits, bitsBase << (8 * (bitsN-3))
        else:
            return self.KimotoGravityWell(height, chain)

    @classmethod
    def bits_to_target(cls, bits: int) -> int:
        # arith_uint256::SetCompact in Bitcoin Core
        if not (0 <= bits < (1 << 32)):
            raise Exception(f"bits should be uint32. got {bits!r}")
        bitsN = (bits >> 24) & 0xff
        bitsBase = bits & 0x7fffff
        if bitsN <= 3:
            target = bitsBase >> (8 * (3-bitsN))
        else:
            target = bitsBase << (8 * (bitsN-3))
        if target != 0 and bits & 0x800000 != 0:
            # Bit number 24 (0x800000) represents the sign of N
            raise Exception("target cannot be negative")
        if (target != 0 and
                (bitsN > 34 or
                 (bitsN > 33 and bitsBase > 0xff) or
                 (bitsN > 32 and bitsBase > 0xffff))):
            raise Exception("target has overflown")
        return target

    @classmethod
    def target_to_bits(cls, target: int) -> int:
        # arith_uint256::GetCompact in Bitcoin Core
        # see https://github.com/bitcoin/bitcoin/blob/7fcf53f7b4524572d1d0c9a5fdc388e87eb02416/src/arith_uint256.cpp#L223
        c = target.to_bytes(length=32, byteorder='big')
        bitsN = len(c)
        while bitsN > 0 and c[0] == 0:
            c = c[1:]
            bitsN -= 1
            if len(c) < 3:
                c += b'\x00'
        bitsBase = int.from_bytes(c[:3], byteorder='big')
        if bitsBase >= 0x800000:
            bitsN += 1
            bitsBase >>= 8
        return bitsN << 24 | bitsBase

    def chainwork_of_header_at_height(self, height: int) -> int:
        """work done by single header at given height"""
        chunk_idx = height // 2016 - 1
        target = self.get_target(chunk_idx)
        work = ((2 ** 256 - target - 1) // (target + 1)) + 1
        return work

    @with_lock
    def get_chainwork(self, height=None) -> int:
        if height is None:
            height = max(0, self.height())
        if constants.net.TESTNET:
            # On testnet/regtest, difficulty works somewhat different.
            # It's out of scope to properly implement that.
            return height
        last_retarget = height // 2016 * 2016 - 1
        cached_height = last_retarget
        while _CHAINWORK_CACHE.get(self.get_hash(cached_height)) is None:
            if cached_height <= -1:
                break
            cached_height -= 2016
        assert cached_height >= -1, cached_height
        running_total = _CHAINWORK_CACHE[self.get_hash(cached_height)]
        while cached_height < last_retarget:
            cached_height += 2016
            work_in_single_header = self.chainwork_of_header_at_height(cached_height)
            work_in_chunk = 2016 * work_in_single_header
            running_total += work_in_chunk
            _CHAINWORK_CACHE[self.get_hash(cached_height)] = running_total
        cached_height += 2016
        work_in_single_header = self.chainwork_of_header_at_height(cached_height)
        work_in_last_partial_chunk = (height % 2016 + 1) * work_in_single_header
        return running_total + work_in_last_partial_chunk

    def can_connect(self, header: dict, check_height: bool=True) -> bool:
        if header is None:
            return False
        height = header['block_height']
        if check_height and self.height() != height - 1:
            return False
        if height == 0:
            return hash_header(header) == constants.net.GENESIS
        try:
            prev_hash = self.get_hash(height - 1)
        except:
            return False
        if prev_hash != header.get('prev_block_hash'):
            return False
        bits, target = None, None
        check_bits_target = self.should_check_bits_target(height)
        if(check_bits_target):
            bits, target = self.get_target(height)
        try:
            self.verify_header(header, prev_hash, bits, target, check_bits_target)
        except BaseException as e:
            return False
        return True

    def connect_chunk(self, idx: int, hexdata: str) -> bool:
        assert idx >= 0, idx
        try:
            data = bfh(hexdata)
            self.verify_chunk(idx, data)
            self.save_chunk(idx, data)
            return True
        except BaseException as e:
            self.logger.info(f'verify_chunk idx {idx} failed: {repr(e)}')
            return False

    def get_checkpoints(self):
        # for each chunk, store the hash of the last block and the target after the chunk
        cp = []
        n = self.height() // 2016
        for index in range(n):
            h = self.get_hash((index+1) * 2016 -1)
            target = self.get_target(index)
            cp.append((h, target))
        return cp


def check_header(header: dict) -> Optional[Blockchain]:
    """Returns any Blockchain that contains header, or None."""
    if type(header) is not dict:
        return None
    with blockchains_lock: chains = list(blockchains.values())
    for b in chains:
        if b.check_header(header):
            return b
    return None


def can_connect(header: dict) -> Optional[Blockchain]:
    """Returns the Blockchain that has a tip that directly links up
    with header, or None.
    """
    with blockchains_lock: chains = list(blockchains.values())
    for b in chains:
        if b.can_connect(header):
            return b
    return None


def get_chains_that_contain_header(height: int, header_hash: str) -> Sequence[Blockchain]:
    """Returns a list of Blockchains that contain header, best chain first."""
    with blockchains_lock: chains = list(blockchains.values())
    chains = [chain for chain in chains
              if chain.check_hash(height=height, header_hash=header_hash)]
    chains = sorted(chains, key=lambda x: x.get_chainwork(), reverse=True)
    return chains
