import logging
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler

logger = logging.getLogger(__name__)

_scheduler: BlockingScheduler | None = None


def _run_pipeline(selector_id: int) -> None:
    from .diagnostics import analyze_failure
    from .llm import suggest_selectors
    from .models import ChangeEvent, Selector
    from .scraper import check_selector

    logger.info("Verificando seletor id=%d", selector_id)
    result = check_selector(selector_id)
    status = result.get("status")
    failure_type = result.get("failure_type", "")
    logger.info("  → %s: %s", status, result.get("message", ""))

    if status == "failed":
        if failure_type in ("http_error", "network_error"):
            logger.warning("  Erro de rede/HTTP — diagnóstico e LLM ignorados (sem HTML para analisar).")
        else:
            logger.info("  Falha detectada — analisando diferenças no HTML...")
            report = analyze_failure(selector_id)
            if report:
                logger.info("  Tipo de mudança: %s — consultando LLM...", report["change_type"])
                llm_result = suggest_selectors(selector_id)
                if llm_result and "error" not in llm_result:
                    n_sugs = len(llm_result.get("suggestions", []))
                    logger.info("  LLM gerou %d sugestão(ões).", n_sugs)
                    _try_auto_heal(selector_id)
                else:
                    logger.warning("  LLM retornou erro: %s", llm_result)

    anomaly = result.get("anomaly")
    if anomaly:
        direction = "alta" if anomaly["change_pct"] > 0 else "baixa"
        logger.warning(
            "  Anomalia de valor: %s → %s (%+.1f%% de %s)",
            anomaly["previous"], anomaly["current"], anomaly["change_pct"], direction,
        )
        try:
            sel = Selector.objects.get(id=selector_id)
            ChangeEvent.objects.create(
                selector=sel,
                change_type="anomalia_de_valor",
                diff_report=(
                    f"Valor anterior: {anomaly['previous']} ({anomaly['previous_num']})\n"
                    f"Valor atual:    {anomaly['current']} ({anomaly['current_num']})\n"
                    f"Variação:       {anomaly['change_pct']:+.1f}%\n"
                    f"Threshold:      {sel.anomaly_threshold}%"
                ),
            )
        except Exception as exc:
            logger.error("  Erro ao criar ChangeEvent de anomalia: %s", exc)


def _try_auto_heal(selector_id: int) -> None:
    """Aplica a melhor sugestão validada, se AUTO_HEAL estiver ativo."""
    from django.conf import settings

    if not settings.AUTO_HEAL:
        return

    from .healing import apply_recommendation
    from .models import ChangeEvent

    event = (
        ChangeEvent.objects.filter(selector_id=selector_id, resolved=False)
        .order_by("-detected_at")
        .first()
    )
    if not event:
        return

    healed = apply_recommendation(event.id)
    if healed:
        logger.info(
            "  Auto-healing aplicado: %r → %r",
            healed["old_selector"], healed["new_selector"],
        )
    else:
        logger.info("  Auto-healing: nenhuma sugestão válida para aplicar.")


def _sync_selectors() -> None:
    """Detecta seletores novos/removidos e atualiza os jobs dinamicamente."""
    from .models import Selector

    active = Selector.objects.filter(is_active=True).select_related("site")
    active_ids = set()

    for sel in active:
        job_id = f"selector_{sel.id}"
        active_ids.add(job_id)
        if _scheduler.get_job(job_id) is None:
            # Seletor novo: agenda e dispara imediatamente
            interval = sel.site.check_interval_minutes
            _scheduler.add_job(
                _run_pipeline,
                trigger="interval",
                minutes=interval,
                args=[sel.id],
                id=job_id,
                max_instances=1,
                replace_existing=True,
                next_run_time=datetime.now(timezone.utc),  # roda agora
            )
            logger.info(
                "Novo job: seletor '%s' (%s) a cada %d min — primeira execução imediata",
                sel.name, sel.site.name, interval,
            )

    # Remove jobs de seletores desativados/deletados
    for job in _scheduler.get_jobs():
        if job.id.startswith("selector_") and job.id not in active_ids:
            job.remove()
            logger.info("Job removido: %s (seletor inativo ou deletado)", job.id)


def build_scheduler() -> BlockingScheduler:
    global _scheduler
    _scheduler = BlockingScheduler(timezone="America/Sao_Paulo")

    # Job de sincronização: detecta seletores novos a cada 30 segundos
    _scheduler.add_job(
        _sync_selectors,
        trigger="interval",
        seconds=30,
        id="sync_selectors",
        max_instances=1,
        next_run_time=datetime.now(timezone.utc),  # roda imediatamente ao iniciar
    )

    return _scheduler
