import re

import requests
from bs4 import BeautifulSoup
from lxml import etree


def _parse_number(value: str) -> float | None:
    cleaned = re.sub(r"[^\d.,\-]", "", value).replace(",", ".")
    # handle "1.234.567,89" style (remove all dots then re-add for decimal)
    parts = cleaned.split(".")
    if len(parts) > 2:
        cleaned = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(cleaned)
    except ValueError:
        return None

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


def fetch_page(url: str, timeout: int = 20) -> str:
    resp = requests.get(url, headers=_HEADERS, timeout=timeout)
    resp.raise_for_status()
    # requests assume Latin-1 quando o servidor não declara charset;
    # preferred_encoding detecta corretamente UTF-8 nesses casos
    if resp.encoding and resp.encoding.lower() in ("iso-8859-1", "latin-1"):
        resp.encoding = resp.apparent_encoding
    return resp.text


def run_selector(html: str, selector: str, selector_type: str) -> list[str]:
    if selector_type == "css":
        soup = BeautifulSoup(html, "lxml")
        return [
            el.get_text(strip=True)
            for el in soup.select(selector)
            if el.get_text(strip=True)
        ]

    if selector_type == "xpath":
        tree = etree.HTML(html)
        if tree is None:
            return []
        texts: list[str] = []
        for r in tree.xpath(selector):
            if isinstance(r, etree._Element):
                # nó elemento: extrai todo o texto interno
                text = "".join(r.itertext()).strip()
            else:
                # string direta (ex: xpath com /text() ou @attr)
                text = str(r).strip()
            if text:
                texts.append(text)
        return texts

    raise ValueError(f"Tipo de seletor desconhecido: {selector_type!r}")


def extract_fragment(html: str, selector: str, selector_type: str) -> str:
    """Extrai trecho de HTML relevante ao redor do match do seletor.

    Quando o seletor encontra elementos, retorna o elemento pai (contexto).
    Quando falha, retorna o início do body para comparação pelo módulo de diagnóstico.
    """
    soup = BeautifulSoup(html, "lxml")

    if selector_type == "css":
        elements = soup.select(selector)
        if elements:
            parent = elements[0].parent
            return str(parent)[:6000] if parent else str(elements[0])[:6000]

    elif selector_type == "xpath":
        try:
            parser = etree.HTMLParser()
            tree = etree.fromstring(html.encode(), parser)
            results = tree.xpath(selector)
            if results and hasattr(results[0], "getparent"):
                parent = results[0].getparent()
                if parent is not None:
                    return etree.tostring(parent, encoding="unicode", method="html")[:6000]
        except Exception:
            pass

    body = soup.find("body")
    return str(body)[:6000] if body else html[:6000]


def validate_result(
    values: list[str], expected_type: str, min_results: int
) -> tuple[bool, str, str]:
    """Retorna (is_valid, message, failure_reason)."""
    from .models import Snapshot

    if not values:
        return False, "Nenhum resultado retornado", Snapshot.SELECTOR_EMPTY

    if len(values) < min_results:
        return False, f"Esperado ≥{min_results} resultado(s), obtido {len(values)}", Snapshot.SELECTOR_EMPTY

    first = values[0]

    if expected_type == "number":
        if _parse_number(first) is None:
            return False, f"Esperado número, obtido: {first!r}", Snapshot.TYPE_MISMATCH

    elif expected_type == "url":
        if not (first.startswith("http") or first.startswith("/")):
            return False, f"Esperado URL, obtido: {first!r}", Snapshot.TYPE_MISMATCH

    elif expected_type == "text":
        if not first:
            return False, "Esperado texto não vazio", Snapshot.TYPE_MISMATCH

    return True, "ok", ""


def check_selector(selector_id: int) -> dict:
    from .models import Selector, Snapshot

    try:
        sel = Selector.objects.select_related("site").get(id=selector_id, is_active=True)
    except Selector.DoesNotExist:
        return {"status": "skipped", "reason": "seletor não encontrado ou inativo"}

    try:
        html = fetch_page(sel.site.url)
    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else "?"
        Snapshot.objects.create(
            selector=sel,
            html_fragment="",
            extracted_value=f"[HTTP {code}]",
            status=Snapshot.FAILED,
            failure_reason=Snapshot.HTTP_ERROR,
        )
        return {
            "selector_id": selector_id,
            "status": "failed",
            "failure_type": Snapshot.HTTP_ERROR,
            "message": f"Erro HTTP {code}",
        }
    except Exception as exc:
        Snapshot.objects.create(
            selector=sel,
            html_fragment="",
            extracted_value=f"[REDE: {exc}]",
            status=Snapshot.FAILED,
            failure_reason=Snapshot.NETWORK_ERROR,
        )
        return {
            "selector_id": selector_id,
            "status": "failed",
            "failure_type": Snapshot.NETWORK_ERROR,
            "message": f"Erro de rede: {exc}",
        }

    try:
        values = run_selector(html, sel.selector, sel.selector_type)
    except Exception as exc:
        return {
            "selector_id": selector_id,
            "status": "failed",
            "failure_type": "selector_error",
            "message": f"Erro ao executar seletor: {exc}",
        }

    is_valid, message, failure_reason = validate_result(values, sel.expected_type, sel.min_results)
    status = Snapshot.OK if is_valid else Snapshot.FAILED
    fragment = extract_fragment(html, sel.selector, sel.selector_type)

    Snapshot.objects.create(
        selector=sel,
        html_fragment=fragment,
        extracted_value=values[0] if values else "",
        status=status,
        failure_reason=failure_reason,
    )

    result = {
        "selector_id": selector_id,
        "selector_name": sel.name,
        "site_name": sel.site.name,
        "status": "ok" if is_valid else "failed",
        "failure_type": failure_reason,
        "values": values[:5],
        "message": message,
    }

    # Detecção de anomalia de valor (apenas para seletores numéricos com threshold)
    if is_valid and sel.anomaly_threshold and sel.expected_type == "number" and values:
        last_ok = sel.snapshots.filter(status="ok").order_by("-checked_at")[1:2].first()
        if last_ok and last_ok.extracted_value:
            current_num = _parse_number(values[0])
            last_num = _parse_number(last_ok.extracted_value)
            if current_num is not None and last_num is not None and last_num != 0:
                change_pct = (current_num - last_num) / abs(last_num) * 100
                if abs(change_pct) > sel.anomaly_threshold:
                    result["anomaly"] = {
                        "previous": last_ok.extracted_value,
                        "current": values[0],
                        "previous_num": last_num,
                        "current_num": current_num,
                        "change_pct": round(change_pct, 1),
                    }

    return result


def check_all_selectors() -> list[dict]:
    from .models import Selector

    ids = list(Selector.objects.filter(is_active=True).values_list("id", flat=True))
    return [check_selector(sid) for sid in ids]
