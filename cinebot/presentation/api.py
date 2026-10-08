import asyncio
import contextlib
import hashlib
import hmac
import json
import logging
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, HTTPException, Request, Depends, Query
from fastapi.responses import PlainTextResponse, HTMLResponse, JSONResponse
from pathlib import Path
import secrets
from cinebot.presentation.public import public_router, sign_session, session_id
from fastapi.staticfiles import StaticFiles
from cinebot.infrastructure.tvmaze import CombinedCatalog
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from cinebot.domain.errors import LLMRateLimited
from cinebot.application.chat import ChatService
from cinebot.infrastructure.settings import Settings
from cinebot.infrastructure.storage import SQLiteStore
from cinebot.infrastructure.providers import TMDB, OpenAILLM, DemoLLM, WhatsApp

log = logging.getLogger(__name__)
bearer = HTTPBearer()

class ChatRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=4000)

class ChatResponse(BaseModel):
    answer: str
    demo: bool
    recommendations: list[dict] = Field(default_factory=list)

def create_app(settings=None):
    settings = settings or Settings()
    store = SQLiteStore(settings.database_path)

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(timeout=30) as client:
            catalog = CombinedCatalog(client, settings)
            app.state.catalog = catalog
            llm = OpenAILLM(client, settings) if settings.llm_enabled else DemoLLM()
            app.state.llm = llm
            app.state.chat = ChatService(store, catalog, llm)
            sender = WhatsApp(client, settings)
            async def worker():
                while True:
                    row = store.pending()
                    if row:
                        ident, payload, answer = row
                        data = json.loads(payload)
                        try:
                            if answer is None:
                                try:
                                    answer = await app.state.chat.respond(data['user'], data['text'])
                                except LLMRateLimited as exc:
                                    answer = exc.user_message.replace(' Sua mensagem continua no campo de envio.', '')
                                store.save_response(ident, answer)
                            await sender.send(data['user'], answer)
                            store.done(ident)
                        except Exception as exc:
                            log.warning('Falha no processamento: %s', type(exc).__name__)
                            store.retry(ident)
                    await asyncio.sleep(0.5)
            task = asyncio.create_task(worker())
            yield
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title='CineBot AI', version='0.1.0', lifespan=lifespan)

    @app.exception_handler(LLMRateLimited)
    async def rate_limit_error(request, exc):
        return JSONResponse(status_code=429, content={'detail':exc.detail()},
                            headers={'Retry-After':str(exc.retry_after_seconds)})

    app.mount('/assets', StaticFiles(directory=Path(__file__).parent / 'assets'), name='assets')

    def authorize(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
        if not hmac.compare_digest(credentials.credentials, settings.admin_token):
            raise HTTPException(401, 'Token inválido')

    @app.get('/', response_class=HTMLResponse)
    def home(request: Request):
        response = HTMLResponse(Path(__file__).with_name('index.html').read_text(encoding='utf-8'))
        if settings.public_password and not session_id(request.cookies.get('cinebot_session'), settings.admin_token):
            cookie = sign_session(secrets.token_hex(16), settings.admin_token)
            response.set_cookie('cinebot_session', cookie, httponly=True, samesite='strict', max_age=2592000)
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/health')
    def health(request: Request):
        llm = getattr(request.app.state, 'llm', None)
        wait = getattr(llm, 'remaining_wait', 0)
        return {'status':'ok','llm_retry_after_seconds':wait,'llm_wait_estimated':getattr(llm,'cooldown_estimated',False),'demo':not settings.llm_enabled,'provider':settings.llm_provider if settings.llm_enabled else 'demo','catalog_enabled':bool(settings.tmdb_token) or settings.tvmaze_enabled,'tvmaze_enabled':settings.tvmaze_enabled,'movie_catalog_enabled':bool(settings.tmdb_token),'whatsapp_enabled':not settings.demo,'public_mode':bool(settings.public_password),'local_default_token':settings.admin_token == 'change-me' and not settings.public_password}

    @app.get('/catalog/search')
    async def search_catalog(q: str = Query(min_length=2, max_length=100)):
        if not settings.tvmaze_enabled:
            raise HTTPException(503, 'Catálogo indisponível')
        try:
            return await app.state.catalog.tvmaze.execute('search_series', {'query':q})
        except httpx.HTTPError:
            raise HTTPException(502, 'TVMaze indisponível; tente novamente')

    @app.get('/catalog/shows/{show_id}')
    async def show_details(show_id: int):
        if show_id <= 0:
            raise HTTPException(422, 'ID inválido')
        if not settings.tvmaze_enabled:
            raise HTTPException(503, 'Catálogo indisponível')
        try:
            return await app.state.catalog.tvmaze.execute('series_details', {'show_id':show_id})
        except httpx.HTTPStatusError as exc:
            raise HTTPException(404 if exc.response.status_code == 404 else 502, 'Série não encontrada ou serviço indisponível')
        except httpx.HTTPError:
            raise HTTPException(502, 'TVMaze indisponível')

    @app.get('/catalog/featured')
    async def featured_catalog():
        if not settings.tvmaze_enabled:
            raise HTTPException(503, 'Catálogo indisponível')
        try:
            return await app.state.catalog.tvmaze.featured()
        except httpx.HTTPError:
            raise HTTPException(502, 'TVMaze indisponível; tente novamente')

    @app.post('/chat', response_model=ChatResponse, dependencies=[Depends(authorize)])
    async def chat(data: ChatRequest):
        try:
            answer = await app.state.chat.respond(data.user_id, data.message)
            return ChatResponse(answer=answer, demo=not settings.llm_enabled, recommendations=app.state.chat.recommendations.get(data.user_id,[]))
        except (httpx.HTTPError, ValueError):
            raise HTTPException(502, 'Não foi possível consultar os serviços externos')

    @app.delete('/users/{user_id}/memory', dependencies=[Depends(authorize)])
    async def forget(user_id: str):
        service = app.state.chat
        async with service.locks.setdefault(user_id, asyncio.Lock()):
            store.forget(user_id)
        return {'deleted':True}

    @app.get('/webhooks/whatsapp', response_class=PlainTextResponse)
    async def verify(request: Request):
        q = request.query_params
        if settings.whatsapp_verify_token and q.get('hub.mode') == 'subscribe' and hmac.compare_digest(q.get('hub.verify_token',''), settings.whatsapp_verify_token):
            return q.get('hub.challenge','')
        raise HTTPException(403, 'Verificação inválida')

    @app.post('/webhooks/whatsapp')
    async def webhook(request: Request):
        raw = await request.body()
        if len(raw) > 1_000_000:
            raise HTTPException(413, 'Payload excessivo')
        expected = 'sha256=' + hmac.new(settings.whatsapp_app_secret.encode(), raw, hashlib.sha256).hexdigest()
        if not settings.whatsapp_app_secret or not hmac.compare_digest(request.headers.get('x-hub-signature-256',''), expected):
            raise HTTPException(403, 'Assinatura inválida')
        try:
            payload = json.loads(raw)
            for entry in payload.get('entry', []):
                for change in entry.get('changes', []):
                    for message in change.get('value', {}).get('messages', []):
                        if message.get('type') == 'text':
                            data = ChatRequest(user_id=message['from'], message=message['text']['body'])
                            store.enqueue(message['id'], data.user_id, data.message)
        except (ValueError, KeyError, TypeError, AttributeError):
            raise HTTPException(400, 'Payload inválido')
        return {'accepted':True}
    app.include_router(public_router(settings, store))
    return app

app = create_app()
