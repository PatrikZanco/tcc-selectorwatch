# Arquitetura do SelectorWatch

Sistema *self-healing* para seletores de web scrapers — detecção automática de falhas, diagnóstico por diff estrutural de HTML e sugestão de seletores alternativos via LLM.

TCC — Patrik Zanco — Ciência da Informação / UFSC.

---

## 1. Visão geral

O SelectorWatch monitora seletores CSS/XPath periodicamente. Quando um seletor para de funcionar (o site alterou o HTML), o sistema:

1. **Monitora** — registra snapshots de sucesso/falha de cada seletor.
2. **Diagnostica** — compara o HTML atual com o último snapshot bom (diff estrutural) e classifica o tipo de mudança.
3. **Sugere** — consulta a API da OpenAI (few-shot prompting) para propor novos seletores e os valida automaticamente contra o HTML atual.
4. **Apresenta** — dashboard web com métricas operacionais e de avaliação do protótipo.

---

## 2. Arquitetura de implantação (containers)

```mermaid
graph TB
    subgraph host["Máquina host / Docker Compose"]
        subgraph web["Container: web"]
            DJ["Django 5.x<br/>runserver :8000"]
            VIEWS["Views + Templates<br/>Bootstrap 5 / Chart.js"]
        end
        subgraph sched["Container: scheduler"]
            APS["APScheduler<br/>BlockingScheduler"]
        end
        DB[("SQLite<br/>data/selectorwatch.db")]
    end

    OPENAI["API da OpenAI<br/>gpt-4o-mini"]
    SITES["Sites alvo<br/>(HTML público)"]

    DJ --> DB
    APS --> DB
    APS -->|"HTTP GET"| SITES
    APS -->|"OpenAI SDK (HTTPS)"| OPENAI
    VIEWS -.->|"renderiza"| USER(["Navegador do usuário"])

    style web fill:#e3f2fd,stroke:#1565c0
    style sched fill:#e8f5e9,stroke:#2e7d32
    style DB fill:#fff3e0,stroke:#ef6c00
    style OPENAI fill:#f3e5f5,stroke:#6a1b9a
```

**Volume compartilhado:** `./data:/app/data` — o arquivo SQLite é acessível pelos dois containers. **Dependência de startup:** o `scheduler` aguarda o `web` subir (`condition: service_started`) para garantir que as migrations já foram aplicadas.

---

## 3. Stack tecnológica

| Camada | Tecnologia | Papel |
|---|---|---|
| **Backend / Web** | Python 3.11 + Django 5.x | ORM, admin, templates, migrations, servidor de desenvolvimento |
| **Banco de dados** | SQLite (via Django ORM) | Persistência (protótipo); migrável para PostgreSQL sem mudar código |
| **Scraping HTTP** | `requests` | Cliente HTTP com User-Agent realista e correção de encoding |
| **Parsing HTML** | `BeautifulSoup4` (CSS) + `lxml` (XPath) | Execução dos seletores nos dois formatos |
| **Diff / diagnóstico** | `difflib` + `BeautifulSoup4` | Diff unificado, tabela side-by-side e classificação heurística |
| **LLM** | API da OpenAI (`gpt-4o-mini`, configurável) | Sugestão de seletores via few-shot + chain-of-thought |
| **Cliente LLM** | OpenAI Python SDK | Chamada à API (tipagem, retry); `base_url` configurável |
| **Agendamento** | APScheduler (`BlockingScheduler`) | Um job por seletor + job de sincronização dinâmica |
| **Frontend** | Bootstrap 5.3 + Chart.js 4.4 (via CDN) | UI responsiva e 7 gráficos, sem build step |
| **Infraestrutura** | Docker Compose | 2 containers: `web` + `scheduler` |
| **Config** | `python-dotenv` (`.env`) | Separação de credenciais (chave OpenAI, secret Django) |

---

## 4. Os três módulos de negócio

Pipeline com responsabilidade única e sem ciclos — o fluxo vai sempre do Módulo 1 → 2 → 3.

| Módulo | Arquivo | Responsabilidade | Dependências |
|---|---|---|---|
| **1 — Monitoramento** | `monitor/scraper.py` | fetch → run_selector → validate → Snapshot | `requests`, `bs4`, `lxml` |
| **2 — Diagnóstico** | `monitor/diagnostics.py` | diff → classify → ChangeEvent | `difflib`, `bs4` |
| **3 — Sugestão LLM** | `monitor/llm.py` | prompt → OpenAI → valida sugestões | `openai`, Módulo 1 |

---

## 5. Fluxo de dados ponta a ponta

