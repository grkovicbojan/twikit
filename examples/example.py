import asyncio
import json
import os
import sys

# MONKEY PATCH: Remove this block when twikit is updated to fix ON_DEMAND_FILE_REGEX
import re
_tx_mod = __import__('twikit.x_client_transaction.transaction', fromlist=['ClientTransaction'])
_tx_mod.ON_DEMAND_FILE_REGEX = re.compile(
    r""",(\d+):["']ondemand\.s["']""", flags=(re.VERBOSE | re.MULTILINE))
_tx_mod.ON_DEMAND_HASH_PATTERN = r',{}:"([0-9a-f]+)"'

async def _patched_get_indices(self, home_page_response, session, headers):
    key_byte_indices = []
    response = self.validate_response(home_page_response) or self.home_page_response
    on_demand_file_index = _tx_mod.ON_DEMAND_FILE_REGEX.search(str(response)).group(1)
    regex = re.compile(_tx_mod.ON_DEMAND_HASH_PATTERN.format(on_demand_file_index))
    filename = regex.search(str(response)).group(1)
    on_demand_file_url = f"https://abs.twimg.com/responsive-web/client-web/ondemand.s.{filename}a.js"
    on_demand_file_response = await session.request(method="GET", url=on_demand_file_url, headers=headers)
    key_byte_indices_match = _tx_mod.INDICES_REGEX.finditer(str(on_demand_file_response.text))
    for item in key_byte_indices_match:
        key_byte_indices.append(item.group(2))
    if not key_byte_indices:
        raise Exception("Couldn't get KEY_BYTE indices")
    key_byte_indices = list(map(int, key_byte_indices))
    return key_byte_indices[0], key_byte_indices[1:]

_tx_mod.ClientTransaction.get_indices = _patched_get_indices
# END MONKEY PATCH

from twikit import Client
from twikit.client import client as _client_mod
from twikit.gql_refresh import refresh_query_ids


# DIAGNOSTIC: print the URL + response details on any HTTP error so a future
# rotation or shadow-block shows up as one obvious line of output instead of
# an empty "404".
_orig_request = _client_mod.Client.request

async def _logging_request(self, method, url, *args, **kwargs):
    try:
        return await _orig_request(self, method, url, *args, **kwargs)
    except Exception as exc:
        headers = getattr(exc, 'headers', None)
        cf_ray = headers.get('cf-ray') if headers else None
        server = headers.get('server') if headers else None
        print(
            f"[debug] {method} {url[:200]} -> {type(exc).__name__}\n"
            f"[debug]   server: {server}    cf-ray: {cf_ray}",
            file=sys.stderr,
        )
        raise

_client_mod.Client.request = _logging_request
# END DIAGNOSTIC

###########################################

# Cloudflare currently fingerprints httpx's TLS on /1.1/onboarding/task.json
# and blocks password login from most IPs (especially datacenter proxies).
# Workflow:
#   1. Log in to https://x.com in a real browser.
#   2. Use the "Cookie-Editor" (or EditThisCookie) extension.
#      Click "Export" -> "Export as JSON" and save the result as cookies.json
#      in this folder. The file is the standard extension export, i.e. a JSON
#      array of objects with `name`, `value`, `domain`, ... fields.
#   3. Run this script.
COOKIES_FILE = os.environ.get('TWIKIT_COOKIES', 'cookies.json')

