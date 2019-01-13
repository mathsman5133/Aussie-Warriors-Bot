from urllib.parse import quote

import json
import discord
import requests


def build_url(endpoint, api_version, uri_parts):
    uri_parts = [str(x) for x in uri_parts]
    # and encoded
    uri_parts = [quote(x) for x in uri_parts]
    # Add enpoint and version
    all_uri_parts = [endpoint, api_version, ] + uri_parts
    # join parts
    url_to_call = "/".join(all_uri_parts)

    return url_to_call


async def json_or_text(response):
    text = await response.text(encoding='utf-8')
    if response.headers['content-type'] == 'application/json':
        return json.loads(text)
    return json.loads(text)


class ApiResponse:
    pass


class ApiListResponse(list, ApiResponse):
    pass


class ApiDictResponse(dict, ApiResponse):
    pass


class ApiCall(object):
    """ Minified REST API call generator using attributes.

        REST URLs are replicated using properties and method calls as shown.
        The URI path:

            /locations/12003/rank/global

        Is replicated using sequence:

            api.locations(12003).rank.global

        In order make the api call, the methods `get` and `post` are provided
        (each using a different http method). In the call, the endpoint and the
        version of the api are included as the URL base. So, a sequence:

            api=ApiCall(endpoint='http://example.org', api_version='v1')
            api.locations(12003).rank.global.get()

        Will perform an http get to the URL:

            http://example.org/v1/locations/12003/rank/global

        The way it works, it that each access to `ApiCall` attributes returns a
        new API call with the attributtes with the existing one, but it appends
        the uri part. Sequential call, thus produce the explained result.

        Note that attributes starting with an underscore are omitted.

        Additionally, arguments are supported. To use them you must provide dictionary like parameters:

            api.clans(name='theclan', minMembers=10)
    """

    def __init__(self, bot, endpoint, api_version,
                 extract_items=True, uri_parts=None):
        """ Construct an ApiCall object.

            :param str endpoint: The endpoint od the API
            :param str api_version: The version of the API. Used to build the API url
            :param boolean extract_items: If true, response will be parsed and wraped
                in a list or dictionary. Otherwise, the requests response will be
                returned.
            :param tuple uri_parts: Provide an initial value to uri_parts. Used with
                recursive calls by the `__getattr__` and `__call__` methods.
        """
        self.bot = bot
        self.bearer_token = ''
        self.endpoint = endpoint
        self.api_version = api_version
        self.extract_items = extract_items

        if uri_parts is None:
            self.uri_parts = ()
        else:
            self.uri_parts = uri_parts

    def __getattr__(self, k):
        """ Append the name of the attribute to the uri_parts tuple.
            Attributes starting with an underscore are omitted. `self` is returned
            to enable chainability.
        """
        if k.startswith("_"):
            pass
        if k.startswith("connection"):
            pass
        else:
            return ApiCall(self.bot, self.endpoint, self.api_version,
                           extract_items=self.extract_items,
                           uri_parts=self.uri_parts + (k,))

    def __call__(self, *args):
        """ Append the arguments to the `uri_parts` tuple. `self` is returned
            to enable chainability.
        """
        if args:

            return ApiCall(self.bot, self.endpoint, self.api_version,
                           extract_items=self.extract_items,
                           uri_parts=self.uri_parts + args)
        return self

    def build_headers(self):
        """Build the required headers to make the API call
        """
        return {"Accept": "application/json", "authorization": "Bearer {}".format(self.bearer_token)}

    async def _process_call(self, method):

        url = build_url(self.endpoint, self.api_version, self.uri_parts)

        async with (await self.bot.httpsession()) as session:
            async with session.request(method, url, headers=self.build_headers()) as r:
                data = await json_or_text(r)

        return data

    async def get(self, token):
        """Execute a GET API call given by the `uri_parts` stored.
        """
        self.bearer_token = token
        data = await self._process_call('get')
        if 'reason' in data.keys():
            if data['reason'] in ['accessDenied.invalidIp', 'accessDenied']:
                try:
                    token = await self.new_token()
                except Exception as err:
                    e = discord.Embed(colour=discord.Colour.red())
                    e.add_field(name="Clash of Clans API Error",
                                value=f"Error: {err}\nProbably need to delete some keys from website")
                    await self.bot.get_channel(self.bot.info_channel_id).send(embed=e)
                    return

                self.bot.loaded['coctoken'] = token
                await self.bot.save_json()

                self.bearer_token = token
                data = await self._process_call('get')

        return data

    async def post(self, token):
        """Execute a POST API call given by the `uri_parts` stored.
        """
        self.bearer_token = token
        data = await self._process_call('post')

        if 'reason' in data.keys():
            if data['reason'] in ['accessDenied.invalidIp', 'accessDenied']:
                try:
                    token = await self.new_token()
                except Exception as err:
                    e = discord.Embed(colour=discord.Colour.red())
                    e.add_field(name="Clash of Clans API Error",
                                value=f"Error: {err}\nProbably need to delete some keys from website")
                    await self.bot.get_channel(self.bot.info_channel_id).send(embed=e)
                    return

                self.bot.loaded['coctoken'] = token
                await self.bot.save_json()

                self.bearer_token = token
                data = await self._process_call('post')

        return data

    async def new_token(self):

        current_ip = requests.get('http://ip.42.pl/short').text

        token_name = 'nameOfToken'
        token_description = 'This is an example'
        whitelisted_ips = [current_ip]  # must be a list even if only 1 item

        get_token_data = {'name': token_name,
                          'description': token_description,
                          'cidrRanges': whitelisted_ips}

        coc_api_login_url = 'https://developer.clashofclans.com/api/login'
        create_token_url = 'https://developer.clashofclans.com/api/apikey/create'
        list_tokens_url = 'https://developer.clashofclans.com/api/apikey/list'
        delete_token_url = 'https://developer.clashofclans.com/api/apikey/revoke'

        login_data = {'email': self.bot.loaded['cocemail'],
                      'password': self.bot.loaded['cocpassword']}

        login_headers = {'content-type': 'application/json'}

        # Start a session, in which we will be making request to log in and to generate new Token
        async with (await self.bot.httpsession()) as session:
            async with session.post(coc_api_login_url, json=login_data, headers=login_headers) as sess:
                response_dict = await sess.json()
                session = sess.cookies['session']

        # These are the cookies needed to create the Token
        game_api_token = response_dict['temporaryAPIToken']
        game_api_url = response_dict['swaggerUrl']

        # stitch together in same format as browser
        cookies = f'session={session};game-api-url={game_api_url};game-api-token={game_api_token}'

        token_header = {'cookie': cookies,
                        'content-type': 'application/json'}

        # Get list of existing keys
        async with (await self.bot.httpsession()) as session:
            async with session.post(list_tokens_url, json=(), headers=token_header) as sess:
                existing_tokens_dict = await sess.json()

        for token in existing_tokens_dict['keys']:

            if current_ip in token['cidrRanges']:
                return token['key']  # if we have a token already with that IP then why bother creating another one

            else:
                # otherwise if its an outdated IP adress we don't need it anymore, so lets delete it to not clog them up
                # and to prevent hitting the 10 token limit
                token_id = token['id']
                data = {'id': token_id}
                async with (await self.bot.httpsession()) as session:
                    async with session.post(delete_token_url, json=data, headers=token_header) as sess:
                        response = await sess.json()

        # POST request
        async with (await self.bot.httpsession()) as session:
            async with session.post(create_token_url, json=get_token_data, headers=token_header) as sess:
                response_dict = await sess.json()

        # Supercell is weird, this is how dictionary structure ends up being
        clean_token = response_dict['key']['key']

        e = discord.Embed(colour=discord.Colour.green())
        e.add_field(name='Updated COC Token',
                    value='\u200b')
        await (self.bot.get_channel(self.bot.info_channel_id)).send(embed=e)

        return clean_token


