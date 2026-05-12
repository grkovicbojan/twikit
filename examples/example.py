import asyncio

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

###########################################

# Enter your account information
USERNAME = '@grkovicbojan90'
EMAIL = 'grkovicbojan90@gmail.com'
PASSWORD = 'Pajko19915!@#!@#'

client = Client('en-US', proxy='socks5://14ab94d7187c2:076d4ae3fa@206.53.57.231:12324')

async def main():
    # Asynchronous client methods are coroutines and
    # must be called using `await`.
    await client.login(
        auth_info_1=USERNAME,
        auth_info_2=EMAIL,
        password=PASSWORD
    )

    ###########################################

    # Search Latest Tweets
    tweets = await client.search_tweet('query', 'Latest')
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
