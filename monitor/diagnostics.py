import difflib

from bs4 import BeautifulSoup


def diff_html_fragments(old: str, new: str) -> str:
    """Retorna diff unificado entre dois fragmentos HTML."""
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(old_lines, new_lines, fromfile="antes.html", tofile="depois.html", n=3)
    )


def diff_html_table(old: str, new: str) -> str:
    """Retorna diff em formato HTML (tabela side-by-side) para exibição no template."""
    d = difflib.HtmlDiff(wrapcolumn=80)
    return d.make_table(
        old.splitlines(),
        new.splitlines(),
        fromdesc="HTML anterior (funcionava)",
        todesc="HTML atual (seletor falhou)",
    )


def classify_change(old_html: str, new_html: str) -> str:
    """Classifica heuristicamente o tipo de mudança entre dois fragmentos HTML."""
    old_soup = BeautifulSoup(old_html, "lxml")
    new_soup = BeautifulSoup(new_html, "lxml")

    old_classes = {cls for tag in old_soup.find_all(True) for cls in (tag.get("class") or [])}
    new_classes = {cls for tag in new_soup.find_all(True) for cls in (tag.get("class") or [])}
    old_tags = {tag.name for tag in old_soup.find_all(True)}
    new_tags = {tag.name for tag in new_soup.find_all(True)}

    removed_classes = old_classes - new_classes
    added_classes = new_classes - old_classes

    if removed_classes and added_classes:
        return "renomeacao_de_classe_css"
    if removed_classes and not added_classes:
        return "elemento_removido"
    if old_tags - new_tags:
        return "tag_removida"
    if new_tags - old_tags:
        return "estrutura_adicionada"
    if old_html != new_html:
        return "conteudo_alterado"
    return "desconhecido"


def analyze_failure(selector_id: int) -> dict | None:
    """Compara último snapshot OK com snapshot atual com falha.

    Cria um ChangeEvent no banco com o relatório de diferenças.
    Retorna None se não houver falha para analisar.
    """
    from .models import ChangeEvent, Selector

    try:
        sel = Selector.objects.get(id=selector_id)
    except Selector.DoesNotExist:
        return None

    last_good = sel.snapshots.filter(status="ok").order_by("-checked_at").first()
    current = sel.snapshots.order_by("-checked_at").first()

    if not last_good or not current or current.status == "ok":
        return None

    # Evita criar eventos duplicados para o mesmo período de falha
    existing = sel.change_events.filter(resolved=False).order_by("-detected_at").first()
    if existing and last_good.checked_at == existing.detected_at:
        return None

    old_html = last_good.html_fragment
    new_html = current.html_fragment

    change_type = classify_change(old_html, new_html)
    diff_text = diff_html_fragments(old_html, new_html)

    ChangeEvent.objects.create(
        selector=sel,
        change_type=change_type,
        old_html_fragment=old_html,
        new_html_fragment=new_html,
        diff_report=diff_text[:10000],
    )

    return {
        "change_type": change_type,
        "diff_summary": diff_text[:3000],
        "old_fragment": old_html,
        "new_fragment": new_html,
    }
