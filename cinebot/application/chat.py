import asyncio
from cinebot.domain.ports import Memory, Catalog, LanguageModel

class ChatService:
    def __init__(self, memory: Memory, catalog: Catalog, llm: LanguageModel):
        self.memory, self.catalog, self.llm = memory, catalog, llm
        self.locks = {}

    async def respond(self, user: str, text: str) -> str:
        async with self.locks.setdefault(user, asyncio.Lock()):
            if text.strip().lower() == '/esquecer':
                self.memory.forget(user)
                return 'Seu histórico foi apagado. 🍿'
            messages = self.memory.history(user) + [{'role': 'user', 'content': text}]
            answer = await self.llm.reply(messages, self.catalog)
            if not answer.strip():
                raise ValueError('Resposta vazia')
            self.memory.append(user, 'user', text)
            self.memory.append(user, 'assistant', answer)
            return answer
