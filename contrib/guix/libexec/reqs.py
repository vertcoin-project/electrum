#!/usr/bin/env python3
"""Print the requirement blocks (name==version plus their --hash lines) of a
hash-pinned requirements file, keeping only --only NAMES or dropping --exclude NAMES.

    reqs.py FILE [--only a,b] [--exclude c,d]
"""
import re
import sys


def canonical(name: str) -> str:
    return re.sub(r'[-_.]+', '-', name).lower()


def blocks(path):
    block = []
    for line in open(path, encoding='utf-8'):
        if line.startswith('#') or not line.strip():
            continue
        if not line[0].isspace() and block:
            yield block
            block = []
        block.append(line.rstrip('\n'))
    if block:
        yield block


def main():
    path = sys.argv[1]
    only = exclude = None
    args = sys.argv[2:]
    while args:
        opt, val = args[0], args[1]
        names = {canonical(n) for n in val.split(',') if n}
        if opt == '--only':
            only = names
        elif opt == '--exclude':
            exclude = names
        else:
            raise SystemExit(f'unknown option {opt}')
        args = args[2:]
    seen = set()
    for block in blocks(path):
        name = canonical(re.split(r'[=<>!~;\s\[]', block[0], maxsplit=1)[0])
        if only is not None and name not in only:
            continue
        if exclude is not None and name in exclude:
            continue
        seen.add(name)
        print('\n'.join(block))
    if only is not None and only - seen:
        raise SystemExit(f'not in {path}: {sorted(only - seen)}')


if __name__ == '__main__':
    main()
