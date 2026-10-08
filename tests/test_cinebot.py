import asyncio
import hashlib
import hmac
import json
import pytest
from fastapi.testclient import TestClient
from cinebot.infrastructure.settings import Settings
from cinebot.infrastructure.storage import SQLiteStore
from cinebot.infrastructure.providers import TMDB, Movie
from cinebot.presentation.api import create_app

@pytest.fixture
def client(tmp_path):
    settings = Settings(_env_file=None, llm_provider='openai', openai_api_key='', groq_api_key_file='', database_path=str(tmp_path/'test.db'), admin_token='test', whatsapp_app_secret='secret', whatsapp_verify_token='verify')
    with TestClient(create_app(settings)) as c:
        yield c

AUTH = {'Authorization':'Bearer test'}

def test_memory_and_deletion(client):
    first = client.post('/chat', headers=AUTH, json={'user_id':'alice','message':'suspense'})
    assert first.status_code == 200
    assert '0 mensagem' in first.json()['answer']
    assert '1 mensagem' in client.post('/chat', headers=AUTH, json={'user_id':'alice','message':'outro'}).json()['answer']
    assert '0 mensagem' in client.post('/chat', headers=AUTH, json={'user_id':'bob','message':'outro'}).json()['answer']
    assert client.delete('/users/alice/memory', headers=AUTH).status_code == 200
    assert '0 mensagem' in client.post('/chat', headers=AUTH, json={'user_id':'alice','message':'outro'}).json()['answer']

def test_auth_validation(client):
    assert client.post('/chat', json={'user_id':'a','message':'x'}).status_code in (401,403)
    assert client.post('/chat', headers=AUTH, json={'user_id':'a','message':''}).status_code == 422
    assert client.post('/chat', headers={'Authorization':'Bearer wrong'}, json={'user_id':'a','message':'x'}).status_code == 401

def test_webhook_security(client):
    assert client.post('/webhooks/whatsapp', json={}).status_code == 403
    assert client.get('/webhooks/whatsapp', params={'hub.mode':'subscribe','hub.verify_token':'verify','hub.challenge':'123'}).text == '123'
    raw = json.dumps({'entry':[]}).encode()
    signature = 'sha256='+hmac.new(b'secret',raw,hashlib.sha256).hexdigest()
    assert client.post('/webhooks/whatsapp', content=raw, headers={'x-hub-signature-256':signature}).status_code == 200

def test_deduplication_and_retry(tmp_path):
    db = SQLiteStore(str(tmp_path/'db.sqlite'))
    db.enqueue('same','alice','hi')
    db.enqueue('same','alice','hi')
    assert db.pending()[0] == 'same'
    db.save_response('same','answer')
    db.retry('same')
    assert db.pending() is None
    db.done('same')
    with db.connect() as connection:
        assert connection.execute('SELECT count(*) FROM inbox').fetchone()[0] == 1

def test_tmdb_streaming():
    import httpx
    def handler(request):
        assert request.url.path == '/3/movie/157336/watch/providers'
        return httpx.Response(200, json={'results':{'BR':{'flatrate':[{'provider_name':'Example'}]}}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await TMDB(c,'token').execute('streaming', {'movie_id':157336,'country':'BR'})
    result = asyncio.run(run())
    assert result['providers']['flatrate'][0]['provider_name'] == 'Example'
    assert 'JustWatch' in result['attribution']

def test_live_requires_credentials():
    with pytest.raises(ValueError):
        Settings(_env_file=None, demo=False)
    with pytest.raises(ValueError):
        Movie(movie_id=-1)

def test_llm_tool_roundtrip():
    import httpx
    from cinebot.infrastructure.providers import OpenAILLM
    calls = []
    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 1:
            message = {'role':'assistant','content':None,'tool_calls':[{'id':'call_1','type':'function','function':{'name':'search_movies','arguments':'{"query":"Interestelar"}'}}]}
        else:
            assert body['messages'][-1]['role'] == 'tool'
            message = {'role':'assistant','content':'Interestelar (2014).'}
        return httpx.Response(200,json={'choices':[{'message':message}]})
    class FakeCatalog:
        async def execute(self, name, arguments):
            assert name == 'search_movies'
            assert arguments['query'] == 'Interestelar'
            return {'results':[{'id':157336,'title':'Interestelar'}]}
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            settings = Settings(_env_file=None, llm_provider='openai', openai_api_key='test', groq_api_key_file='', tmdb_token='test')
            return await OpenAILLM(c,settings).reply([{'role':'user','content':'Interestelar'}],FakeCatalog())
    assert asyncio.run(run()) == 'Interestelar (2014).'
    assert len(calls) == 2

def test_groq_configuration_and_request(tmp_path):
    import httpx
    from cinebot.infrastructure.providers import OpenAILLM
    keyfile = tmp_path/'key.txt'
    keyfile.write_text('gsk_fakeUnitTestOnly', encoding='utf-8')
    settings = Settings(_env_file=None, llm_provider='groq', groq_api_key_file=str(keyfile), tmdb_token='')
    def handler(request):
        assert str(request.url) == 'https://api.groq.com/openai/v1/chat/completions'
        assert request.headers['authorization'] == 'Bearer gsk_fakeUnitTestOnly'
        body = json.loads(request.content)
        assert body['model'] == 'openai/gpt-oss-120b'
        assert 'tools' not in body
        return httpx.Response(200,json={'choices':[{'message':{'role':'assistant','content':'Olá!'}}]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await OpenAILLM(c,settings).reply([{'role':'user','content':'Oi'}],None)
    assert asyncio.run(run()) == 'Olá!'