```mermaid
flowchart TD
    START(["APScheduler dispara<br/>_run_pipeline(selector_id)"]) --> M1

    subgraph M1["Módulo 1 — Monitoramento (scraper.py)"]
        F1["fetch_page(url)"] --> F2["run_selector(html, seletor, tipo)"]
        F2 --> F3["validate_result(valores, tipo, min)"]
        F3 --> F4["extract_fragment → HTML do pai"]
        F4 --> F5[("Snapshot.create<br/>status ok|failed")]
    end

    M1 --> Q1{"status == failed?<br/>(não é erro de rede/HTTP)"}
    Q1 -->|"Não / erro de rede"| ANOM
    Q1 -->|"Sim"| M2

    subgraph M2["Módulo 2 — Diagnóstico (diagnostics.py)"]
        D1["classify_change(old, new)<br/>heurística por classes/tags"] --> D2["diff_html_fragments"]
        D2 --> D3[("ChangeEvent.create<br/>change_type + diff")]
    end

    M2 --> Q2{"ChangeEvent criado?"}
    Q2 -->|"Sim"| M3

    subgraph M3["Módulo 3 — Sugestão LLM (llm.py)"]
        L1["_build_prompt<br/>few-shot + CoT"] --> L2["OpenAI SDK → API OpenAI"]
        L2 --> L3["parse JSON<br/>(limpa markdown fences)"]
        L3 --> L4["valida cada sugestão<br/>run_selector no HTML atual"]
        L4 --> L5[("event.save<br/>suggested + validation_results")]
    end

    M3 --> END(["Dashboard exibe<br/>diff + sugestões validadas"])

    ANOM{"numérico +<br/>anomaly_threshold?"} -->|"variação > limite"| ANOMEV[("ChangeEvent<br/>anomalia_de_valor")]
    ANOM -->|"não"| END

    style M1 fill:#e3f2fd,stroke:#1565c0
    style M2 fill:#fff3e0,stroke:#ef6c00
    style M3 fill:#f3e5f5,stroke:#6a1b9a
```

**Decisão de roteamento:** erros de rede/HTTP (sem HTML para analisar) pulam os Módulos 2 e 3 — não há fragmento para diff nem para o LLM.

---

## 6. Fluxo da sugestão via LLM (Módulo 3)

```mermaid
sequenceDiagram
    participant S as scheduler
    participant L as llm.py
    participant SDK as OpenAI SDK
    participant API as API da OpenAI
    participant DB as SQLite

    S->>L: suggest_selectors(selector_id)
    L->>DB: busca ChangeEvent sem sugestão
    L->>L: _build_prompt (few-shot + HTML old/new + diff)
    L->>SDK: chat.completions.create(model, temperature=0.1)
    SDK->>API: HTTPS (OPENAI_API_KEY)
    API-->>SDK: JSON com reasoning + suggested_selectors[]
    SDK-->>L: resposta
    L->>L: parse JSON + valida cada seletor no HTML atual
    L->>DB: event.suggested_selectors + validation_results
    Note over L,DB: validation gera a métrica llm_accuracy<br/>sem intervenção humana
```

**Configuração (tudo via `.env`):** `OPENAI_API_KEY`, `OPENAI_MODEL` (default `gpt-4o-mini`), `OPENAI_BASE_URL` (opcional).

---

## 7. Modelo de dados

```mermaid
erDiagram
    Site ||--o{ Selector : "tem"
    Selector ||--o{ Snapshot : "registra"
    Selector ||--o{ ChangeEvent : "gera"

    Site {
        int id PK
        string name
        url url UK
        int check_interval_minutes
        datetime created_at
    }
    Selector {
        int id PK
        int site_id FK
        string selector
        string selector_type "css|xpath"
        string expected_type "text|number|url|any"
        int min_results
        int anomaly_threshold "nullable"
        bool is_active
    }
    Snapshot {
        int id PK
        int selector_id FK
        text html_fragment
        text extracted_value
        string status "ok|failed"
        string failure_reason
        datetime checked_at
    }
    ChangeEvent {
        int id PK
        int selector_id FK
        string change_type
        text old_html_fragment
        text new_html_fragment
        text diff_report
        json suggested_selectors
        json validation_results
        bool resolved
        datetime detected_at
    }
```

`Snapshot` é *append-only* (imutável). `ChangeEvent` guarda o diagnóstico completo + a resposta do LLM e a validação de cada sugestão em campos `JSONField`.

---

## 8. Scheduler — sincronização dinâmica

```mermaid
graph LR
    SYNC["Job sync_selectors<br/>(a cada 30s)"] -->|"detecta novos"| ADD["Adiciona job<br/>selector_{id}"]
    SYNC -->|"detecta desativados"| RM["Cancela job"]
    ADD --> JOB["Job por seletor<br/>IntervalTrigger<br/>minutes = check_interval"]
    JOB -->|"dispara"| PIPE["_run_pipeline(selector_id)"]

    style SYNC fill:#e8f5e9,stroke:#2e7d32
    style JOB fill:#e3f2fd,stroke:#1565c0
```

- **Job de sincronização:** roda a cada 30s, adiciona/remove jobs conforme os seletores ativos no banco — sem reiniciar o scheduler.
- **Job por seletor:** `IntervalTrigger` com o intervalo do site; `max_instances=1` evita sobreposição se um check demorar mais que o intervalo.

---

## 9. Métricas de avaliação (dashboard)

Computadas na `DashboardView` e exibidas via Chart.js:

| Métrica | Fórmula | Significado |
|---|---|---|
| **Recall** | `selectors_com_event / selectors_com_falha` | % de falhas detectadas que geraram diagnóstico |
| **Precisão LLM** | `sugestões_válidas / sugestões_totais` | % de seletores sugeridos que realmente funcionam |
| **Auto-recuperação** | `events_com_sugestão_válida / total_events` | % de falhas com ao menos 1 correção válida |
| **MTTR** | média de `resolved_at − detected_at` | tempo real de recuperação (vs. baseline manual de 24h) |

---

## 10. Resumo do ciclo

```
Monitorar  →  Detectar falha  →  Diagnosticar (diff)  →  Sugerir (LLM)  →  Validar  →  Apresentar
 scraper          Snapshot          diagnostics            llm.py        run_selector   dashboard
```

O que tradicionalmente é manual (perceber a falha, inspecionar o DOM, reescrever o seletor, reimplantar) passa a ser um pipeline automático com diagnóstico transparente e sugestões já validadas.
