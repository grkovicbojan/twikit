"""Bootstrap a `cookies.json` for twikit from a browser cookie export.

Cloudflare currently fingerprints httpx's TLS handshake and blocks
twikit's password login on /1.1/onboarding/task.json. The reliable
workaround is to log in once in a real browser, then reuse the
resulting session cookies.

Supported input formats
-----------------------
1. Cookie-Editor / EditThisCookie JSON export (a JSON *array* of
   objects with at least ``name`` and ``value`` fields). This is what
   you get from the popular browser extensions.
2. A JSON *object* already in twikit's ``{"name": "value"}`` shape
   (useful if you exported with another tool or hand-edited).
3. Pairs on the command line, e.g.
   ``auth_token=abc ct0=def`` (kept for convenience).

Usage examples
--------------
    # Paste the Cookie-Editor export into a file then convert it:
    python examples/save_cookies.py -i x-cookies.json -o cookies.json

    # Or pipe it straight in from stdin:
    cat x-cookies.json | python examples/save_cookies.py -o cookies.json

    # Or hand-pick the two required cookies:
    python examples/save_cookies.py auth_token=<value> ct0=<value>

After this, run ``examples/example.py`` and it will skip login and
just load the cookies file.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any


REQUIRED = ('auth_token', 'ct0')

KEEP_COOKIES = {
    'auth_token',
    'ct0',
    'guest_id',
    'twid',
    'att',
    'kdt',
    'personalization_id',
    'guest_id_ads',
    'guest_id_marketing',
    'lang',
    'des_opt_in',
    'auth_multi',
    'd_prefs',
}

DROP_COOKIES = {
    '__cf_bm',
    'gt',
    'night_mode',
    'dnt',
    '__gads',
    '__gpi',
    '__eoi',
    '_ga',
    '_gid',
    '_gat',
    'mbox',
}


def _from_browser_array(data: list[Any]) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for entry in data:
        if not isinstance(entry, dict):
            continue
        name = entry.get('name')
        value = entry.get('value')
        if not isinstance(name, str) or not isinstance(value, str):
            continue
        # Cookie-Editor exports include cookies for every domain in the
        # current tab. Restrict to twitter/x domains so we don't send
        # third-party tracking cookies to x.com.
        domain = (entry.get('domain') or '').lstrip('.').lower()
        if domain and domain not in {'x.com', 'twitter.com'}:
            continue
        cookies[name] = value
    return cookies


def _parse_kv_pairs(items: list[str]) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for raw in items:
        if '=' not in raw:
            raise SystemExit(
                f"[save_cookies] '{raw}' is not in name=value form."
            )
        name, value = raw.split('=', 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if not name or not value:
            raise SystemExit(
                f"[save_cookies] empty name or value in '{raw}'"
            )
        cookies[name] = value
    return cookies


def _load_from_text(text: str) -> dict[str, str]:
    text = text.strip()
    if not text:
        raise SystemExit('[save_cookies] input is empty.')
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"[save_cookies] could not parse input as JSON: {exc}"
        )
    if isinstance(data, list):
        return _from_browser_array(data)
    if isinstance(data, dict):
        return {
            str(k): str(v)
            for k, v in data.items()
            if isinstance(v, (str, int))
        }
    raise SystemExit(
        '[save_cookies] JSON must be either an array of cookie objects '
        '(Cookie-Editor export) or an object of name->value.'
    )


def _filter(cookies: dict[str, str], keep_all: bool) -> dict[str, str]:
    if keep_all:
        return {n: v for n, v in cookies.items() if n not in DROP_COOKIES}
    filtered = {n: v for n, v in cookies.items() if n in KEEP_COOKIES}
    for name in REQUIRED:
        if name in cookies:
            filtered[name] = cookies[name]
    return filtered


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description='Build a twikit cookies.json from a browser export.',
    )
    parser.add_argument(
        'pairs',
        nargs='*',
        help='Optional name=value pairs (e.g. auth_token=abc ct0=def).',
    )
    parser.add_argument(
        '-i', '--input',
        help='Path to a JSON file (browser export or {name:value} object). '
             'Use "-" to read from stdin.',
    )
    parser.add_argument(
        '-o', '--output',
        default='cookies.json',
        help='Output path (default: cookies.json).',
    )
    parser.add_argument(
        '--keep-all',
        action='store_true',
        help='Keep every cookie except the known-junk ones '
             '(ads, __cf_bm, etc.). Default keeps only the auth-related ones.',
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Overwrite the output file if it already exists.',
    )
    args = parser.parse_args(argv)

    cookies: dict[str, str] = {}

    if args.input == '-' or (args.input is None and not args.pairs and not sys.stdin.isatty()):
        cookies.update(_load_from_text(sys.stdin.read()))
    elif args.input:
        if not os.path.exists(args.input):
            print(f"[save_cookies] file not found: {args.input}", file=sys.stderr)
            return 1
        with open(args.input, 'r', encoding='utf-8') as fp:
            cookies.update(_load_from_text(fp.read()))

    if args.pairs:
        cookies.update(_parse_kv_pairs(args.pairs))

    if not cookies:
        parser.print_help(sys.stderr)
        return 2

    cookies = _filter(cookies, keep_all=args.keep_all)

    missing = [name for name in REQUIRED if name not in cookies]
    if missing:
        print(
            f"[save_cookies] missing required cookie(s): {', '.join(missing)}.\n"
            f"[save_cookies] At minimum twikit needs auth_token and ct0.",
            file=sys.stderr,
        )
        return 1

    if os.path.exists(args.output) and not args.force:
        print(
            f"[save_cookies] refusing to overwrite '{args.output}' "
            f"without --force.",
            file=sys.stderr,
        )
        return 1

    with open(args.output, 'w', encoding='utf-8') as fp:
        json.dump(cookies, fp, indent=2, sort_keys=True)

    kept = ', '.join(sorted(cookies))
    print(
        f"[save_cookies] wrote {len(cookies)} cookie(s) to '{args.output}': "
        f"{kept}"
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
