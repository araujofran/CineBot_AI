import asyncio
import html
import re
import time
from collections import OrderedDict
from pydantic import BaseModel, ConfigDict, Field
from cinebot.infrastructure.providers import TOOLS, Search, Person, TMDB

class Show(BaseModel):
    model_config = ConfigDict(extra='forbid')
    show_id: int = Field(gt=0)

TV_TOOLS = {
    'search_series': (Search, 'Busque séries e programas pelo título no TVMaze, não filmes.'),
    'series_details': (Show, 'Consulte sinopse, gêneros, ano, status, avaliação e emissora original de uma série.'),
    'series_cast': (Show, 'Consulte elenco e personagens de uma série.'),
    'search_tv_people': (Search, 'Busque atores e pessoas da televisão no TVMaze.'),
    'tv_credits': (Person, 'Consulte séries em que um ator participou.'),
}

def clean_show(show):
    return {
        'id': show['id'], 'name': show.get('name'), 'url': show.get('url'),
        'genres': show.get('genres', []), 'premiered': show.get('premiered'),
        'ended': show.get('ended'), 'status': show.get('status'),
        'rating': (show.get('rating') or {}).get('average'),
        'runtime': show.get('averageRuntime') or show.get('runtime'),
        'summary': html.unescape(re.sub('<[^>]+>', '', show.get('summary') or ''))[:1200],
        'image': (show.get('image') or {}).get('medium'),
        'original_network': (show.get('network') or show.get('webChannel') or {}).get('name'),
        'availability_notice': 'Emissora original não confirma disponibilidade atual de streaming no Brasil.',
        'source': 'TVMaze', 'license': 'CC BY-SA',
    }

class TVMaze:
    def __init__(self, client):
        self.client = client
        self.cache = OrderedDict()
        self.lock = asyncio.Lock()
        self.last_request = 0.0

    async def get(self, path, params=None):
        key = path + repr(sorted((params or {}).items()))
        async with self.lock:
            cached = self.cache.get(key)
            if cached and cached[0] > time.monotonic():
                self.cache.move_to_end(key)
                return cached[1]
            await asyncio.sleep(max(0, 0.55 - (time.monotonic() - self.last_request)))
            response = await self.client.get('https://api.tvmaze.com' + path, params=params, headers={'User-Agent':'CineBot/0.1 (TVMaze catalog)'})
            self.last_request = time.monotonic()
            if response.status_code == 429:
                await asyncio.sleep(2)
                response = await self.client.get('https://api.tvmaze.com' + path, params=params)
                self.last_request = time.monotonic()
            response.raise_for_status()
            data = response.json()
            self.cache[key] = (time.monotonic()+3600, data)
            if len(self.cache) > 128:
                self.cache.popitem(last=False)
            return data

    async def execute(self, name, arguments):
        if name not in TV_TOOLS:
            raise ValueError('Ferramenta TVMaze desconhecida')
        args = TV_TOOLS[name][0].model_validate(arguments).model_dump()
        if name == 'search_series':
            data = await self.get('/search/shows', {'q':args['query']})
            return {'results':[clean_show(item['show']) for item in data[:8]], 'source':'TVMaze'}
        if name == 'series_details':
            return clean_show(await self.get(f"/shows/{args['show_id']}"))
        if name == 'series_cast':
            data = await self.get(f"/shows/{args['show_id']}/cast")
            return {'cast':[{'name':item['person']['name'], 'character':item['character']['name']} for item in data[:16]], 'source':'TVMaze'}
        if name == 'search_tv_people':
            data = await self.get('/search/people', {'q':args['query']})
            return {'results':[{'id':item['person']['id'],'name':item['person']['name'],'url':item['person']['url']} for item in data[:8]], 'source':'TVMaze'}
        data = await self.get(f"/people/{args['person_id']}/castcredits", {'embed':'show'})
        return {'results':[clean_show(item['_embedded']['show']) for item in data[:8] if item.get('_embedded',{}).get('show')], 'source':'TVMaze'}

    async def featured(self):
        shows = []
        for ident in (169, 82, 46562, 430):
            shows.append(clean_show(await self.get(f'/shows/{ident}')))
        return {'results':shows, 'source':'TVMaze'}

class CombinedCatalog:
    def __init__(self, client, settings):
        self.tvmaze = TVMaze(client)
        self.tmdb = TMDB(client, settings.tmdb_token)
        self.tools = dict(TV_TOOLS) if settings.tvmaze_enabled else {}
        if settings.tmdb_token:
            self.tools.update(TOOLS)

    async def execute(self, name, arguments):
        if name not in self.tools:
            raise ValueError('Ferramenta indisponível')
        adapter = self.tvmaze if name in TV_TOOLS else self.tmdb
        return await adapter.execute(name, arguments)
