# SelectorWatch

Sistema de detecção automática de falhas em seletores de web scrapers com apoio de inteligência artificial.

Trabalho de Conclusão de Curso — Ciência da Informação, UFSC, 2026.
Orientador: Prof. Dr. Márcio Matias.

---

## O problema

Web scrapers dependem de seletores CSS ou XPath para localizar dados em páginas HTML. Quando um site altera seu layout, esses seletores quebram silenciosamente — o scraper continua executando, mas retorna dados vazios ou incorretos. A correção manual é lenta, repetitiva e consome tempo que poderia ser dedicado à análise dos dados.

## A solução

O **SelectorWatch** monitora seletores continuamente, detecta falhas automaticamente, compara snapshots de HTML para identificar o que mudou e consulta a API da OpenAI para sugerir seletores alternativos — com explicação do raciocínio e validação automática das sugestões.

---

## Arquitetura

```
┌──────────────────────────────────────────────────────┐
│                    Docker Compose                    │
│                                                      │
│  ┌─────────────┐    ┌─────────────┐                  │
│  │     web     │    │  scheduler  │                  │
│  │  Django     │    │  APScheduler│                  │
│  │  :8000      │    │             │                  │
│  └──────┬──────┘    └──────┬──────┘                  │
│         │                 │                          │
│         └────────┬─────────┘                         │
└──────────────────┼───────────────────────────────────┘
                   ▼
            ┌─────────────┐
            │  OpenAI API │  chamada direta via SDK
            │  gpt-4o-mini│
            └─────────────┘
```

**5 módulos integrados:**

| Módulo | Arquivo | Responsabilidade |
|--------|---------|-----------------|
| 1 — Monitoramento | `monitor/scraper.py` | Busca páginas, executa seletores, valida resultados |
| 2 — Diagnóstico | `monitor/diagnostics.py` | Compara snapshots HTML, classifica o tipo de mudança |
| 3 — Sugestão LLM | `monitor/llm.py` | Consulta a API da OpenAI, valida sugestões |
| 4 — Relatórios | `monitor/views.py` + templates | Dashboard web com diff e sugestões |
| 5 — Histórico | `monitor/models.py` | Persiste snapshots e eventos no SQLite |

---

