#!/usr/bin/env python3
#
# Regenerate electrum_vtc/chains/<net>/checkpoints.json from a synced vertcoind.
#
# Each entry is [hash of the last block of a 2016-block chunk, target of that block].
# Below the last checkpoint Electrum-VTC only checks that headers link up to the
# checkpointed hashes; above it, every header's KGW difficulty and Verthash PoW are verified.
#
# usage: make_checkpoints.py --rpcurl http://user:pass@127.0.0.1:5888/ [--confirmations 2016] [--out FILE]

import argparse
import base64
import json
import urllib.parse
import urllib.request

CHUNK_SIZE = 2016


def bits_to_target(bits: int) -> int:
    size = bits >> 24
    word = bits & 0x007fffff
    if size <= 3:
        return word >> (8 * (3 - size))
    return word << (8 * (size - 3))


class RPC:
    def __init__(self, url: str):
        u = urllib.parse.urlparse(url)
        self.url = urllib.parse.urlunparse((u.scheme, f"{u.hostname}:{u.port}", u.path or '/', '', '', ''))
        self.auth = base64.b64encode(f"{urllib.parse.unquote(u.username or '')}:{urllib.parse.unquote(u.password or '')}".encode()).decode()

    def batch(self, calls):
        body = json.dumps([{'jsonrpc': '1.0', 'id': i, 'method': m, 'params': p}
                           for i, (m, p) in enumerate(calls)]).encode()
        req = urllib.request.Request(self.url, data=body, headers={
            'Authorization': 'Basic ' + self.auth, 'Content-Type': 'application/json'})
        res = sorted(json.loads(urllib.request.urlopen(req, timeout=600).read()), key=lambda r: r['id'])
        for r in res:
            if r.get('error'):
                raise Exception(r['error'])
        return [r['result'] for r in res]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rpcurl', default='http://127.0.0.1:5888/')
    parser.add_argument('--confirmations', type=int, default=CHUNK_SIZE,
                        help='only checkpoint chunks with at least this many blocks on top')
    parser.add_argument('--out', default='checkpoints.json')
    args = parser.parse_args()

    rpc = RPC(args.rpcurl)
    tip = rpc.batch([('getblockcount', [])])[0]
    num_chunks = (tip - args.confirmations + 1) // CHUNK_SIZE
    heights = [(i + 1) * CHUNK_SIZE - 1 for i in range(num_chunks)]
    checkpoints = []
    for i in range(0, len(heights), 1000):
        hashes = rpc.batch([('getblockhash', [h]) for h in heights[i:i + 1000]])
        headers = rpc.batch([('getblockheader', [bh, True]) for bh in hashes])
        for bh, hdr in zip(hashes, headers):
            checkpoints.append([bh, bits_to_target(int(hdr['bits'], 16))])
    with open(args.out, 'w') as f:
        json.dump(checkpoints, f, indent=4)
        f.write('\n')
    print(f"wrote {len(checkpoints)} checkpoints (max checkpoint height {len(checkpoints) * CHUNK_SIZE - 1}, tip {tip})")


if __name__ == '__main__':
    main()
