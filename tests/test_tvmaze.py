import asyncio
import json
import httpx
import pytest
from cinebot.infrastructure.tvmaze import TVMaze, CombinedCatalog, TV_TOOLS
from cinebot.infrastructure.settings import Settings
from cinebot.infrastructure.providers import OpenAILLM

SHOW = {'id':169,'name':'Breaking Bad','url':'https://www.tvmaze.com/shows/169/breaking-bad',
        'premiered':'2008-01-20','genres':['Drama','Crime'],'summary':'<p>A <b>teacher</b> &amp; his choices.</p>',
        'image':None,'rating':{'average':9.2},'webChannel':{'name':'Original channel'}}

def test_tvmaze_search_cache_and_clean_data():
    requests=[]
    def handler(request):
        requests.append(request)
        assert request.url.params['q']=='Breaking Bad'
        return httpx.Response(200,json=[{'score':1,'show':SHOW}])
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            catalog=TVMaze(c)
            first=await catalog.execute('search_series',{'query':'Breaking Bad'})
            second=await catalog.execute('search_series',{'query':'Breaking Bad'})
            assert first==second
            return first
    result=asyncio.run(run())
    show=result['results'][0]
    assert show['summary']=='A teacher & his choices.'
    assert show['image'] is None
    assert 'não confirma' in show['availability_notice']
    assert show['source']=='TVMaze'
    assert len(requests)==1

def test_tvmaze_rejects_invalid_ids_and_missing_series():
    def handler(request):
        return httpx.Response(404)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            catalog=TVMaze(c)
            with pytest.raises(ValueError):
                await catalog.execute('series_details',{'show_id':-1})
            with pytest.raises(httpx.HTTPStatusError):
                await catalog.execute('series_details',{'show_id':999999999})
    asyncio.run(run())

def test_tvmaze_tools_without_tmdb_key():
    s=Settings(_env_file=None,llm_provider='openai',openai_api_key='fake',tmdb_token='',public_password='')
    async def run():
        calls=[]
        def handler(request):
            if request.url.host=='api.tvmaze.com':
                return httpx.Response(200,json=[{'show':SHOW}])
            body=json.loads(request.content)
            names=[tool['function']['name'] for tool in body['tools']]
            assert 'search_series' in names
            assert 'streaming' not in names
            calls.append(body)
            if len(calls)==1:
                msg={'role':'assistant','content':None,'tool_calls':[{'id':'tv1','type':'function','function':{'name':'search_series','arguments':'{"query":"Breaking Bad"}'}}]}
            else:
                output=json.loads(body['messages'][-1]['content'])
                assert output['results'][0]['id']==169
                msg={'role':'assistant','content':'Breaking Bad (2008), fonte TVMaze.'}
            return httpx.Response(200,json={'choices':[{'message':msg}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            catalog=CombinedCatalog(c,s)
            assert 'search_movies' not in catalog.tools
            return await OpenAILLM(c,s).reply([{'role':'user','content':'Breaking Bad'}],catalog)
    assert '2008' in asyncio.run(run())
