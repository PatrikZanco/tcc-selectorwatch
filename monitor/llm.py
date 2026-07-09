import json
import logging

from django.conf import settings
from openai import OpenAI

from .scraper import run_selector, validate_result

logger = logging.getLogger(__name__)

_FEW_SHOT_EXAMPLES = """
## Exemplo 1
Seletor quebrado (CSS): .product-price span
HTML anterior: <div class="product-price"><span>R$ 129,90</span></div>
HTML atual: <div class="price-wrapper"><p class="price-value">R$ 129,90</p></div>
Resposta JSON:
{
  "reasoning": "A classe 'product-price' foi renomeada para 'price-wrapper' e o span virou um parágrafo com classe 'price-value'.",
  "suggested_selectors": [
    {"selector": ".price-value", "confidence": "high", "explanation": "Seleciona pela nova classe semântica — independente do elemento pai."},
    {"selector": ".price-wrapper p", "confidence": "medium", "explanation": "Alternativa baseada no novo container."}
  ]
}

## Exemplo 2
Seletor quebrado (CSS): #main-title h1
HTML anterior: <div id="main-title"><h1>Título</h1></div>
HTML atual: <header class="page-header"><h1 class="title">Título</h1></header>
Resposta JSON:
{
  "reasoning": "O container mudou de id 'main-title' para class 'page-header', mas o h1 mantém a classe 'title'.",
  "suggested_selectors": [
    {"selector": "h1.title", "confidence": "high", "explanation": "Seleciona h1 pela nova classe — mais estável que depender do container pai."}
  ]
}
""".strip()


def _build_prompt(
    selector: str,
    selector_type: str,
    expected_type: str,
    old_fragment: str,
    new_fragment: str,
    change_type: str,
    diff_summary: str,
) -> str:
    return f"""Você é um especialista em web scraping. Um seletor {selector_type.upper()} parou de funcionar porque o site alterou sua estrutura HTML.

Analise as mudanças e sugira até 3 seletores alternativos que extraiam corretamente o mesmo dado.

{_FEW_SHOT_EXAMPLES}

---

## Caso atual
- Tipo: {selector_type.upper()}
- Seletor quebrado: `{selector}`
- Tipo de dado esperado: {expected_type}
- Mudança detectada: {change_type}

## HTML anterior (seletor funcionava):
```html
{old_fragment[:2000]}
```

## HTML atual (seletor falhou):
```html
{new_fragment[:2000]}
```

## Resumo do diff:
```
{diff_summary[:600]}
```

## Instruções de resposta
1. Identifique qual elemento o seletor buscava
2. Localize o equivalente no novo HTML
3. Sugira 1-3 seletores (mais robusto primeiro)
4. Prefira seletores baseados em atributos semânticos (data-*, aria-*, id fixo)

Responda APENAS com JSON válido, sem texto adicional:
{{
  "reasoning": "explicação clara do que mudou e por que o seletor quebrou",
  "suggested_selectors": [
    {{
      "selector": "o seletor",
      "confidence": "high|medium|low",
      "explanation": "por que este seletor funciona e é robusto"
    }}
  ]
}}"""


def _get_client() -> OpenAI:
    return OpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
        timeout=120.0,
    )


def suggest_selectors(selector_id: int) -> dict | None:
    """Consulta a API da OpenAI para sugerir seletores alternativos.

    Lê o ChangeEvent mais recente sem sugestão, chama o modelo configurado
    em OPENAI_MODEL, valida as sugestões e persiste os resultados.
    """
    from .models import ChangeEvent, Selector

    try:
        sel = Selector.objects.select_related("site").get(id=selector_id)
    except Selector.DoesNotExist:
        return None

    event = (
        sel.change_events.filter(suggested_selectors__isnull=True)
        .order_by("-detected_at")
        .first()
    )
    if not event:
        return None

    prompt = _build_prompt(
        selector=sel.selector,
        selector_type=sel.selector_type,
        expected_type=sel.expected_type,
        old_fragment=event.old_html_fragment,
        new_fragment=event.new_html_fragment,
        change_type=event.change_type or "desconhecido",
        diff_summary=event.diff_report[:600] if event.diff_report else "",
    )

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.1,   # baixa temperatura para respostas mais determinísticas
        )
        raw = response.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("Erro na chamada à API da OpenAI (modelo %s): %s", settings.OPENAI_MODEL, exc)
        return {"error": str(exc)}

    # Remove markdown code fences se presentes
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("LLM retornou JSON inválido: %s", raw[:300])
        return {"error": "JSON inválido retornado pelo LLM", "raw": raw[:300]}

    # Valida cada seletor sugerido contra o fragmento HTML atual
    new_html = event.new_html_fragment or ""
    validation_results = []
    for suggestion in result.get("suggested_selectors", []):
        suggested = suggestion.get("selector", "")
        try:
            values = run_selector(new_html, suggested, sel.selector_type)
            is_valid, msg, _ = validate_result(values, sel.expected_type, sel.min_results)
            validation_results.append({
                "selector": suggested,
                "works": is_valid,
                "extracted": values[:3],
                "message": msg,
            })
        except Exception as exc:
            validation_results.append({
                "selector": suggested,
                "works": False,
                "extracted": [],
                "message": str(exc),
            })

    event.suggested_selectors = result
    event.validation_results = validation_results
    event.save()

    return {
        "reasoning": result.get("reasoning", ""),
        "suggestions": result.get("suggested_selectors", []),
        "validations": validation_results,
    }
