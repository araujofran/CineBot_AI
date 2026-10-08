import asyncio
import hashlib
import hmac
import secrets
import time
from collections import deque
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import httpx

class VisitorMessage(BaseModel):
    message: str = Field(min_length=1, max_length=4000)

def sign_session(ident, secret):
    signature = hmac.new(secret.encode(), ident.encode(), hashlib.sha256).hexdigest()
    return ident + '.' + signature

def session_id(cookie, secret):
    if not cookie:
        return None
    parts = cookie.split('.')
    if len(parts) != 2 or len(parts[0]) != 32:
        return None
    expected = sign_session(parts[0], secret)
    return 'web-' + parts[0] if hmac.compare_digest(cookie, expected) else None

def public_router(settings, store):
    router = APIRouter(prefix='/visit')
    bearer = HTTPBearer()
    slots = asyncio.Semaphore(3)
    usage = {}
    global_usage = deque()

    def visitor(request: Request, credentials: HTTPAuthorizationCredentials = Depends(bearer)):
        if not settings.public_password or not hmac.compare_digest(credentials.credentials, settings.public_password):
            raise HTTPException(401, 'Senha de acesso inválida')
        user = session_id(request.cookies.get('cinebot_session'), settings.admin_token)
        if not user:
            raise HTTPException(401, 'Abra a página para iniciar uma sessão')
        return user

    @router.post('/chat')
    async def chat(data: VisitorMessage, request: Request, user: str = Depends(visitor)):
        now = time.monotonic()
        for key in list(usage):
            if not usage[key] or now - usage[key][-1] > 60:
                del usage[key]
        local = usage.setdefault(user, deque())
        for bucket in (local, global_usage):
            while bucket and bucket[0] < now - 60:
                bucket.popleft()
        if len(local) >= 10 or len(global_usage) >= 30 or slots.locked():
            raise HTTPException(429, 'Muitas solicitações; tente novamente em um minuto')
        local.append(now)
        global_usage.append(now)
        async with slots:
            try:
                answer = await request.app.state.chat.respond(user, data.message)
            except (httpx.HTTPError, ValueError):
                raise HTTPException(502, 'Não foi possível consultar a IA')
        return {'answer':answer, 'demo':not settings.llm_enabled}

    @router.delete('/memory')
    async def forget(request: Request, user: str = Depends(visitor)):
        service = request.app.state.chat
        async with service.locks.setdefault(user, asyncio.Lock()):
            store.forget(user)
        return {'deleted':True}

    return router
