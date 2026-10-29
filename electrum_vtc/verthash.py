# Electrum-VTC - lightweight Vertcoin client
#
# Verthash proof-of-work and native generation of the Verthash datafile.
#
# The datafile is a ~1.2 GiB proof-of-space graph built from SHA3-256 hashes.
# This is a port of vertcoin-core's src/crypto/verthash_datfile.cpp
# (also see github.com/gertjaap/verthash-go graph.go) and src/crypto/verthash.cpp.
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

import errno
import functools
import hashlib
import mmap
import multiprocessing
import os
import shutil
import struct
import sys
import threading
import time
from typing import Callable, Optional, Sequence, TYPE_CHECKING

from .logging import get_logger

if TYPE_CHECKING:
    from .simple_config import SimpleConfig


_logger = get_logger(__name__)

# Optional C implementation from the vertcoinhash package (an absolute import: its
# module is also called verthash). Used only if it agrees with verthash_pow().
try:
    import verthash as _vertcoinhash
except ImportError:
    _vertcoinhash = None

DATAFILE_NAME = 'verthash.dat'
GRAPH_INDEX = 17
NODE_SIZE = 32
# sha256 of the datafile, as hex string (vertcoin-core stores it byte-reversed as a uint256)
DATAFILE_SHA256 = 'a55531e843cd56b010114aaf6325b0d529ecf88f8ad47639b6ededafd721aa48'

HEADER_SIZE = 80
HASH_OUT_SIZE = 32
P0_SIZE = 64
N_ITER = 8
N_SUBSET = P0_SIZE * N_ITER
N_ROT = 32
N_INDEXES = 4096
BYTE_ALIGNMENT = 16

_FNV_PRIME = 0x1000193
_FNV_OFFSET = 0x811c9dc5
_M32 = 0xffffffff


class VerthashDatafileError(Exception):
    pass


# ---------------------------------------------------------------------------
# Datafile generation
# ---------------------------------------------------------------------------

def _num_xi(index: int) -> int:
    return (1 << index) * (index + 1) * index


def _log2(x: int) -> int:
    r = 0
    while x > 1:
        x >>= 1
        r += 1
    return r


DATAFILE_SIZE = _num_xi(GRAPH_INDEX) * NODE_SIZE  # 1283457024 bytes


def _varint_node(val: int) -> bytes:
    """Go's binary.PutVarint (zigzag) into a zero-padded NODE_SIZE buffer."""
    uval = val << 1 if val >= 0 else ~(val << 1)
    out = bytearray()
    while uval >= 0x80:
        out.append((uval & 0x7f) | 0x80)
        uval >>= 7
    out.append(uval)
    return bytes(out) + bytes(NODE_SIZE - len(out))


