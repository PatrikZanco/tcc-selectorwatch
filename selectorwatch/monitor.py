import re

import requests
from bs4 import BeautifulSoup
from lxml import etree

from .db import get_conn

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


def fetch_page(url: str, timeout: int = 20) -> str:
    resp = requests.get(url, headers=_HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def run_selector(html: str, selector: str, selector_type: str) -> list[str]:
    if selector_type == "css":
        soup = BeautifulSoup(html, "lxml")
        elements = soup.select(selector)
        return [el.get_text(strip=True) for el in elements if el.get_text(strip=True)]

    if selector_type == "xpath":
        parser = etree.HTMLParser()
        tree = etree.fromstring(html.encode(), parser)
        results = tree.xpath(selector)
        texts: list[str] = []
        for r in results:
            if isinstance(r, str):
                text = r.strip()
            elif hasattr(r, "text_content"):
                text = r.text_content().strip()
            else:
                text = str(r).strip()
            if text:
                texts.append(text)
        return texts

    raise ValueError(f"Tipo de seletor desconhecido: {selector_type!r}")


def extract_fragment(html: str, selector: str, selector_type: str) -> str:
    """Extrai o trecho de HTML relevante ao redor do seletor para armazenamento no snapshot."""
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
) -> tuple[bool, str]:
    if len(values) < min_results:
        return False, f"Esperado ≥{min_results} resultado(s), obtido {len(values)}"

    if not values:
        return False, "Nenhum resultado retornado"

    first = values[0]

    if expected_type == "number":
        cleaned = re.sub(r"[^\d.,\-]", "", first)
        cleaned = cleaned.replace(",", ".")
        try:
            float(cleaned)
        except ValueError:
            return False, f"Esperado número, obtido: {first!r}"

    elif expected_type == "url":
        if not (first.startswith("http") or first.startswith("/")):
            return False, f"Esperado URL, obtido: {first!r}"

    elif expected_type == "text":
        if not first:
            return False, "Esperado texto não vazio"

    return True, "ok"


def check_selector(selector_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT s.id, s.name AS selector_name, s.selector, s.selector_type,
                   s.expected_type, s.min_results,
                   si.url, si.name AS site_name
            FROM selectors s
            JOIN sites si ON si.id = s.site_id
            WHERE s.id = ? AND s.is_active = 1
            """,
            (selector_id,),
        ).fetchone()

    if not row:
        return {"status": "skipped", "reason": "seletor não encontrado ou inativo"}

    try:
        html = fetch_page(row["url"])
    except Exception as exc:
        return {"selector_id": selector_id, "status": "failed",
                "message": f"Erro ao buscar página: {exc}"}

    try:
        values = run_selector(html, row["selector"], row["selector_type"])
    except Exception as exc:
        return {"selector_id": selector_id, "status": "failed",
                "message": f"Erro ao executar seletor: {exc}"}

    is_valid, message = validate_result(values, row["expected_type"], row["min_results"])
    status = "ok" if is_valid else "failed"
    fragment = extract_fragment(html, row["selector"], row["selector_type"])
    extracted = values[0] if values else ""

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO snapshots (selector_id, html_fragment, extracted_value, status)
            VALUES (?, ?, ?, ?)
            """,
            (selector_id, fragment, extracted, status),
        )

    return {
        "selector_id": selector_id,
        "selector_name": row["selector_name"],
        "site_name": row["site_name"],
        "status": status,
        "values": values[:5],
        "message": message,
    }


def check_all_selectors() -> list[dict]:
    with get_conn() as conn:
        ids = [r["id"] for r in conn.execute(
            "SELECT id FROM selectors WHERE is_active = 1"
        ).fetchall()]
    return [check_selector(sid) for sid in ids]
