# CineBot AI
MVP de assistente de filmes para WhatsApp: FastAPI, Python, Pydantic, pytest, Conda e GUI Tkinter.

## Executar
No terminal nesta pasta:
```powershell
conda env create -f environment.yml
conda activate cinebot
Copy-Item .env.example .env
python -m uvicorn cinebot.presentation.api:app --host 127.0.0.1 --port 8000
```
Em outro terminal com o ambiente ativado:
```powershell
python -m cinebot.presentation.gui
```
Alternativa sem Conda: crie um venv e execute `python -m pip install -e ".[dev]"`.
Swagger: http://127.0.0.1:8000/docs. A GUI usa o token ADMIN_TOKEN; padrão somente para demo: change-me.
Teste: `python -m pytest -q`.

## Arquitetura limpa em camadas
- domain: contratos independentes de frameworks.
- application: caso de uso de conversa, memória e exclusão.
- infrastructure: SQLite, configuração, OpenAI, TMDB e envio WhatsApp.
- presentation: rotas FastAPI com DTOs Pydantic e GUI HTTP.
O caso de uso recebe dependências pelos contratos. A composição ocorre na fábrica da API.

## Modo real
Edite .env com as credenciais e DEMO=false. TMDB_TOKEN é o token Bearer de leitura.
Configure um número WhatsApp Business Cloud, seu token, phone ID, app secret e verify token.
A versão Graph é configurável; confirme a versão habilitada no aplicativo Meta.
Publique com HTTPS e registre /webhooks/whatsapp na Meta, assinando eventos messages.
O GET verifica o desafio; o POST exige assinatura HMAC SHA256 do corpo original.
OPENAI_MODEL é configurável; o adaptador usa Chat Completions com function calling.
As ferramentas consultam busca, detalhes, semelhantes, gêneros, filtros por ano, pessoas,
filmografia e provedores por país (BR padrão). A LLM decide as chamadas dentro de um limite
de seis rodadas. Não há integração direta com API comercial JustWatch nesta versão.
Streaming vem do endpoint watch/providers do TMDB, com atribuição JustWatch e link retornado.
Inclua também as atribuições/logos oficiais TMDB e JustWatch na interface pública conforme
os termos antes de comercializar. Resultados são dados do provedor, sem garantia de disponibilidade.

## Memória e operação
Histórico por usuário em SQLite, últimas 20 mensagens enviadas ao modelo; registros com mais
de 30 dias são eliminados ao consultar histórico. /esquecer ou DELETE /users/{id}/memory
apaga histórico e conteúdo de eventos desse usuário. Preferências são inferidas do histórico;
perfil estruturado de longo prazo ainda não está implementado.
Informe usuários sobre armazenamento e retenção antes de ativar o número.

Webhook confirma após gravar a fila SQLite; worker realiza processamento e envio.
IDs repetidos não criam novos eventos. Falhas recebem até cinco tentativas, com intervalo
de 60 segundos; resposta gerada é persistida antes do envio. Eventos enviados mantêm apenas ID
para deduplicação. Eventos falhos requerem inspeção operacional do banco.
Execute **um único processo / worker Uvicorn**: fila e locks foram projetados para o MVP local.
Há uma janela de duplicação se o envio externo ocorrer e o processo cair antes de marcar como
concluído; garantia de envio exatamente uma vez exige suporte do provedor.
Use banco/queue externos, observabilidade, limites de requisição, retenção automática dos eventos,
gestão de consentimento e controle de custos antes de operar em escala.
A API administrativa exige Bearer token. Não exponha /chat publicamente sem controles adicionais.
Respostas automáticas são destinadas a mensagens recebidas; disparos e templates estão fora do escopo.

## Documentação das integrações
- https://developers.openai.com/api/docs/guides/function-calling
- https://developer.themoviedb.org/reference/movie-watch-providers
- https://apis.justwatch.com/docs/api/
- https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks

## Groq e conversa no navegador
Abra http://127.0.0.1:8000/ para a interface web.
Para Groq: LLM_PROVIDER=groq, GROQ_API_KEY_FILE=caminho/do/arquivo.txt e
GROQ_MODEL=openai/gpt-oss-120b. A chave é lida apenas pelo backend;
a pasta chavesGroqCloud e .env estão ignorados pelo Git.
Uma chave LLM ativa a conversa real mesmo com DEMO=true, que continua desabilitando
o envio real pelo WhatsApp. Sem TMDB_TOKEN, ferramentas de catálogo ficam desabilitadas
e o modelo responde com conhecimento próprio, sem confirmar streaming atual.
Documentação: https://console.groq.com/docs/tool-use/overview

## Acesso externo pelo computador
O sistema estÃ¡ exposto via Cloudflare Quick Tunnel HTTPS.
URL e senha de visitantes estÃ£o em data/public-url.txt e data/public-access.txt.
Compartilhe a URL e a senha; ADMIN_TOKEN e a chave Groq ficam privados.
Cada navegador recebe uma sessÃ£o assinada e consulta somente sua memÃ³ria.
Limites do chat pÃºblico: 10 mensagens por minuto por sessÃ£o, 30 no total e 3 simultÃ¢neas.
Os dados da conversa sÃ£o armazenados por atÃ© 30 dias, conforme limpeza descrita acima.
ApÃ³s reiniciar o computador, execute .\iniciar-publico.ps1 no PowerShell nesta pasta.
O endereÃ§o pode mudar apÃ³s reiniciar o tÃºnel; confira o novo link no log ou na saÃ­da do script.
Mantenha computador, conexÃ£o, backend e conector ativos e evite suspensÃ£o.
NÃ£o Ã© necessÃ¡rio abrir portas no roteador.
Quick Tunnels sÃ£o temporÃ¡rios, sem garantia de disponibilidade:
https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/

## TVMaze e interface de descoberta
O catálogo gratuito TVMaze funciona sem chave e está habilitado por padrão
(TVMAZE_ENABLED=true). Ele fornece séries e programas, não um catálogo de filmes.
A IA pode buscar títulos, consultar detalhes, elenco, pessoas e créditos de atores.
O catálogo composto disponibiliza ferramentas TMDB somente quando TMDB_TOKEN existe.
A emissora original informada por TVMaze não comprova streaming atual no Brasil.

A página inicial agora tem busca de séries, pôsteres, seleção editorial e chat integrado,
layout responsivo, navegação por teclado, mensagens com links seguros e indicador de busca.
CSS e JavaScript são servidos localmente em /assets, sem dependências de frontend externas.
A busca visual usa /catalog/search?q= e os destaques /catalog/featured.
TVMaze usa conexão HTTP reutilizada, cache de uma hora com limite de 128 entradas,
intervalo entre chamadas e recuo em caso de HTTP 429.
Dados TVMaze atribuídos na interface e respostas: https://www.tvmaze.com/ · CC BY-SA.
Documentação: https://www.tvmaze.com/api


## IA local com Ollama

Instale o Ollama oficial e execute `ollama pull qwen3:4b`. Configure `.env` com `LLM_PROVIDER=ollama`, `OLLAMA_URL=http://127.0.0.1:11434` e `OLLAMA_MODEL=qwen3:4b`. Inicie o Ollama antes do FastAPI. A integracao usa a API compativel com OpenAI e preserva ferramentas, memoria e autenticacao existentes. A geracao local e serializada para reduzir sobrecarga da GPU. TVMaze e TMDB continuam consultando servicos externos; disponibilidade de streaming exige fonte configurada. Nao publique a porta 11434.
