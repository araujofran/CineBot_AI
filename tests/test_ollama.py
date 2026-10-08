import asyncio
import json
import httpx
from cinebot.infrastructure.settings import Settings
from cinebot.infrastructure.providers import OpenAILLM, TOOLS

def test_ollama_tools_roundtrip():
    settings = Settings(_env_file=None, llm_provider='ollama', tmdb_token='')
    assert settings.llm_enabled
    calls = []
    def handler(request):
        assert str(request.url) == 'http://127.0.0.1:11434/v1/chat/completions'
        body = json.loads(request.content)
        assert body['model'] == 'qwen3:4b'
        assert body['max_tokens'] == 1200
        calls.append(body)
        if len(calls) == 1:
            message = {'role':'assistant','content':None,'tool_calls':[{'id':'local_1','type':'function','function':{'name':'search_movies','arguments':'{"query":"Arrival"}'}}]}
        else:
            assert body['messages'][-1]['role'] == 'tool'
            assert 'Arrival' in body['messages'][-1]['content']
            message = {'role':'assistant','content':'Arrival (2016).'}
        return httpx.Response(200, json={'choices':[{'message':message}]})
    class Catalog:
        tools = TOOLS
        async def execute(self, name, args):
            assert name == 'search_movies' and args['query'] == 'Arrival'
            return {'results':[{'title':'Arrival','year':2016}]}
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await OpenAILLM(client, settings).reply([{'role':'user','content':'Arrival'}], Catalog())
    assert asyncio.run(run()) == 'Arrival (2016).'
    assert len(calls) == 2
