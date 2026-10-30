import socket
import tempfile
from unittest import mock

from aiohttp import web

from electrum_vtc import util
from electrum_vtc.simple_config import SimpleConfig

from . import ElectrumTestCase


class TestBlockExplorerFallback(ElectrumTestCase):
    """cryptoID.info falls back to the Blockbook explorers in sync, then to BitInfoCharts.com.
    A local web server stands in for cryptoID.info (/cid/) and vtcblocks.com (/bb/)."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = SimpleConfig({'electrum_path': tempfile.mkdtemp()})
        self.cid_status = 200
        self.bb_status = 200
        self.bb_in_sync = True
        async def cryptoid(request):
            return web.Response(status=self.cid_status)

        async def blockbook_api(request):
            return web.json_response({'blockbook': {'coin': 'Vertcoin', 'inSync': self.bb_in_sync}},
                                     status=self.bb_status)
        app = web.Application()
        app.router.add_route('HEAD', '/cid/{tail:.*}', cryptoid)
        app.router.add_route('GET', '/bb/api/', blockbook_api)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, '127.0.0.1', 0)
        await site.start()
        self.base = f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}'

    async def asyncTearDown(self):
        await self.runner.cleanup()
        await super().asyncTearDown()

    def explorers(self, cryptoid=None, blockbook=None):
        explorers = dict(util.mainnet_block_explorers)
        for name, url in (('cryptoID.info', cryptoid or f'{self.base}/cid/'),
                          ('vtcblocks.com', blockbook or f'{self.base}/bb/')):
            explorers[name] = (url, explorers[name][1])
        return mock.patch.dict(util.mainnet_block_explorers, explorers)

    def closed_port_url(self):
        with socket.socket() as s:  # a port nothing listens on
            s.bind(('127.0.0.1', 0))
            return f'http://127.0.0.1:{s.getsockname()[1]}/'

    async def fallback(self, kind='tx', item='ab'):
        return await util.block_explorer_URL_or_fallback(self.config, kind, item, timeout=2)

    async def test_default_is_cryptoid(self):
        self.assertEqual('cryptoID.info', util.block_explorer(self.config))

    async def test_cryptoid_answering(self):
        with self.explorers():
            self.assertEqual(f'{self.base}/cid/tx.dws?ab', await self.fallback())

    async def test_cryptoid_down_blockbook_in_sync(self):
        with self.explorers(cryptoid=self.closed_port_url()):
            self.assertEqual(f'{self.base}/bb/address/Vabc', await self.fallback('addr', 'Vabc'))

    async def test_cryptoid_error_blockbook_out_of_sync(self):
        self.cid_status = 503
        self.bb_in_sync = False
        with self.explorers():
            self.assertEqual('https://bitinfocharts.com/vertcoin/tx/ab', await self.fallback())

    async def test_cryptoid_error_blockbook_error(self):
        self.cid_status = 502
        self.bb_status = 500
        with self.explorers():
            self.assertEqual('https://bitinfocharts.com/vertcoin/tx/ab', await self.fallback())

    async def test_both_down(self):
        with self.explorers(cryptoid=self.closed_port_url(), blockbook=self.closed_port_url()):
            self.assertEqual('https://bitinfocharts.com/vertcoin/address/Vabc', await self.fallback('addr', 'Vabc'))

    async def test_other_explorer_is_not_checked(self):
        self.config.BLOCK_EXPLORER = 'vtcblocks.com'
        with mock.patch.object(util, 'make_aiohttp_session', side_effect=AssertionError):
            self.assertEqual('https://vtcblocks.com/tx/ab', await self.fallback())