class _GraphBuilder:

    def __init__(self, buf, index: int, pk: bytes, progress_cb: Optional[Callable[[float], None]] = None):
        self.buf = buf
        self.index = index
        self.pk = pk
        size = _num_xi(index)
        self.total_nodes = size
        self.pow2 = 1 << (_log2(size) + 1)
        self.progress_cb = progress_cb
        self._next_progress = 0

    # nodes are stored at (node_id & ~pow2); ids start at pow2, so this is (node_id - pow2)
    def _get(self, node_id: int) -> bytes:
        off = (node_id - self.pow2) * NODE_SIZE
        return self.buf[off:off + NODE_SIZE]

    def _put(self, node_id: int, h: bytes) -> None:
        off = (node_id - self.pow2) * NODE_SIZE
        self.buf[off:off + NODE_SIZE] = h

    def _report(self, count: int) -> None:
        if count >= self._next_progress:
            self._next_progress = count + (1 << 20)
            if self.progress_cb:
                self.progress_cb((count - self.pow2) / self.total_nodes)

    def butterfly_graph(self, index: int, count: int) -> int:
        if index == 0:
            index = 1
        sha3 = hashlib.sha3_256
        pk = self.pk
        get, put = self._get, self._put
        num_level = 2 * index
        per_level = 1 << index
        begin = count - per_level  # level 0 created outside
        for level in range(1, num_level):
            shift = index - level
            if level > num_level // 2:
                shift = level - num_level // 2
            bit = 1 << shift
            row = begin + (level - 1) * per_level
            for i in range(per_level):
                prev = i + bit if (i >> shift) & 1 == 0 else i - bit
                parent0 = get(row + prev)
                parent1 = get(count - per_level)
                put(count, sha3(pk + _varint_node(count) + parent0 + parent1).digest())
                count += 1
            self._report(count)
        return count

    def build(self) -> None:
        sha3 = hashlib.sha3_256
        pk = self.pk
        get, put = self._get, self._put
        index = self.index
        count = self.pow2

        for i in range(1 << index):  # sources at this level
            put(count, sha3(pk + _varint_node(count)).digest())
            count += 1

        if index == 1:
            self.butterfly_graph(index, count)
            return

        stack = [index] * 5
        graph_stack = [4, 3, 2, 1, 0]
        while stack and graph_stack:
            index = stack.pop()
            graph = graph_stack.pop()
            pow2index = 1 << index
            pow2index_1 = 1 << (index - 1)

            if graph == 0:
                # sources to sources of first butterfly
                sources = count - pow2index
                for i in range(pow2index_1):
                    parent0 = get(sources + i)
                    parent1 = get(sources + i + pow2index_1)
                    put(count, sha3(pk + _varint_node(count) + parent0 + parent1).digest())
                    count += 1
            elif graph in (1, 2, 3):
                # 1: sinks of first butterfly to sources of first xi graph
                # 2: sinks of first xi to sources of second xi
                # 3: sinks of second xi to sources of second butterfly
                first = count
                for i in range(pow2index_1):
                    node_id = first + i
                    parent = get(first - pow2index_1 + i)
                    put(node_id, sha3(pk + _varint_node(node_id) + parent).digest())
                    count += 1
            else:
                # sinks of second butterfly to sinks, and sources to sinks directly
                sinks = count
                sources = sinks + pow2index - _num_xi(index)
                for i in range(pow2index_1):
                    node_id0 = sinks + i
                    node_id1 = sinks + i + pow2index_1
                    parent0 = get(sinks - pow2index_1 + i)
                    parent1_0 = get(sources + i)
                    parent1_1 = get(sources + i + pow2index_1)
                    put(node_id0, sha3(pk + _varint_node(node_id0) + parent0 + parent1_0).digest())
                    put(node_id1, sha3(pk + _varint_node(node_id1) + parent0 + parent1_1).digest())
                    count += 2
            self._report(count)

            if graph in (0, 3) or (graph in (1, 2) and index == 2):
                count = self.butterfly_graph(index - 1, count)
            elif graph in (1, 2):
                stack.extend([index - 1] * 5)
                graph_stack.extend([4, 3, 2, 1, 0])
        if self.progress_cb:
            self.progress_cb(1.0)


def generate_datafile(path: str, *, progress_cb: Optional[Callable[[float], None]] = None) -> None:
    """Create the Verthash datafile at `path`. Takes a few minutes.
    The file is written to a temporary name and renamed once its checksum is verified.
    """
    tmp_path = path + '.tmp'
    pk = hashlib.sha3_256(b"Verthash Proof-of-Space Datafile").digest()
    t0 = time.monotonic()
    _logger.info(f"generating verthash datafile at {path}")
    try:
        with open(tmp_path, 'w+b') as f:
            _reserve(f, DATAFILE_SIZE)
            with mmap.mmap(f.fileno(), DATAFILE_SIZE) as mm:
                _GraphBuilder(mm, GRAPH_INDEX, pk, progress_cb).build()
                mm.flush()
        _logger.info(f"verthash datafile generated in {time.monotonic() - t0:.0f} s. verifying...")
        _install_datafile(tmp_path, path)
    except BaseException:
        # don't leave 1.2 GiB behind
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _reserve(f, size: int) -> None:
    """Allocate the file's blocks before writing them through a memory map: on a full disk,
    writing a page of a sparse file kills the process with SIGBUS instead of raising."""
    if hasattr(os, 'posix_fallocate'):
        try:
            os.posix_fallocate(f.fileno(), 0, size)
            return
        except OSError as e:
            if e.errno == errno.ENOSPC:
                raise
            # the filesystem can't allocate ahead
    f.truncate(size)


def check_disk_space(path: str) -> None:
    """Raises VerthashDatafileError if there is no room to generate the datafile at path."""
    try:
        stale = os.path.getsize(path + '.tmp')  # the generator replaces it
    except OSError:
        stale = 0
    free = shutil.disk_usage(os.path.dirname(os.path.abspath(path))).free + stale
    if free < DATAFILE_SIZE:
        raise VerthashDatafileError(
            f"not enough disk space for the verthash datafile at {path}: "
            f"it needs {DATAFILE_SIZE / 2**30:.1f} GiB, {free / 2**30:.1f} GiB are free")


def _install_datafile(tmp_path: str, path: str) -> None:
    """Rename a generated datafile into place once its checksum is verified."""
    if not verify_datafile(tmp_path):
        os.unlink(tmp_path)
        raise VerthashDatafileError("generated verthash datafile has an unexpected checksum")
    os.replace(tmp_path, path)


