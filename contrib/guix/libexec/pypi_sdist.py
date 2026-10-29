#!/usr/bin/env python3
"""Download the source distribution of every requirement in a hash-pinned
requirements file from PyPI, keeping only files whose sha256 is one of the
pinned hashes. Unlike `pip download`, this runs no code from the packages.

    pypi_sdist.py REQFILE DEST
"""
import hashlib
import json
import os
import re
import sys
import urllib.request


def requirements(path):
    name = version = None
    hashes = set()
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        m = re.match(r'^([A-Za-z0-9_.-]+)==([^\s\\;]+)', line)
        if m:
            if name:
                yield name, version, hashes
            name, version, hashes = m.group(1), m.group(2), set()
        hashes.update(re.findall(r'--hash=sha256:([0-9a-f]{64})', line))
    if name:
        yield name, version, hashes


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    reqfile, dest = sys.argv[1:]
    os.makedirs(dest, exist_ok=True)
    for name, version, hashes in requirements(reqfile):
        with urllib.request.urlopen(f'https://pypi.org/pypi/{name}/{version}/json', timeout=120) as r:
            files = json.load(r)['urls']
        sdists = [f for f in files if f['packagetype'] == 'sdist' and f['digests']['sha256'] in hashes]
        if not sdists:
            sys.exit(f'no sdist of {name}=={version} matches the pinned hashes')
        f = sdists[0]
        path = os.path.join(dest, f['filename'])
        if os.path.exists(path) and sha256(path) == f['digests']['sha256']:
            continue
        print(f"downloading {f['filename']}", flush=True)
        with urllib.request.urlopen(f['url'], timeout=300) as r, open(path + '.part', 'wb') as out:
            while chunk := r.read(1 << 20):
                out.write(chunk)
        if sha256(path + '.part') not in hashes:
            os.unlink(path + '.part')
            sys.exit(f"sha256 mismatch for {f['filename']}")
        os.replace(path + '.part', path)


if __name__ == '__main__':
    main()
