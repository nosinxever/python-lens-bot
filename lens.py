import asyncio
import aiohttp
from web3 import Account
from eth_account.messages import encode_defunct

import json
import uuid



# pip install aiohttp web3 python-dotenv


class Lens:
    def __init__(self, private_key):
        self.url = 'https://api.lens.dev/'
        self.headers = {
            "referer": "https://lenster.xyz/",
            "origin": "https://lenster.xyz/",
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/102.0.0.0 Safari/537.36 "
        }
        self.headers_with_access_token = None

        self.private_key = private_key
        self.address = Account.privateKeyToAccount(private_key).address
        self.access_token = None
        self.user_id = None
        self.user_handle = None

        self.tx_id = None
        self.tx_hash = None

        asyncio.run(self.get_profile())

    async def get_message_for_signature(self):
        payload = {
            "operationName": "Challenge",
            "variables": {
                "request": {
                    "address": f"{self.address}"
                }
            },
            "query": "query Challenge($request: ChallengeRequest!) {\n  challenge(request: $request) {\n    text\n    "
                     "__typename\n  }\n} "
        }
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.post(self.url, json=payload) as response:
                    message = (await response.json())['data']['challenge']['text']
                    return message
        except Exception as e:
            print(f"Request failed: get message for signature {e}")
            return False

    async def get_signature(self):
        message = await self.get_message_for_signature()
        message_hash = encode_defunct(text=message)
        signed_message = Account.sign_message(
            message_hash, private_key=self.private_key)
        signature = signed_message.signature.hex()
        return signature

    async def get_access_token(self):
        signature = await self.get_signature()
        payload = {
            "operationName": "Authenticate",
            "variables": {
                "request": {
                    "address": f"{self.address}",
                    "signature": f"{signature}"
                }
            },
            "query": "mutation Authenticate($request: SignedAuthChallenge!) {\n  authenticate(request: $request) {\n  "
                     "  accessToken\n    refreshToken\n    __typename\n  }\n} "
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.url, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        access_token = data['data']['authenticate']['accessToken']
                        # refresh_token = data['data']['authenticate']['refreshToken']
                        self.access_token = access_token
                        self.headers_with_access_token = {
                            "referer": "https://lenster.xyz/",
                            "origin": "https://lenster.xyz/",
                            "content-type": "application/json",
                            "x-access-token": f"Bearer {access_token}",
                            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, "
                                          "like Gecko) Chrome/102.0.0.0 Safari/537.36 "
                        }
                        # print("get access token success")
                        return access_token
                    else:
                        print(f"Error: {response.status}")

        except aiohttp.ClientError as e:
            print(f"get access token fail: {e}")

    async def get_profile(self):
        access_token = await self.get_access_token()
        headers = {
            "referer": "https://lenster.xyz/",
            "origin": "https://lenster.xyz/",
            "content-type": "application/json",
            "x-access-token": f"Bearer {access_token}",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/102.0.0.0 Safari/537.36 "
        }
        payload = {
            "operationName": "UserProfiles",
            "variables": {
                "ownedBy": self.address
            },
            "query": "query UserProfiles($ownedBy: [EthereumAddress!]) {\n  profiles(request: {ownedBy: $ownedBy}) {"
                     "\n    items {\n      ...ProfileFields\n      interests\n      isDefault\n      dispatcher {\n   "
                     "     canUseRelay\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n  "
                     "userSigNonces {\n    lensHubOnChainSigNonce\n    __typename\n  }\n}\n\nfragment ProfileFields "
                     "on Profile {\n  id\n  name\n  handle\n  bio\n  ownedBy\n  isFollowedByMe\n  stats {\n    "
                     "totalFollowers\n    totalFollowing\n    __typename\n  }\n  attributes {\n    key\n    value\n   "
                     " __typename\n  }\n  picture {\n    ... on MediaSet {\n      original {\n        url\n        "
                     "__typename\n      }\n      __typename\n    }\n    ... on NftImage {\n      uri\n      "
                     "__typename\n    }\n    __typename\n  }\n  followModule {\n    __typename\n  }\n  __typename\n} "
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.url, headers=headers, data=json.dumps(payload)) as response:
                    data = await response.json()
                    result = {
                        "id": data["data"]["profiles"]["items"][0]["id"],
                        "name": data["data"]["profiles"]["items"][0]["name"],
                        "handle": data["data"]["profiles"]["items"][0]["handle"],
                        "totalFollowers": data["data"]["profiles"]["items"][0]["stats"]["totalFollowers"],
                        "totalFollowing": data["data"]["profiles"]["items"][0]["stats"]["totalFollowing"]
                    }
                    # print("get user profile success")
                    self.user_id = data["data"]["profiles"]["items"][0]["id"]
                    self.user_handle = data["data"]["profiles"]["items"][0]["handle"]
                    # return result
        except Exception as e:
            print(f"{self.address} failed to get profile: {e}")
            return False

    async def get_post_context_arid(self, post_context):
        # Arweave id
        url = "https://metadata.lenster.xyz/"

        payload = {
            "version": "2.0.0",
            "metadata_id": str(uuid.uuid4()),
            "description": post_context,
            "content": post_context,
            "external_url": f"https://lenster.xyz/u/{self.user_handle}",
            "image": None,
            "imageMimeType": "image/svg+xml",
            "name": f"Post by @{self.user_handle}",
            "tags": [],
            "animation_url": None,
            "mainContentFocus": "TEXT_ONLY",
            "contentWarning": None,
            "attributes": [{
                "traitType": "type",
                "displayType": "string",
                "value": "text_only"
            }],
            "media": [],
            "locale": "en-US",
            "appId": "Lenster"
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, headers=self.headers, json=payload) as response:
                    data = await response.json()
                    # print("get post_context arid success")
                    return data['id']
            except Exception as e:
                print(
                    f"{self.user_handle} get post context arid failed: {e}")
                return False

    async def post(self, post_context):
        arid = await self.get_post_context_arid(post_context)
        headers = {
            "referer": "https://claim.lens.xyz/",
            "origin": "https://claim.lens.xyz",
            "content-type": "application/json",
            "x-access-token": f"Bearer {self.access_token}",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/102.0.0.0 Safari/537.36 "
        }
        payload = {
            "operationName": "CreatePostViaDispatcher",
            "variables": {
                "request": {
                    "profileId": self.user_id,
                    "contentURI": f"https://arweave.net/{arid}",
                    "collectModule": {
                        "revertCollectModule": True
                    },
                    "referenceModule": {
                        "degreesOfSeparationReferenceModule": {
                            "commentsRestricted": True,
                            "mirrorsRestricted": True,
                            "degreesOfSeparation": 2
                        }
                    }
                }
            },
            "query": "mutation CreatePostViaDispatcher($request: CreatePublicPostRequest!) {\n  "
                     "createPostViaDispatcher(request: $request) {\n    ...RelayerResultFields\n    __typename\n  "
                     "}\n}\n\nfragment RelayerResultFields on RelayResult {\n  ... on RelayerResult {\n    txHash\n   "
                     " txId\n    __typename\n  }\n  ... on RelayError {\n    reason\n    __typename\n  }\n  "
                     "__typename\n} "
        }
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(self.url, headers=headers, json=payload) as response:
                    data = await response.json()
                    if data['data']['createPostViaDispatcher']['txId'] != "":
                        # print(f"{self.user_handle} post: {post_context} success")
                        return f"{self.user_handle} post: {post_context} success"
                    else:
                        # print(f"{self.user_handle} post fail")
                        return print(f"{self.user_handle} post fail")

            except Exception as e:
                print(f"{self.user_handle} post fail: {e}")
                return False

    async def get_recommended_users(self):

        payload = {"operationName": "RecommendedProfiles", "variables": {"options": {"shuffle": False}},
                   "query": "query RecommendedProfiles($options: RecommendedProfileOptions) {\n  recommendedProfiles("
                            "options: $options) {\n    ...ProfileFields\n    isFollowedByMe\n    __typename\n  "
                            "}\n}\n\nfragment ProfileFields on Profile {\n  id\n  name\n  handle\n  bio\n  ownedBy\n  "
                            "isFollowedByMe\n  stats {\n    totalFollowers\n    totalFollowing\n    __typename\n  }\n "
                            " attributes {\n    key\n    value\n    __typename\n  }\n  picture {\n    ... on MediaSet "
                            "{\n      original {\n        url\n        __typename\n      }\n      __typename\n    }\n "
                            "   ... on NftImage {\n      uri\n      __typename\n    }\n    __typename\n  }\n  "
                            "followModule {\n    __typename\n  }\n  __typename\n}"}
        async with aiohttp.ClientSession() as session:
            async with session.post(self.url, data=json.dumps(payload), headers=self.headers) as response:
                data = await response.json()
                recommended_users_list = []
                for user in data['data']['recommendedProfiles']:
                    recommended_users_list.append(user['handle'])
                print(recommended_users_list)
                return recommended_users_list

    async def get_profile_by_handle(self, user_handle):
        # get the profile id then you can follow
        # user_profile = await self.get_profile()
        payload = {
            'operationName': 'Profile',
            'variables': {
                'request': {
                    'handle': user_handle
                },
                'who': self.user_id
            },
            'query': 'query Profile($request: SingleProfileQueryRequest!, $who: ProfileId) {\n  profile(request: '
                     '$request) {\n    id\n    handle\n    ownedBy\n    name\n    bio\n    metadata\n    '
                     'followNftAddress\n    isFollowedByMe\n    isFollowing(who: $who)\n    attributes {\n      key\n '
                     '     value\n      __typename\n    }\n    dispatcher {\n      canUseRelay\n      __typename\n    '
                     '}\n    onChainIdentity {\n      proofOfHumanity\n      sybilDotOrg {\n        verified\n        '
                     'source {\n          twitter {\n            handle\n            __typename\n          }\n        '
                     '  __typename\n        }\n        __typename\n      }\n      ens {\n        name\n        '
                     '__typename\n      }\n      worldcoin {\n        isHuman\n        __typename\n      }\n      '
                     '__typename\n    }\n    stats {\n      totalFollowers\n      totalFollowing\n      totalPosts\n  '
                     '    totalComments\n      totalMirrors\n      __typename\n    }\n    picture {\n      ... on '
                     'MediaSet {\n        original {\n          url\n          __typename\n        }\n        '
                     '__typename\n      }\n      ... on NftImage {\n        uri\n        __typename\n      }\n      '
                     '__typename\n    }\n    coverPicture {\n      ... on MediaSet {\n        original {\n          '
                     'url\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    '
                     'followModule {\n      __typename\n    }\n    __typename\n  }\n} '
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.url, data=json.dumps(payload), headers=self.headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'profile' in data['data']:
                        print(
                            f"{user_handle}'s profile_id is {data['data']['profile']['id']}")
                        return data['data']['profile']['id']
                        # 'isFollowedByMe': data['data']['profile']['isFollowedByMe'],
                        # 'isFollowing': data['data']['profile']['isFollowing']

                    else:
                        print(
                            f'{self.user_handle} fail to get profile id: {data}')
                        return False
                else:
                    print(
                        f'{self.user_handle} request fail: {response.status}')
                    return False

    async def follow(self, user_handle):
        to_be_follow_profile_id = await self.get_profile_by_handle(user_handle)
        headers = {
            "referer": "https://claim.lens.xyz/",
            "origin": "https://claim.lens.xyz",
            "content-type": "application/json",
            "x-access-token": f"Bearer {self.access_token}",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/102.0.0.0 Safari/537.36 "
        }
        payload = {
            'operationName': 'ProxyAction',
            'variables': {
                'request': {
                    'follow': {
                        'freeFollow': {
                            'profileId': to_be_follow_profile_id
                        }
                    }
                }
            },
            'query': 'mutation ProxyAction($request: ProxyActionRequest!) {\n  proxyAction(request: $request)\n}'
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.url, data=json.dumps(payload), headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    print(data)
                    print(
                        f"{self.user_handle} follow {to_be_follow_profile_id} success")
                else:
                    print(
                        f"{self.user_handle} follow {to_be_follow_profile_id}  fail : {response.status}")
                    return False

    async def like(self, publication_id):
        # need to get publication_id first  publication_id : 0x012ba5-0x0122
        payload = {
            "operationName": "AddReaction",
            "variables": {
                "request": {
                    "profileId": f"{self.user_id}",
                    "reaction": "UPVOTE",
                    "publicationId": f"{publication_id}"
                }
            },
            "query": "mutation AddReaction($request: ReactionRequest!) {\n  addReaction(request: $request)\n}"
        }
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.post(self.url, json=payload) as response:
                    data = await response.json()
                    if data['data']['addReaction'] is None:
                        print(
                            f"{self.user_handle} like {publication_id} success ")
                    else:
                        print(f"{self.user_handle} like fail")
        except Exception as e:
            print(e)

    async def mirror(self, publication_id):
        # need to get publication_id first  publication_id : 0x012ba5-0x0122
        headers = {
            "referer": "https://claim.lens.xyz/",
            "origin": "https://claim.lens.xyz",
            "content-type": "application/json",
            "x-access-token": f"Bearer {self.access_token}",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/102.0.0.0 Safari/537.36 "
        }
        payload = {"operationName": "CreateMirrorViaDispatcher", "variables": {
            "request": {"profileId": f"{self.user_id}", "publicationId": f"{publication_id}",
                        "referenceModule": {"followerOnlyReferenceModule": False}}},
                   "query": "mutation CreateMirrorViaDispatcher($request: CreateMirrorRequest!) {\n  "
                            "createMirrorViaDispatcher(request: $request) {\n    ...RelayerResultFields\n    "
                            "__typename\n  }\n}\n\nfragment RelayerResultFields on RelayResult {\n  ... on "
                            "RelayerResult {\n    txHash\n    txId\n    __typename\n  }\n  ... on RelayError {\n    "
                            "reason\n    __typename\n  }\n  __typename\n}"}
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.post(self.url, json=payload) as response:
                    data = await response.json()
                    if data['data']['createMirrorViaDispatcher']['txHash'] is not None:
                        print(
                            f"{self.user_handle} mirror {publication_id} success ")
                    else:
                        print(f"{self.user_handle} mirror fail")
        except Exception as e:
            print(e)

    async def get_followers(self, profile_id):

        payload = {"operationName": "Followers", "variables": {"request": {"profileId": f"{profile_id}", "limit": 30}},
                   "query": "query Followers($request: FollowersRequest!) {\n  followers(request: $request) {\n    "
                            "items {\n      wallet {\n        address\n        defaultProfile {\n          "
                            "...ProfileFields\n          isFollowedByMe\n          __typename\n        }\n        "
                            "__typename\n      }\n      totalAmountOfTimesFollowed\n      __typename\n    }\n    "
                            "pageInfo {\n      next\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment "
                            "ProfileFields on Profile {\n  id\n  name\n  handle\n  bio\n  ownedBy\n  isFollowedByMe\n "
                            " stats {\n    totalFollowers\n    totalFollowing\n    __typename\n  }\n  attributes {\n  "
                            "  key\n    value\n    __typename\n  }\n  picture {\n    ... on MediaSet {\n      "
                            "original {\n        url\n        __typename\n      }\n      __typename\n    }\n    ... "
                            "on NftImage {\n      uri\n      __typename\n    }\n    __typename\n  }\n  followModule {"
                            "\n    __typename\n  }\n  __typename\n}"}
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.post(self.url, json=payload) as response:
                    data = await response.json()
                    followers_list = []
                    for follower in data['data']['followers']['items']:
                        handle = follower['wallet']['defaultProfile']['handle']
                        followers_list.append(handle)
                    print(followers_list)
                    return followers_list

        except Exception as e:
            print(e)

    async def get_following(self, address):
        payload = {"operationName": "Following",
                   "variables": {"request": {"address": f"{address}", "limit": 30}},
                   "query": "query Following($request: FollowingRequest!) {\n  following(request: $request) {\n    "
                            "items {\n      profile {\n        ...ProfileFields\n        isFollowedByMe\n        "
                            "__typename\n      }\n      totalAmountOfTimesFollowing\n      __typename\n    }\n    "
                            "pageInfo {\n      next\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment "
                            "ProfileFields on Profile {\n  id\n  name\n  handle\n  bio\n  ownedBy\n  isFollowedByMe\n "
                            " stats {\n    totalFollowers\n    totalFollowing\n    __typename\n  }\n  attributes {\n  "
                            "  key\n    value\n    __typename\n  }\n  picture {\n    ... on MediaSet {\n      "
                            "original {\n        url\n        __typename\n      }\n      __typename\n    }\n    ... "
                            "on NftImage {\n      uri\n      __typename\n    }\n    __typename\n  }\n  followModule {"
                            "\n    __typename\n  }\n  __typename\n}"}
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.post(self.url, json=payload) as response:
                    data = await response.json()
                    following_list = []
                    for follower in data['data']['following']['items']:
                        handle = follower['profile']['handle']
                        following_list.append(handle)
                    print(following_list)
                    return following_list
        except Exception as e:
            print(e)

    async def get_feed(self):
        # get publication_id
        headers = {
            "referer": "https://claim.lens.xyz/",
            "origin": "https://claim.lens.xyz",
            "content-type": "application/json",
            "x-access-token": f"Bearer {self.access_token}",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/102.0.0.0 Safari/537.36 "
        }
        payload = {"operationName": "Timeline",
                   "variables": {"request": {"profileId": f"{self.user_id}", "limit": 10,
                                             "feedEventItemTypes": ["POST", "COMMENT",
                                                                    "COLLECT_POST",
                                                                    "COLLECT_COMMENT",
                                                                    "MIRROR"]},
                                 "reactionRequest": {"profileId": f"{self.user_id}"},
                                 "profileId": f"{self.user_id}"},
                   "query": "query Timeline($request: FeedRequest!, $reactionRequest: ReactionFieldResolverRequest, "
                            "$profileId: ProfileId) {\n  feed(request: $request) {\n    items {\n      root {\n       "
                            " ... on Post {\n          ...PostFields\n          __typename\n        }\n        ... on "
                            "Comment {\n          ...CommentFields\n          __typename\n        }\n        "
                            "__typename\n      }\n      electedMirror {\n        mirrorId\n        profile {\n        "
                            "  ...ProfileFields\n          __typename\n        }\n        timestamp\n        "
                            "__typename\n      }\n      mirrors {\n        profile {\n          ...ProfileFields\n    "
                            "      __typename\n        }\n        timestamp\n        __typename\n      }\n      "
                            "collects {\n        profile {\n          ...ProfileFields\n          __typename\n        "
                            "}\n        timestamp\n        __typename\n      }\n      reactions {\n        profile {"
                            "\n          ...ProfileFields\n          __typename\n        }\n        reaction\n        "
                            "timestamp\n        __typename\n      }\n      comments {\n        ...CommentFields\n     "
                            "   __typename\n      }\n      __typename\n    }\n    pageInfo {\n      next\n      "
                            "__typename\n    }\n    __typename\n  }\n}\n\nfragment PostFields on Post {\n  id\n  "
                            "profile {\n    ...ProfileFields\n    __typename\n  }\n  reaction(request: "
                            "$reactionRequest)\n  mirrors(by: $profileId)\n  hasCollectedByMe\n  onChainContentURI\n  "
                            "isGated\n  canComment(profileId: $profileId) {\n    result\n    __typename\n  }\n  "
                            "canMirror(profileId: $profileId) {\n    result\n    __typename\n  }\n  canDecrypt("
                            "profileId: $profileId) {\n    result\n    reasons\n    __typename\n  }\n  collectModule "
                            "{\n    ...CollectModuleFields\n    __typename\n  }\n  stats {\n    ...StatsFields\n    "
                            "__typename\n  }\n  metadata {\n    ...MetadataFields\n    __typename\n  }\n  hidden\n  "
                            "createdAt\n  appId\n  __typename\n}\n\nfragment ProfileFields on Profile {\n  id\n  "
                            "name\n  handle\n  bio\n  ownedBy\n  isFollowedByMe\n  stats {\n    totalFollowers\n    "
                            "totalFollowing\n    __typename\n  }\n  attributes {\n    key\n    value\n    "
                            "__typename\n  }\n  picture {\n    ... on MediaSet {\n      original {\n        url\n     "
                            "   __typename\n      }\n      __typename\n    }\n    ... on NftImage {\n      uri\n      "
                            "__typename\n    }\n    __typename\n  }\n  followModule {\n    __typename\n  }\n  "
                            "__typename\n}\n\nfragment CollectModuleFields on CollectModule {\n  ... on "
                            "FreeCollectModuleSettings {\n    type\n    contractAddress\n    followerOnly\n    "
                            "__typename\n  }\n  ... on FeeCollectModuleSettings {\n    type\n    referralFee\n    "
                            "contractAddress\n    followerOnly\n    amount {\n      ...ModuleFeeAmountFields\n      "
                            "__typename\n    }\n    __typename\n  }\n  ... on LimitedFeeCollectModuleSettings {\n    "
                            "type\n    collectLimit\n    referralFee\n    contractAddress\n    followerOnly\n    "
                            "amount {\n      ...ModuleFeeAmountFields\n      __typename\n    }\n    __typename\n  }\n "
                            " ... on LimitedTimedFeeCollectModuleSettings {\n    type\n    collectLimit\n    "
                            "endTimestamp\n    referralFee\n    contractAddress\n    followerOnly\n    amount {\n     "
                            " ...ModuleFeeAmountFields\n      __typename\n    }\n    __typename\n  }\n  ... on "
                            "TimedFeeCollectModuleSettings {\n    type\n    endTimestamp\n    referralFee\n    "
                            "contractAddress\n    followerOnly\n    amount {\n      ...ModuleFeeAmountFields\n      "
                            "__typename\n    }\n    __typename\n  }\n  ... on MultirecipientFeeCollectModuleSettings "
                            "{\n    type\n    contractAddress\n    amount {\n      ...ModuleFeeAmountFields\n      "
                            "__typename\n    }\n    optionalCollectLimit: collectLimit\n    referralFee\n    "
                            "followerOnly\n    optionalEndTimestamp: endTimestamp\n    recipients {\n      "
                            "recipient\n      split\n      __typename\n    }\n    __typename\n  }\n  "
                            "__typename\n}\n\nfragment ModuleFeeAmountFields on ModuleFeeAmount {\n  asset {\n    "
                            "symbol\n    decimals\n    address\n    __typename\n  }\n  value\n  "
                            "__typename\n}\n\nfragment StatsFields on PublicationStats {\n  totalUpvotes\n  "
                            "totalAmountOfMirrors\n  totalAmountOfCollects\n  totalAmountOfComments\n  "
                            "__typename\n}\n\nfragment MetadataFields on MetadataOutput {\n  name\n  content\n  "
                            "image\n  attributes {\n    traitType\n    value\n    __typename\n  }\n  cover {\n    "
                            "original {\n      url\n      __typename\n    }\n    __typename\n  }\n  media {\n    "
                            "original {\n      url\n      mimeType\n      __typename\n    }\n    __typename\n  }\n  "
                            "encryptionParams {\n    accessCondition {\n      or {\n        criteria {\n          "
                            "...SimpleConditionFields\n          and {\n            criteria {\n              "
                            "...SimpleConditionFields\n              __typename\n            }\n            "
                            "__typename\n          }\n          or {\n            criteria {\n              "
                            "...SimpleConditionFields\n              __typename\n            }\n            "
                            "__typename\n          }\n          __typename\n        }\n        __typename\n      }\n  "
                            "    __typename\n    }\n    __typename\n  }\n  __typename\n}\n\nfragment "
                            "SimpleConditionFields on AccessConditionOutput {\n  nft {\n    contractAddress\n    "
                            "chainID\n    contractType\n    tokenIds\n    __typename\n  }\n  eoa {\n    address\n    "
                            "__typename\n  }\n  token {\n    contractAddress\n    amount\n    chainID\n    "
                            "condition\n    decimals\n    __typename\n  }\n  follow {\n    profileId\n    "
                            "__typename\n  }\n  collect {\n    publicationId\n    thisPublication\n    __typename\n  "
                            "}\n  __typename\n}\n\nfragment CommentFields on Comment {\n  id\n  profile {\n    "
                            "...ProfileFields\n    __typename\n  }\n  reaction(request: $reactionRequest)\n  mirrors("
                            "by: $profileId)\n  hasCollectedByMe\n  onChainContentURI\n  isGated\n  canComment("
                            "profileId: $profileId) {\n    result\n    __typename\n  }\n  canMirror(profileId: "
                            "$profileId) {\n    result\n    __typename\n  }\n  canDecrypt(profileId: $profileId) {\n  "
                            "  result\n    reasons\n    __typename\n  }\n  collectModule {\n    "
                            "...CollectModuleFields\n    __typename\n  }\n  stats {\n    ...StatsFields\n    "
                            "__typename\n  }\n  metadata {\n    ...MetadataFields\n    __typename\n  }\n  hidden\n  "
                            "createdAt\n  appId\n  commentOn {\n    ... on Post {\n      ...PostFields\n      "
                            "__typename\n    }\n    ... on Comment {\n      id\n      profile {\n        "
                            "...ProfileFields\n        __typename\n      }\n      reaction(request: "
                            "$reactionRequest)\n      mirrors(by: $profileId)\n      hasCollectedByMe\n      "
                            "onChainContentURI\n      isGated\n      canComment(profileId: $profileId) {\n        "
                            "result\n        __typename\n      }\n      canMirror(profileId: $profileId) {\n        "
                            "result\n        __typename\n      }\n      canDecrypt(profileId: $profileId) {\n        "
                            "result\n        reasons\n        __typename\n      }\n      collectModule {\n        "
                            "...CollectModuleFields\n        __typename\n      }\n      metadata {\n        "
                            "...MetadataFields\n        __typename\n      }\n      stats {\n        ...StatsFields\n  "
                            "      __typename\n      }\n      mainPost {\n        ... on Post {\n          "
                            "...PostFields\n          __typename\n        }\n        ... on Mirror {\n          "
                            "...MirrorFields\n          __typename\n        }\n        __typename\n      }\n      "
                            "hidden\n      createdAt\n      __typename\n    }\n    ... on Mirror {\n      "
                            "...MirrorFields\n      __typename\n    }\n    __typename\n  }\n  "
                            "__typename\n}\n\nfragment MirrorFields on Mirror {\n  id\n  profile {\n    "
                            "...ProfileFields\n    __typename\n  }\n  reaction(request: $reactionRequest)\n  "
                            "isGated\n  canComment(profileId: $profileId) {\n    result\n    __typename\n  }\n  "
                            "canMirror(profileId: $profileId) {\n    result\n    __typename\n  }\n  canDecrypt("
                            "profileId: $profileId) {\n    result\n    reasons\n    __typename\n  }\n  collectModule "
                            "{\n    ...CollectModuleFields\n    __typename\n  }\n  stats {\n    ...StatsFields\n    "
                            "__typename\n  }\n  metadata {\n    ...MetadataFields\n    __typename\n  }\n  hidden\n  "
                            "mirrorOf {\n    ... on Post {\n      ...PostFields\n      __typename\n    }\n    ... on "
                            "Comment {\n      id\n      profile {\n        ...ProfileFields\n        __typename\n     "
                            " }\n      collectNftAddress\n      reaction(request: $reactionRequest)\n      mirrors("
                            "by: $profileId)\n      onChainContentURI\n      isGated\n      canComment(profileId: "
                            "$profileId) {\n        result\n        __typename\n      }\n      canMirror(profileId: "
                            "$profileId) {\n        result\n        __typename\n      }\n      canDecrypt(profileId: "
                            "$profileId) {\n        result\n        reasons\n        __typename\n      }\n      stats "
                            "{\n        ...StatsFields\n        __typename\n      }\n      createdAt\n      "
                            "__typename\n    }\n    __typename\n  }\n  createdAt\n  appId\n  __typename\n}"}
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.post(self.url, json=payload) as response:
                    data = await response.json()
                    publication_id_from_feed = []
                    for item in data['data']['feed']['items']:
                        publication_id = item['root']['id']
                        publication_id_from_feed.append(publication_id)

                    print(publication_id_from_feed)
                    return publication_id_from_feed

        except Exception as e:
            print(e)


# if __name__ == '__main__':
    # bot = Lens()
    # asyncio.run(bot.get_recommended_users())
    # asyncio.run(bot.follow("0x0cc9"))
    # asyncio.run(bot.like('0x6acb-0x0343'))
    # asyncio.run(bot.mirror('0xfb33-0x24'))
    # asyncio.run(bot.get_followers('0xfb32'))
    # asyncio.run(bot.get_following('0xeE52b2CB6783a40c4DDD500BDF49a17533dED32d'))
    # asyncio.run(bot.get_feed())
    # asyncio.run(bot.post('Hello 23-3-15'))
    # asyncio.run(bot.comment('0xfb32-0x22', "hi there, how's going"))

    # feed_id_list = asyncio.run(bot.get_feed())
    # asyncio.run(bot.post('Hello March 2023'))
    # for id in feed_id_list:
    #     asyncio.run(bot.like(id))