class ClashOfClans(ApiCall):
    """ Create a new Clash of clans connector.

        Use the `bearer_token` to identify your call.

        `endpoint` lets you change the api endpoint which is used to build the base URI.
         By default is uses 'https://api.clashofclans.com'.

        `api_version` is used to build the base URI. By default it uses 'v1'.

        Examples:

            To start the client:

                from coc import *
                coc = ClashOfClans(bearer_token=<api_key>)

            To access all locations use the call (GET /locations)

                coc.locations.get()

            To access a particular location given by an id (GET /locations/{locationId})

                coc.locations(32000218).get()

            To access the rankings of a location GET /locations/{locationId}/rankings/{rankingId}

                coc.locations(32000218).rankings('clans').get()
                coc.locations(32000218).rankings.clans.get()

            Note that attributes starting with an underscore are omitted.

            To include parameters in the call use provide dictionary like arguments to the call:

                coc.clans(name='theclan', minMembers=10).get()

            This produces /clans?name=theclan&minMembers=10. The parameters are uri encoded.

            When the results are split in more than one page (for instance, when we limit
            the number of results using the `limit` param) pagination is automatically
            handled by the client. In those cases the response will contain a `next` and ` previous`
            attributes to store the `ApiCall` objects to get the next and the previous page.
            For instance:

                r = coc.clans(nam='myclan', limit=5).get()
                r.next # contains the next api call to use
                r2 = r.next.get() # returns the second page

    """

    def __init__(self,
                 bot,
                 endpoint='https://api.clashofclans.com',
                 api_version='v1',
                 extract_items=True):
        """ Contruct a ClashOfClans client.

            :param str endpoint: the endpoint of the API. Default value is https://api.clashofclans.com
            :param str api_version: the version of the API. Default value is v1
            :param boolean extract_items: if True, the response will be parsed and wraped in a list or
                    dictionary. Otherwise, the requests response will be returned.
        """
        super(ClashOfClans, self).__init__(
            bot=bot,
            endpoint=endpoint,
            api_version=api_version,
            extract_items=extract_items
        )
