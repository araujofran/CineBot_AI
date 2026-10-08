from fastapi.testclient import TestClient
from cinebot.infrastructure.settings import Settings
from cinebot.presentation.api import create_app

def test_public_access_and_isolation(tmp_path):
    s = Settings(_env_file=None, llm_provider='openai', openai_api_key='', groq_api_key_file='', admin_token='private-admin', public_password='visitor-pass', database_path=str(tmp_path/'db'))
    app = create_app(s)
    headers = {'Authorization':'Bearer visitor-pass'}
    with TestClient(app) as a, TestClient(app) as b:
        assert a.post('/visit/chat',headers=headers,json={'message':'oi'}).status_code == 401
        assert a.get('/').status_code == 200
        assert b.get('/').status_code == 200
        assert a.post('/visit/chat',json={'message':'oi'}).status_code in (401,403)
        assert '0 mensagem' in a.post('/visit/chat',headers=headers,json={'message':'oi'}).json()['answer']
        assert '1 mensagem' in a.post('/visit/chat',headers=headers,json={'message':'outro'}).json()['answer']
        assert '0 mensagem' in b.post('/visit/chat',headers=headers,json={'message':'oi'}).json()['answer']
        assert a.post('/chat',headers=headers,json={'user_id':'b','message':'oi'}).status_code == 401
        assert a.delete('/visit/memory',headers=headers).status_code == 200
        assert '0 mensagem' in a.post('/visit/chat',headers=headers,json={'message':'oi'}).json()['answer']
        assert not a.get('/health').json()['local_default_token']
        a.cookies.set('cinebot_session','forged')
        assert a.post('/visit/chat',headers=headers,json={'message':'oi'}).status_code == 401
