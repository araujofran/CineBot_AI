import math

class LLMRateLimited(Exception):
    def __init__(self, retry_after_seconds=60, provider='Groq', estimated=False):
        self.retry_after_seconds = max(1, math.ceil(retry_after_seconds))
        self.provider = provider
        self.estimated = estimated
        super().__init__(self.user_message)

    @property
    def user_message(self):
        minutes = math.ceil(self.retry_after_seconds / 60)
        unit = 'minuto' if minutes == 1 else 'minutos'
        duration = f'{minutes} {unit}'
        if self.estimated:
            return (f'A {self.provider} atingiu o limite de requisições da IA. '
                    f'O serviço não informou o prazo de liberação. Aguarde cerca de {duration} '
                    'e pergunte novamente. Sua mensagem continua no campo de envio.')
        return (f'A {self.provider} atingiu o limite de requisições da IA. '
                f'Aguarde {duration} e pergunte novamente. Sua mensagem continua no campo de envio.')

    def detail(self):
        return {'code':'llm_rate_limit','message':self.user_message,
                'retry_after_seconds':self.retry_after_seconds,
                'estimated':self.estimated,'provider':self.provider}
