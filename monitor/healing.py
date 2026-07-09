import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def apply_recommendation(event_id: int) -> dict | None:
    """Aplica automaticamente a melhor sugestão validada ao seletor quebrado.

    Escolhe a primeira sugestão cujo teste automático passou (works=True) — as
    sugestões vêm ordenadas por confiança pelo LLM — substitui a string do
    seletor no banco e marca o evento como curado automaticamente.

    Retorna None se não houver evento ou nenhuma sugestão válida para aplicar.
    """
    from .models import ChangeEvent

    try:
        event = ChangeEvent.objects.select_related("selector").get(id=event_id)
    except ChangeEvent.DoesNotExist:
        return None

    if event.resolved:
        return None

    valid = next(
        (v for v in (event.validation_results or []) if v.get("works")),
        None,
    )
    if not valid:
        return None

    sel = event.selector
    old_selector = sel.selector
    new_selector = valid["selector"]

    if new_selector == old_selector:
        return None

    sel.selector = new_selector
    sel.save(update_fields=["selector"])

    event.applied_selector = new_selector
    event.auto_healed = True
    event.resolved = True
    event.resolved_at = timezone.now()
    event.save(update_fields=["applied_selector", "auto_healed", "resolved", "resolved_at"])

    logger.info(
        "Auto-healing: seletor '%s' (id=%d) trocado de %r para %r",
        sel.name, sel.id, old_selector, new_selector,
    )

    return {
        "selector_id": sel.id,
        "selector_name": sel.name,
        "old_selector": old_selector,
        "new_selector": new_selector,
        "extracted": valid.get("extracted"),
    }