def _generate_with_vertcoinhash(path: str, progress_cb: Callable[[float], None]) -> None:
    """vertcoinhash's port of Vertcoin Core's generator (1.1.0 and later): about 15 s on a
    desktop. It writes path + '.tmp' through a memory map and renames it to path; the GIL
    is released meanwhile, except to call progress_cb. It does not check the checksum."""
    t0 = time.monotonic()
    _logger.info(f"generating verthash datafile at {path} with vertcoinhash")
    _vertcoinhash.create_datafile(path, progress_cb=progress_cb)
    _logger.info(f"verthash datafile generated in {time.monotonic() - t0:.0f} s")


def _generate_in_child(path: str, progress) -> None:
    def on_progress(x: float):
        progress.value = x
    generate_datafile(path, progress_cb=on_progress)


class _CannotSpawn(Exception):
    pass


def _generate_in_process(path: str, progress_cb: Callable[[float], None]) -> None:
    """generate_datafile() in a child process. It is minutes of CPU-bound pure
    python, which in a thread holds the GIL and makes the GUI sluggish.
    Raises _CannotSpawn if no child process could be run here."""
    if 'ANDROID_DATA' in os.environ or not sys.executable:
        raise _CannotSpawn("no python executable to run a child process")
    ctx = multiprocessing.get_context('spawn')
    progress = ctx.Value('d', 0.0, lock=False)
    proc = ctx.Process(target=_generate_in_child, args=(path, progress), name='verthash-datafile', daemon=True)
    try:
        proc.start()
    except Exception as e:
        raise _CannotSpawn(repr(e)) from e
    while proc.is_alive():
        proc.join(0.5)
        progress_cb(progress.value)
    if proc.exitcode != 0:
        if progress.value == 0:
            # it never got going, e.g. a frozen app that cannot run the child
            raise _CannotSpawn(f"child process exited with code {proc.exitcode}")
        raise VerthashDatafileError(f"datafile generation exited with code {proc.exitcode}")


def _read_through(path: str) -> None:
    """Read the file once, into the OS page cache."""
    t0 = time.monotonic()
    try:
        with open(path, 'rb', buffering=0) as f:
            buf = bytearray(1 << 22)
            while f.readinto(buf):
                pass
    except OSError as e:
        _logger.info(f"could not read {path} through: {e!r}")
        return
    _logger.info(f"read the verthash datafile through in {time.monotonic() - t0:.1f} s")


def verify_datafile(path: str) -> bool:
    try:
        if os.path.getsize(path) != DATAFILE_SIZE:
            return False
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            while chunk := f.read(1 << 22):
                h.update(chunk)
        return h.hexdigest() == DATAFILE_SHA256
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

# vertcoinhash's test header; its verthash is e0f6c10b4a38f35a6cdcc26d32a7ed8c3bfc5d827a9bc72647afa324b70d0463
_SELFTEST_HEADER = bytes.fromhex(
    '000000203a297b4b7685170d7644b43e5a6056234cc2414edde454a87580e1967d14c107'
    '8c13ea916117b0608732f3f65c2e03b81322efc0a62bcee77d8a9371261970a58a5a715d'
    'a80e031b02560ad8')


_UNPACK_NODE = struct.Struct('<8I')


class _FileData:
    """The datafile read with a system call for each 32 bytes a hash needs, for when it
    can't be memory-mapped (e.g. no room for 1.2 GiB in a 32-bit address space)."""

    def __init__(self, f):
        self._f = f
        self._size = os.fstat(f.fileno()).st_size
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return self._size

    def unpack_at(self, offset: int):
        if hasattr(os, 'pread'):
            b = os.pread(self._f.fileno(), HASH_OUT_SIZE, offset)
        else:
            with self._lock:
                self._f.seek(offset)
                b = self._f.read(HASH_OUT_SIZE)
        return _UNPACK_NODE.unpack(b)