# Cookies in the Cookie-Editor export that twikit doesn't need (or that go
# stale fast and would only make requests look weirder).
#
# NOTE: ``__cf_bm`` is *kept* deliberately. It's Cloudflare's bot-management
# token, minted for your browser when it solved a CF challenge. Forwarding
# it from the same session makes CF treat our requests as part of that
# already-trusted session. It expires after ~30 minutes, so when CF starts
# returning 403 again, re-export cookies from the browser.
_DROP_COOKIES = {
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


def _read_cookies(path: str) -> dict[str, str]:
    """Parse cookies.json from either the Cookie-Editor JSON array or
    twikit's own ``{"name": "value"}`` shape."""
    with open(path, 'r', encoding='utf-8') as fp:
        data = json.load(fp)

    if isinstance(data, dict):
        return {str(k): str(v) for k, v in data.items()}

    if not isinstance(data, list):
        raise ValueError(
            f"{path!r} is neither a JSON array (extension export) nor an "
            f"object (twikit format)."
        )

    cookies: dict[str, str] = {}
    for entry in data:
        if not isinstance(entry, dict):
            continue
        name = entry.get('name')
        value = entry.get('value')
        if not isinstance(name, str) or not isinstance(value, str):
            continue
        # Cookie-Editor grabs every cookie on the current tab, including
        # third-party ad cookies on unrelated domains. Only keep x.com /
        # twitter.com cookies.
        domain = (entry.get('domain') or '').lstrip('.').lower()
        if domain and domain not in {'x.com', 'twitter.com'}:
            continue
        if name in _DROP_COOKIES:
            continue
        cookies[name] = value
    return cookies


_PROXY = 'socks5://14ab94d7187c2:076d4ae3fa@206.53.57.231:12324'

# Replace httpx with a curl_cffi-backed shim that replays Safari's exact
# TLS ClientHello. Cloudflare's bot rule on /i/api/graphql/* fingerprints
# the TLS handshake (JA3/JA4); httpx's OpenSSL-based hello doesn't match
# any browser, which is why we kept hitting 403 even with cookies, headers,
# and HTTP/2 all correct. curl_cffi runs over libcurl-impersonate.
#   pip install curl_cffi
from twikit._cffi_http import CffiAsyncClient

client = Client('en-US')
client.http = CffiAsyncClient(proxy=_PROXY, impersonate='safari17_0')


async def main():
    if not os.path.exists(COOKIES_FILE):
        print(
            f"[example] No cookies file at '{COOKIES_FILE}'.\n"
            f"[example] Cloudflare blocks password login from this IP, so "
            f"seed the session from a real browser first:\n"
            f"  1. Log in to https://x.com in your browser.\n"
            f"  2. Open the 'Cookie-Editor' extension and click "
            f"'Export' -> 'Export as JSON'.\n"
            f"  3. Save the JSON to '{COOKIES_FILE}' (in this directory).\n"
            f"  4. Re-run this example.\n",
            file=sys.stderr,
        )
        sys.exit(1)

    cookies = _read_cookies(COOKIES_FILE)

    missing = [name for name in ('auth_token', 'ct0') if name not in cookies]
    if missing:
        print(
            f"[example] '{COOKIES_FILE}' is missing required cookie(s): "
            f"{', '.join(missing)}.\n"
            f"[example] Make sure you exported the cookies *while logged in* "
            f"to https://x.com.",
            file=sys.stderr,
        )
        sys.exit(1)

    # We skip twikit's normal login() entirely because the cookie file format
    # is the Cookie-Editor array, not twikit's flat dict. set_cookies()
    # accepts the dict we just built.
    client.set_cookies(cookies, clear_cookies=True)
    print(f"[example] loaded {len(cookies)} cookie(s) from '{COOKIES_FILE}'.")

    # Pull live GraphQL query IDs from x.com's JS bundle and patch
    # twikit.client.gql.Endpoint. Cached on disk so subsequent runs are free
    # until x.com ships a new bundle.
    patched = await refresh_query_ids(client.http)
    print(f"[example] refreshed {patched} GraphQL endpoint(s) "
          f"against live x.com bundle.")

    ###########################################

    # Smoke test: prove the cookies are valid. If this fails, the search
    # failure isn't about query ids -- it's the account/cookies/IP.
    try:
        twid = cookies.get('twid', '')
        my_id = twid.split('%3D', 1)[-1] or twid.split('=', 1)[-1]
        print(f"[smoke] resolving my own user (id={my_id!r}) ...")
        me = await client.get_user_by_id(my_id)
        print(f"[smoke] OK -- @{me.screen_name} ({me.name}), "
              f"{me.followers_count} followers")
    except Exception as exc:
        print(
            f"[smoke] failed: {type(exc).__name__}: {exc}\n"
            f"[smoke] cookies don't grant access to even your own profile -- "
            f"either they expired or the account is locked. Re-export from "
            f"the browser.",
            file=sys.stderr,
        )
        raise

    ###########################################

    # Search Latest Tweets
    try:
        tweets = await client.search_tweet('query', 'Latest')
    except Exception as exc:
        print(
            f"[example] search_tweet failed: {type(exc).__name__}: {exc}\n"
            f"[example] If status:404 with an empty body above AND the smoke "
            f"test above succeeded, X is likely shadow-blocking search for "
            f"this account / IP (see d60/twikit#400). Try a different proxy "
            f"or a different account.",
            file=sys.stderr,
        )
        raise
    for tweet in tweets:
        print(tweet)
    # Search more tweets
    more_tweets = await tweets.next()

    ###########################################

    # Search users
    # users = await client.search_user('query')
    # for user in users:
    #     print(user)
    # # Search more users
    # more_users = await users.next()

    # ###########################################

    # # Get user by screen name
    # USER_SCREEN_NAME = 'example_user'
    # user = await client.get_user_by_screen_name(USER_SCREEN_NAME)

    # # Access user attributes
    # print(
    #     f'id: {user.id}',
    #     f'name: {user.name}',
    #     f'followers: {user.followers_count}',
    #     f'tweets count: {user.statuses_count}',
    #     sep='\n'
    # )

    # # Follow user
    # await user.follow()
    # # Unfollow user
    # await user.unfollow()

    # # Get user tweets
    # user_tweets = await user.get_tweets('Tweets')
    # for tweet in user_tweets:
    #     print(tweet)
    # # Get more tweets
    # more_user_tweets = await user_tweets.next()

    # ###########################################

    # # Send dm to a user
    # media_id = await client.upload_media('./image.png', 0)
    # await user.send_dm('dm text', media_id)

    # # Get dm history
    # messages = await user.get_dm_history()
    # for message in messages:
    #     print(message)
    # # Get more messages
    # more_messages = await messages.next()

    # ###########################################

    # # Get tweet by ID
    # TWEET_ID = '0000000000'
    # tweet = await client.get_tweet_by_id(TWEET_ID)

    # # Access tweet attributes
    # print(
    #     f'id: {tweet.id}',
    #     f'text {tweet.text}',
    #     f'favorite count: {tweet.favorite_count}',
    #     f'media: {tweet.media}',
    #     sep='\n'
    # )

    # # Favorite tweet
    # await tweet.favorite()
    # # Unfavorite tweet
    # await tweet.unfavorite()
    # # Retweet tweet
    # await tweet.retweet()
    # # Delete retweet
    # await tweet.delete_retweet()

    # # Reply to tweet
    # await tweet.reply('tweet content')

    # ###########################################

    # # Create tweet with media
    # TWEET_TEXT = 'tweet text'
    # MEDIA_IDS = [
    #     await client.upload_media('./media1.png', 0),
    #     await client.upload_media('./media2.png', 1),
    #     await client.upload_media('./media3.png', 2)
    # ]

    # client.create_tweet(TWEET_TEXT, MEDIA_IDS)

    # # Create tweet with a poll
    # TWEET_TEXT = 'tweet text'
    # POLL_URI = await client.create_poll(
    #     ['Option 1', 'Option 2', 'Option 3']
    # )

    # await client.create_tweet(TWEET_TEXT, poll_uri=POLL_URI)

    # ###########################################

    # # Get news trends
    # trends = await client.get_trends('news')
    # for trend in trends:
    #     print(trend)

    ###########################################

asyncio.run(main())
