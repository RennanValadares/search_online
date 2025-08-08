# SearchAPI - Modular Search + Scraping + LLM

Uma API completa e modular para pesquisa, scraping e processamento com LLM, construída com FastAPI.

## 🚀 Características

- **Agnóstico a provedores**: Suporte para múltiplos provedores de busca (Google, Bing) e LLM (OpenAI, OpenRouter)
- **Pipeline completo**: Buscar → Deduplicar → Ranquear → Scrapear → Extrair → Resumir/QA → Retornar com citações
- **Robusto**: Assíncrono, com retries, cache, rate limiting e logs estruturados
- **Conformidade**: Respeita robots.txt e não burla paywalls/CAPTCHAs
- **Modular**: Arquitetura limpa com interfaces bem definidas

## 🏗️ Arquitetura

```
/app
  /api            # FastAPI routers (endpoints)
  /core           # config, logger, errors, constants
  /domain         # contratos/interfaces e modelos de domínio
  /providers
    /search       # GoogleSearchProvider, BingSearchProvider
    /crawl        # HttpCrawler, PlaywrightCrawler
    /llm          # OpenAIClient, OpenRouterClient
  /services       # Orquestração de alto nível
  /utils          # Utilitários (cache, text processing)
```

## 📋 Pré-requisitos

- Python 3.8+
- Redis (opcional, para cache)
- Chaves de API dos provedores desejados

## 🛠️ Instalação

1. **Clone o repositório**:
```bash
git clone <repo-url>
cd searchapi
```

2. **Instale as dependências**:
```bash
pip install -r requirements.txt
```

3. **Configure as variáveis de ambiente**:
```bash
cp .env.example .env
# Edite o arquivo .env com suas chaves de API
```

4. **Instale o Playwright** (opcional, para sites com JavaScript):
```bash
playwright install chromium
```

## ⚙️ Configuração

### Provedores de Busca

**Google Custom Search**:
- Crie um projeto no Google Cloud Console
- Ative a Custom Search API
- Crie um Custom Search Engine em https://cse.google.com
- Configure `GOOGLE_API_KEY` e `GOOGLE_CX`

**Bing Web Search**:
- Crie uma conta no Azure
- Ative o Bing Search v7
- Configure `BING_API_KEY`

### Provedores de LLM

**OpenAI**:
- Crie uma conta em https://platform.openai.com
- Configure `OPENAI_API_KEY`

**OpenRouter**:
- Crie uma conta em https://openrouter.ai
- Configure `OPENROUTER_API_KEY`

## 🚀 Uso

### Iniciar o servidor

```bash
python main.py
```

Ou com uvicorn:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Endpoints principais

#### 1. Busca simples
```bash
GET /v1/search?q=python+programming&providers=google,bing&num=10
```

#### 2. Crawling de URLs
```bash
POST /v1/crawl
{
  "urls": ["https://example.com", "https://another-site.com"],
  "render_js": false
}
```

#### 3. Resumo de conteúdo
```bash
POST /v1/summarize
{
  "url": "https://example.com/article",
  "model": "openai:gpt-4o-mini",
  "max_length": 200
}
```

#### 4. Pipeline completo (Search + Read + Answer)
```bash
POST /v1/qa/search-read
{
  "query": "What are the benefits of Python programming?",
  "search_providers": ["google", "bing"],
  "num_search_results": 8,
  "max_docs_to_crawl": 5,
  "model": "openai:gpt-4o-mini",
  "return_citations": true
}
```

## 📊 Exemplo de Resposta QA

```json
{
  "answer": "Python programming offers several key benefits: [1] Easy to learn and read syntax, [2] Extensive library ecosystem, [3] Cross-platform compatibility...",
  "sources": [
    {
      "id": 1,
      "title": "Python Programming Benefits",
      "url": "https://example.com/python-benefits",
      "provider": "google"
    }
  ],
  "query": "What are the benefits of Python programming?",
  "tokens_used": 150,
  "processing_time": 3.2
}
```

## 🧪 Testes

```bash
# Instalar dependências de teste
pip install pytest pytest-asyncio httpx

# Executar testes
pytest tests/ -v
```

## 🔧 Desenvolvimento

### Adicionar novo provedor de busca

1. Implemente a interface `SearchProvider` em `/app/providers/search/`
2. Registre o provedor em `main.py`
3. Adicione testes em `/tests/providers/search/`

### Adicionar novo crawler

1. Implemente a interface `Crawler` em `/app/providers/crawl/`
2. Integre no `CrawlService`
3. Adicione testes

### Adicionar novo cliente LLM

1. Implemente a interface `LLMClient` em `/app/providers/llm/`
2. Registre em `main.py`
3. Adicione testes

## 📈 Performance

- **Cache Redis**: Resultados de busca (30min), conteúdo crawled (1h)
- **Concorrência**: Até 5 crawls simultâneos por padrão
- **Rate Limiting**: 60 requests/minuto por IP
- **Timeouts**: HTTP (10s), LLM (30s), Playwright (15s)

## 🛡️ Segurança

- Chaves de API mascaradas nos logs
- Validação de entrada com Pydantic
- Respeito ao robots.txt
- CORS configurável
- Rate limiting por IP

## 📝 Logs

Logs estruturados em JSON (produção) ou formato legível (desenvolvimento):

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "info",
  "logger": "app.services.qa_service",
  "message": "QA pipeline completed",
  "query": "python benefits",
  "total_time": 3.2,
  "sources_count": 5
}
```

## 🚀 Deploy

### Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

### Cloud Run / Render / Fly.io
Configure as variáveis de ambiente e faça deploy do container.

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature
3. Commit suas mudanças
4. Push para a branch
5. Abra um Pull Request

## 📄 Licença

MIT License - veja o arquivo LICENSE para detalhes.

## 🆘 Suporte

- Documentação: `/docs` (Swagger UI)
- Issues: GitHub Issues
- Health Check: `/v1/health`

---

**SearchAPI** - Construído com ❤️ usando FastAPI, httpx, trafilatura e muito mais.