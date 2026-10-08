import asyncio
from cinebot.domain.ports import Memory, Catalog, LanguageModel

class ObservedCatalog:
    def __init__(self, catalog):
        self.catalog = catalog
        self.tools = getattr(catalog, 'tools', {})
        self.shows = {}

    async def execute(self, name, arguments):
        result = await self.catalog.execute(name, arguments)
        candidates = result.get('results', []) if isinstance(result, dict) else []
        if isinstance(result, dict) and result.get('source') == 'TVMaze' and 'genres' in result:
            candidates = candidates + [result]
        for show in candidates:
            if isinstance(show, dict) and show.get('source') == 'TVMaze' and 'genres' in show:
                self.shows[show['id']] = show
        return result

class ChatService:
    def __init__(self, memory: Memory, catalog: Catalog, llm: LanguageModel):
        self.memory, self.catalog, self.llm = memory, catalog, llm
        self.locks = {}
        self.recommendations = {}

    async def respond(self, user: str, text: str) -> str:
        async with self.locks.setdefault(user, asyncio.Lock()):
            if text.strip().lower() == '/esquecer':
                self.memory.forget(user)
                self.recommendations.pop(user, None)
                return 'Seu histórico foi apagado. 🍿'
            messages = self.memory.history(user) + [{'role': 'user', 'content': text}]
            observed = ObservedCatalog(self.catalog)
            answer = await self.llm.reply(messages, observed)
            if not answer.strip():
                raise ValueError('Resposta vazia')
            self.memory.append(user, 'user', text)
            self.memory.append(user, 'assistant', answer)
            self.recommendations[user] = list(observed.shows.values())[:8]
            return answer