def verthash_pow(header: bytes, data) -> bytes:
    """Verthash of an 80-byte block header. `data` is the datafile (bytes, mmap or _FileData)."""
    assert len(header) == HEADER_SIZE, len(header)
    p1 = list(struct.unpack('<8I', hashlib.sha3_256(header).digest()))

    rest = header[1:]
    b0 = header[0]
    p0 = b''.join(hashlib.sha3_512(bytes(((b0 + i + 1) & 0xff,)) + rest).digest() for i in range(N_ITER))
    words = struct.unpack(f'<{N_SUBSET // 4}I', p0)
    seek_indexes = []
    for _ in range(N_ROT):
        seek_indexes.extend(words)
        words = [((w << 1) | (w >> 31)) & _M32 for w in words]

    mdiv = ((len(data) - HASH_OUT_SIZE) // BYTE_ALIGNMENT) + 1
    read_at = data.unpack_at if isinstance(data, _FileData) else functools.partial(_UNPACK_NODE.unpack_from, data)
    acc = _FNV_OFFSET
    a0, a1, a2, a3, a4, a5, a6, a7 = p1
    P, M = _FNV_PRIME, _M32
    for seek in seek_indexes:
        offset = ((((seek ^ acc) * P) & M) % mdiv) * BYTE_ALIGNMENT
        v0, v1, v2, v3, v4, v5, v6, v7 = read_at(offset)
        a0 = ((a0 ^ v0) * P) & M; acc = ((acc ^ v0) * P) & M
        a1 = ((a1 ^ v1) * P) & M; acc = ((acc ^ v1) * P) & M
        a2 = ((a2 ^ v2) * P) & M; acc = ((acc ^ v2) * P) & M
        a3 = ((a3 ^ v3) * P) & M; acc = ((acc ^ v3) * P) & M
        a4 = ((a4 ^ v4) * P) & M; acc = ((acc ^ v4) * P) & M
        a5 = ((a5 ^ v5) * P) & M; acc = ((acc ^ v5) * P) & M
        a6 = ((a6 ^ v6) * P) & M; acc = ((acc ^ v6) * P) & M
        a7 = ((a7 ^ v7) * P) & M; acc = ((acc ^ v7) * P) & M
    return struct.pack('<8I', a0, a1, a2, a3, a4, a5, a6, a7)


# ---------------------------------------------------------------------------
# Datafile management
# ---------------------------------------------------------------------------

def _vertcoin_core_dirs() -> Sequence[str]:
    home = os.environ.get('HOME') or os.path.expanduser('~')
    dirs = []
    if os.name == 'posix':
        dirs += [os.path.join(home, '.vertcoin'), os.path.join(home, '.vertcoin-ocm')]
        dirs += [os.path.join(home, 'Library', 'Application Support', 'Vertcoin')]
    for env in ('APPDATA', 'LOCALAPPDATA'):
        if env in os.environ:
            dirs += [os.path.join(os.environ[env], 'Vertcoin'), os.path.join(os.environ[env], 'Vertcoin-OCM')]
    return dirs


class VerthashDatafile:
    """Locates (or creates) the verthash datafile and memory-maps it."""

    def __init__(self):
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._data = None  # type: Optional[mmap.mmap]
        self._c_hash = None  # type: Optional[Callable[[bytes, mmap.mmap], bytes]]
        self._file = None
        self.path = None  # type: Optional[str]
        self.error = None  # type: Optional[str]
        self.progress = None  # type: Optional[float]  # set while generating
        self._thread = None  # type: Optional[threading.Thread]

    def is_ready(self) -> bool:
        return self._ready.is_set()

    def wait(self, timeout: Optional[float] = None) -> bool:
        return self._ready.wait(timeout)

    def candidate_paths(self, config: 'SimpleConfig') -> Sequence[str]:
        paths = []
        if config.VERTHASH_DATAFILE_PATH:
            paths.append(config.VERTHASH_DATAFILE_PATH)
        paths.append(self.default_path(config))
        paths += [os.path.join(d, DATAFILE_NAME) for d in _vertcoin_core_dirs()]
        return paths

    @staticmethod
    def default_path(config: 'SimpleConfig') -> str:
        return os.path.join(config.electrum_path_root(), DATAFILE_NAME)

    @staticmethod
    def _stamp(path: str) -> Optional[str]:
        """size+mtime of a datafile, or None if it is missing or has the wrong size"""
        try:
            st = os.stat(path)
        except OSError:
            return None
        if st.st_size != DATAFILE_SIZE:
            return None
        return f"{os.path.abspath(path)}|{st.st_size}|{int(st.st_mtime)}"

    def _is_known_good(self, config: 'SimpleConfig', path: str) -> bool:
        """Avoid re-hashing 1.2 GiB on every start: remember size+mtime of a verified file."""
        stamp = self._stamp(path)
        if stamp is None:
            return False
        if config.VERTHASH_DATAFILE_VERIFIED == stamp:
            return True
        _logger.info(f"verifying verthash datafile {path}")
        if not verify_datafile(path):
            _logger.warning(f"bad verthash datafile: {path}")
            return False
        config.VERTHASH_DATAFILE_VERIFIED = stamp
        return True

    def _load(self, path: str) -> None:
        f = open(path, 'rb')
        try:
            self._data = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        except (OSError, ValueError, OverflowError) as e:
            _logger.warning(f"could not map the verthash datafile, reading it from disk for every hash: {e!r}")
            self._data = _FileData(f)
        else:
            if hasattr(mmap, 'MADV_RANDOM'):  # not on Windows
                # Each hash reads 32 bytes at 4096 random offsets. Without this, every page fault
                # also reads in the pages around it, which evicts the pages hashes need when the
                # file doesn't fit in RAM.
                self._data.madvise(mmap.MADV_RANDOM)
                # But then, when it does fit, faults read it in only a page at a time: read it
                # once, sequentially, as Vertcoin Core's startup check does. Hashing 2000 headers
                # with the file not yet cached takes 2.6 s like this, instead of 60 s.
                threading.Thread(target=_read_through, args=(path,), name='verthash-read', daemon=True).start()
        self._file = f
        self.path = path
        self.progress = None
        self._c_hash = self._find_c_implementation()
        self._ready.set()
        _logger.info(f"using verthash datafile {path}")
        self._notify()

    def _notify(self) -> None:
        """Tell GUIs that progress, readiness or error changed."""
        from . import util
        try:
            util.trigger_callback('verthash_progress', self.progress)
        except Exception:  # no running event loop, e.g. in tests
            pass

    def prepare(self, config: 'SimpleConfig', *, create: bool = True) -> None:
        """Blocking. Find a valid datafile, or generate one in the Electrum-VTC data dir."""
        with self._lock:
            try:
                self._prepare(config, create=create)
            except Exception as e:
                # e.g. the datafile can't be opened: say so, instead of leaving GUIs waiting for it
                self.error = repr(e)
                self.progress = None
                _logger.exception("failed to load verthash datafile")
                self._notify()

    def _prepare(self, config: 'SimpleConfig', *, create: bool) -> None:
        if self.is_ready():
            return
        self.error = None
        for path in self.candidate_paths(config):
            if self._is_known_good(config, path):
                self._load(path)
                return
        if not create:
            self.error = "verthash datafile not found"
            return
        path = config.VERTHASH_DATAFILE_PATH or self.default_path(config)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        def on_progress(x: float):
            self.progress = x
            self._notify()
        on_progress(0.0)
        # the python generators check the checksum before renaming the file into place
        verified = True
        try:
            check_disk_space(path)
            if _vertcoinhash is not None and hasattr(_vertcoinhash, 'create_datafile'):
                _generate_with_vertcoinhash(path, on_progress)
                verified = False
            else:
                try:
                    _generate_in_process(path, on_progress)
                except _CannotSpawn as e:
                    _logger.info(f"generating the verthash datafile in this process: {e}")
                    generate_datafile(path, progress_cb=on_progress)
        except Exception as e:
            self.error = repr(e)
            self.progress = None
            _logger.exception("failed to generate verthash datafile")
            self._notify()
            return
        config.VERTHASH_DATAFILE_VERIFIED = self._stamp(path) if verified else None
        if self._is_known_good(config, path):
            self._load(path)
        else:
            self.error = "generated verthash datafile failed verification"
            self.progress = None
            self._notify()

    def prepare_in_background(self, config: 'SimpleConfig') -> None:
        if self.is_ready() or (self._thread and self._thread.is_alive()):
            return
        self.error = None
        self._thread = threading.Thread(target=self.prepare, args=(config,), name='verthash-datafile', daemon=True)
        self._thread.start()

    def _find_c_implementation(self):
        """vertcoinhash's verthash.getPoWHash, if it is installed, takes the mmap
        (1.1.0 and later) and gives the same hash as verthash_pow; else None."""
        if _vertcoinhash is None:
            return None
        try:
            agrees = (_vertcoinhash.getPoWHash(_SELFTEST_HEADER, self._data)
                      == verthash_pow(_SELFTEST_HEADER, self._data))
        except Exception as e:
            _logger.info(f"not using vertcoinhash's verthash: {e!r}")
            return None
        if not agrees:
            _logger.warning("not using vertcoinhash's verthash: it disagrees with verthash_pow")
            return None
        _logger.info("using vertcoinhash's C verthash")
        return _vertcoinhash.getPoWHash

    def hash(self, header: bytes) -> bytes:
        if not self.is_ready():
            raise VerthashDatafileError("verthash datafile not loaded")
        if self._c_hash is not None:
            return self._c_hash(header, self._data)
        return verthash_pow(header, self._data)


datafile = VerthashDatafile()
