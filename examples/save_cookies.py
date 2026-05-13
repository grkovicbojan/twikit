"""Bootstrap a `cookies.json` for twikit from values copied out of a browser.

Cloudflare currently blocks twikit's password login flow from most IPs
(especially datacenter/proxy IPs) by fingerprinting the TLS handshake.
The reliable workaround is to log in once in a real browser, then reuse
the resulting session cookies.

Usage
-----
1. Log in to https://x.com in a normal browser.
2. Open DevTools -> Application / Storage -> Cookies -> https://x.com
3. Copy at least the `auth_token` and `ct0` values (everything else is
   optional but improves stealth).
4. Run:

       python examples/save_cookies.py auth_token=<value> ct0=<value>

   Optional extras: guest_id, att, kdt, twid, personalization_id, lang.

   You can also pass `-o some_path.json` to choose the output file
   (default: cookies.json in the current directory).

After this, run `examples/example.py` and it will log in by loading the
cookies file instead of going through onboarding/task.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys


KNOWN_COOKIES = (
    'auth_token',
    'ct0',
    'guest_id',
    'twid',
    'att',
    'kdt',
    'personalization_id',
    'lang',
    'des_opt_in',
    'guest_id_ads',
    'guest_id_marketing',
)

REQUIRED = ('auth_token', 'ct0')


def _parse_kv(items: list[str]) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for raw in items:
        if '=' not in raw:
            raise SystemExit(
                f"[save_cookies] '{raw}' is not in name=value form."
            )
        name, value = raw.split('=', 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if not name:
            raise SystemExit(f"[save_cookies] empty cookie name in '{raw}'")
        if not value:
            raise SystemExit(f"[save_cookies] empty value for cookie '{name}'")
        cookies[name] = value
    return cookies


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description='Build a twikit cookies.json from name=value pairs.'
    )
    parser.add_argument(
        'pairs',
        nargs='*',
        help='Cookie pairs in name=value form (e.g. auth_token=abc ct0=def).',
    )
    parser.add_argument(
        '-o', '--output',
        default='cookies.json',
        help='Path to write (default: cookies.json).',
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Overwrite the output file if it already exists.',
    )
    args = parser.parse_args(argv)

    if not args.pairs:
        parser.print_help(sys.stderr)
        return 2

    cookies = _parse_kv(args.pairs)

    missing = [name for name in REQUIRED if name not in cookies]
    if missing:
        print(
            f"[save_cookies] missing required cookie(s): {', '.join(missing)}.\n"
            f"[save_cookies] At minimum you must provide auth_token and ct0.",
            file=sys.stderr,
        )
        return 1

    unknown = [name for name in cookies if name not in KNOWN_COOKIES]
    if unknown:
        print(
            f"[save_cookies] note: writing non-standard cookie(s) "
            f"{', '.join(unknown)} (twikit will still accept them).",
            file=sys.stderr,
        )

    if os.path.exists(args.output) and not args.force:
        print(
            f"[save_cookies] refusing to overwrite '{args.output}' "
            f"without --force.",
            file=sys.stderr,
        )
        return 1

    with open(args.output, 'w', encoding='utf-8') as fp:
        json.dump(cookies, fp, indent=2, sort_keys=True)

    print(f"[save_cookies] wrote {len(cookies)} cookie(s) to '{args.output}'.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