## Pré-requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Mac/Windows/Linux)
- Uma chave de API da OpenAI ([platform.openai.com/api-keys](https://platform.openai.com/api-keys))
- `make` (incluso no macOS via Xcode Command Line Tools)

---

## Início rápido

```bash
# 1. Clone o repositório
git clone <url-do-repositorio>
cd tcc

# 2. Configure sua chave da OpenAI no .env
cp .env.example .env
# edite OPENAI_API_KEY (e, se quiser, OPENAI_MODEL)

# 3. Sobe tudo com um único comando
make up
```

Após o `make up`:

- **Dashboard:** http://localhost:8000
- **Admin Django:** http://localhost:8000/admin

```bash
# 4. Crie o superusuário para acessar o admin
make superuser

# 5. Adicione um site e seletor de exemplo
make add-site

# 6. Verifique o seletor manualmente
make check
```

---

## Configuração

O arquivo `.env` é criado automaticamente no primeiro `make up` a partir de `.env.example`.

```env
# Chave secreta do Django
DJANGO_SECRET_KEY=django-insecure-selectorwatch-tcc-troque-em-producao

# API da OpenAI (Módulo 3 — Sugestão via LLM)
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4o-mini

# Opcional: URL base customizada (vazio = API oficial da OpenAI)
# OPENAI_BASE_URL=
```

### Trocar o modelo

```bash
# 1. Atualize o .env com o modelo desejado
OPENAI_MODEL=gpt-4o

# 2. Reinicie os containers
make restart
```

---

## Comandos disponíveis

```bash
make help             # lista todos os comandos
make up               # build + sobe os containers (web + scheduler)
make down             # para tudo
make restart          # reinicia sem rebuild
make logs             # logs em tempo real (todos)
make logs-web         # logs do servidor Django
make logs-scheduler   # logs do scheduler

make superuser        # cria superusuário Django
make shell            # shell interativo do Django
make add-site         # cadastra site de exemplo
make check            # verifica todos os seletores agora
make diagnose ID=1    # diagnostica seletor + consulta LLM

make migrate          # aplica migrations manualmente
make clean            # remove containers, volumes e imagens
```

---

## Gerenciamento via CLI (Django management commands)

```bash
# Dentro do container web:
docker compose exec web python manage.py <comando>

# Cadastrar um site
python manage.py add_site --name "Meu Site" --url "https://exemplo.com" --interval 60

# Adicionar um seletor
python manage.py add_selector \
  --site-id 1 \
  --name "Preço do produto" \
  --selector ".price" \
  --type css \
  --expected number \
  --min-results 1

# Verificar todos os seletores manualmente
python manage.py check_selectors

# Verificar seletor específico
python manage.py check_selectors --id 1

# Diagnosticar falha + consultar LLM
python manage.py diagnose_selector 1

# Diagnosticar apenas (sem LLM)
python manage.py diagnose_selector 1 --no-llm

# Iniciar monitoramento contínuo
python manage.py run_scheduler
```

---

## Estrutura do projeto

```
tcc/
├── Dockerfile
├── Makefile
├── docker-compose.yml
├── entrypoint.sh
├── pyproject.toml
├── .env.example
├── manage.py
│
├── config/                    ← projeto Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── monitor/                   ← app Django (todos os módulos)
│   ├── models.py              ← Site, Selector, Snapshot, ChangeEvent
│   ├── admin.py               ← painel de administração
│   ├── views.py               ← Dashboard, EventList, EventDetail, History
│   ├── urls.py
│   ├── scraper.py             ← Módulo 1: monitoramento
│   ├── diagnostics.py         ← Módulo 2: diff e classificação
│   ├── llm.py                 ← Módulo 3: sugestão via API da OpenAI
│   ├── scheduler.py           ← APScheduler
│   └── management/commands/
│       ├── add_site.py
│       ├── add_selector.py
│       ├── check_selectors.py
│       ├── diagnose_selector.py
│       └── run_scheduler.py
│
├── templates/                 ← templates Bootstrap 5
│   ├── base.html
│   ├── dashboard.html
│   ├── event_list.html
│   ├── event_detail.html
│   └── history.html
│
└── data/                      ← banco SQLite (gerado em runtime, não versionado)
    └── selectorwatch.db
```

---

## Fluxo de funcionamento

```
[Scheduler]
     │
     ├─ 1. fetch_page(url)                   → HTML da página
     ├─ 2. run_selector(html, selector)       → valores extraídos
     ├─ 3. validate_result(valores)           → OK ou FALHA
     │
     │  Se FALHA:
     ├─ 4. analyze_failure()                 → compara snapshots HTML
     │      classify_change()                → tipo: renomeação de classe,
     │      diff_html_fragments()               remoção de elemento, etc.
     │
     └─ 5. suggest_selectors()              → prompt few-shot + CoT
            API da OpenAI                   → JSON com sugestões
            validate_suggestion()           → testa cada sugestão

[Dashboard]
     └─ Exibe status, diffs side-by-side, sugestões validadas, histórico
```

---

## Métricas de avaliação (TCC)

O sistema coleta automaticamente os dados para as métricas definidas no trabalho:

| Métrica | Descrição | Onde encontrar |
|---------|-----------|---------------|
| **Recall** | % de falhas detectadas em até 24h | `ChangeEvent` vs. falhas reais |
| **Accuracy** | % de sugestões que extraem o dado correto | `validation_results` em cada `ChangeEvent` |
| **MTTR** | Tempo entre detecção e sugestão válida | `detected_at` vs. `resolved_at` |

### Setup para avaliação

```bash
# 1. Cadastre os 10-20 sites alvo
docker compose exec web python manage.py add_site --name "..." --url "..."

# 2. Configure seletores com baseline conhecido
docker compose exec web python manage.py add_selector --site-id 1 ...

# 3. Inicie o monitoramento (4-6 semanas)
make up

# 4. Para induzir falhas artificiais (páginas de teste):
#    Altere manualmente o HTML e verifique se o sistema detecta

# 5. Exporte dados via admin Django ou shell:
docker compose exec web python manage.py shell
>>> from monitor.models import ChangeEvent
>>> ChangeEvent.objects.filter(resolved=True).count()
```

---

## Stack tecnológica

| Componente | Tecnologia |
|-----------|-----------|
| Backend | Python 3.11 + Django 5 |
| Banco de dados | SQLite (via Django ORM) |
| HTML parsing | BeautifulSoup4 + lxml |
| Agendamento | APScheduler |
| LLM | API da OpenAI (`gpt-4o-mini`, configurável) |
| Cliente LLM | OpenAI Python SDK |
| Frontend | Django templates + Bootstrap 5 |
| Infraestrutura | Docker Compose |

---

## Contexto acadêmico

Este protótipo foi desenvolvido como parte do Trabalho de Conclusão de Curso em Ciência da Informação pela Universidade Federal de Santa Catarina (UFSC). O trabalho se insere na interseção entre recuperação da informação, web scraping e inteligência artificial generativa, propondo uma ferramenta transparente de auto-recuperação de seletores que, diferentemente das soluções comerciais existentes, fornece ao desenvolvedor o diagnóstico completo da falha, o raciocínio da correção e um histórico estruturado de mudanças.

**Palavras-chave:** Web scraping · Seletores CSS · Inteligência artificial · Modelos de linguagem · Recuperação da informação · Self-healing
