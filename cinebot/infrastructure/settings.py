from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from typing import Literal
from pathlib import Path

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    demo: bool = True
    database_path: str = 'data/cinebot.db'
    admin_token: str = 'change-me'
    public_password: str = ''
    llm_provider: Literal['openai', 'groq', 'ollama'] = 'openai'
    ollama_url: str = 'http://127.0.0.1:11434'
    ollama_model: str = 'qwen3:4b'
    groq_api_key_file: str = ''
    groq_model: str = 'openai/gpt-oss-120b'
    openai_api_key: str = ''
    openai_model: str = 'gpt-4.1-mini'
    tmdb_token: str = ''
    tvmaze_enabled: bool = True
    whatsapp_token: str = ''
    whatsapp_phone_id: str = ''
    whatsapp_app_secret: str = ''
    whatsapp_verify_token: str = ''
    whatsapp_api_version: str = 'v23.0'

    @property
    def llm_key(self):
        if self.llm_provider == 'ollama':
            return 'ollama'
        if self.llm_provider == 'groq':
            if not self.groq_api_key_file:
                return ''
            import re
            content = Path(self.groq_api_key_file).read_text(encoding='utf-8-sig')
            match = re.search(r'gsk_[A-Za-z0-9]+', content)
            if not match:
                raise ValueError('Arquivo Groq sem chave reconhecida')
            return match.group(0)
        return self.openai_api_key

    @property
    def llm_enabled(self):
        return bool(self.llm_key)

    @property
    def llm_url(self):
        if self.llm_provider == 'ollama':
            return self.ollama_url.rstrip('/') + '/v1/chat/completions'
        return 'https://api.groq.com/openai/v1/chat/completions' if self.llm_provider == 'groq' else 'https://api.openai.com/v1/chat/completions'

    @property
    def llm_model(self):
        if self.llm_provider == 'ollama':
            return self.ollama_model
        return self.groq_model if self.llm_provider == 'groq' else self.openai_model

    @model_validator(mode='after')
    def validate_live(self):
        if self.public_password and self.admin_token == 'change-me':
            raise ValueError('Configure ADMIN_TOKEN privado antes de habilitar visitantes')
        fields = ('tmdb_token', 'whatsapp_token', 'whatsapp_phone_id', 'whatsapp_app_secret', 'whatsapp_verify_token')
        if not self.demo and (not self.llm_enabled or any(not getattr(self, k) for k in fields) or self.admin_token == 'change-me'):
            raise ValueError('Configure credenciais e ADMIN_TOKEN para usar DEMO=false')
        return self
