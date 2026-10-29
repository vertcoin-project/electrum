import errno
import mmap
import os
import random
import shutil
import tempfile
from collections import namedtuple
from unittest import mock

from electrum_vtc import verthash

from . import ElectrumTestCase


class TestVerthash(ElectrumTestCase):
    """Without the 1.2 GiB datafile: a small file of random bytes stands in for it."""

    def setUp(self):
        super().setUp()
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, verthash.DATAFILE_NAME)
        with open(self.path, 'wb') as f:
            f.write(random.Random(1).randbytes(1 << 20))

    def tearDown(self):
        shutil.rmtree(self.dir)
        super().tearDown()

    def test_file_data_hashes_like_a_mapping(self):
        header = bytes(range(80))
        with open(self.path, 'rb') as f:
            data = f.read()
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                self.assertEqual(verthash.verthash_pow(header, data), verthash.verthash_pow(header, mm))
            self.assertEqual(verthash.verthash_pow(header, data),
                             verthash.verthash_pow(header, verthash._FileData(f)))

    def test_load_reads_the_file_when_it_cannot_be_mapped(self):
        df = verthash.VerthashDatafile()
        with mock.patch.object(verthash.mmap, 'mmap', side_effect=OSError(errno.ENOMEM, 'Cannot allocate memory')):
            df._load(self.path)
        self.assertTrue(df.is_ready())
        self.assertIsInstance(df._data, verthash._FileData)
        with open(self.path, 'rb') as f:
            self.assertEqual(df.hash(bytes(80)), verthash.verthash_pow(bytes(80), f.read()))

    def test_prepare_reports_a_datafile_it_cannot_load(self):
        df = verthash.VerthashDatafile()
        missing = os.path.join(self.dir, 'missing.dat')
        with mock.patch.object(df, 'candidate_paths', return_value=[missing]), \
                mock.patch.object(df, '_is_known_good', return_value=True):
            df.prepare(config=None)
        self.assertFalse(df.is_ready())
        self.assertIn('FileNotFoundError', df.error)

    def test_check_disk_space(self):
        usage = namedtuple('usage', 'total used free')
        with mock.patch.object(verthash.shutil, 'disk_usage', return_value=usage(0, 0, verthash.DATAFILE_SIZE - 1)):
            with self.assertRaises(verthash.VerthashDatafileError):
                verthash.check_disk_space(self.path)
            # a leftover verthash.dat.tmp is replaced, so its space counts as free
            with open(self.path + '.tmp', 'wb') as f:
                f.write(b'x')
            verthash.check_disk_space(self.path)

    def test_generate_removes_the_temporary_file_when_it_fails(self):
        with mock.patch.object(verthash, 'DATAFILE_SIZE', 4096), \
                mock.patch.object(verthash._GraphBuilder, 'build', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                verthash.generate_datafile(self.path)
        self.assertFalse(os.path.exists(self.path + '.tmp'))
