
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand

from monitor.diagnostics import analyze_failure
from monitor.healing import apply_recommendation
from monitor.llm import suggest_selectors
from monitor.models import Selector, Snapshot
from monitor.scraper import run_selector

STRATEGIES = ["rename_class", "change_tag", "remove_class"]


def _mutate(fragment: str, css_selector: str, strategy: str) -> str | None:
    """Aplica uma mutação ao primeiro elemento casado; retorna o novo fragmento."""
    soup = BeautifulSoup(fragment, "lxml")
    try:
        targets = soup.select(css_selector)
    except Exception:
        return None
    if not targets:
        return None
    el = targets[0]

    if strategy == "rename_class":
        classes = el.get("class")
        if not classes:
            return None
        el["class"] = [f"{c}-v2" for c in classes]
    elif strategy == "change_tag":
        el.name = "span" if el.name != "span" else "div"
    elif strategy == "remove_class":
        if not el.get("class"):
            return None
        del el["class"]
    else:
        return None

    return soup.body.decode_contents() if soup.body else str(soup)


class Command(BaseCommand):
    help = "Injeta falhas controladas em seletores estáveis e avalia a recuperação via LLM"

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=0,
                            help="Máximo de injeções (0 = todos os seletores elegíveis)")
        parser.add_argument("--heal", action="store_true",
                            help="Aplica automaticamente a melhor sugestão validada")
        parser.add_argument("--exclude-site", default="produto Amazon",
                            help="Nome de site a excluir (alvo inválido). Padrão: produto Amazon")

    def handle(self, *args, **options):
        limit = options["count"]
        do_heal = options["heal"]
        exclude = options["exclude_site"]

        eligible = (
            Selector.objects.filter(selector_type="css", is_active=True)
            .exclude(site__name=exclude)
            .select_related("site")
        )

        injected = healed = 0
        total_val = ok_val = ev_valid = 0

        for idx, sel in enumerate(eligible):
            if limit and injected >= limit:
                break

            last_ok = sel.snapshots.filter(status="ok").order_by("-checked_at").first()
            if not last_ok or not last_ok.html_fragment:
                continue

            # tenta estratégias em rotação até uma que REALMENTE quebre o seletor
            mutated = None
            used = None
            order = STRATEGIES[idx % len(STRATEGIES):] + STRATEGIES[:idx % len(STRATEGIES)]
            for strat in order:
                cand = _mutate(last_ok.html_fragment, sel.selector, strat)
                if cand and not run_selector(cand, sel.selector, "css"):
                    mutated, used = cand, strat
                    break

            if mutated is None:
                self.stdout.write(self.style.WARNING(
                    f"[SKIP] #{sel.id} {sel.name}: nenhuma mutação quebrou o seletor"))
                continue

            # cria snapshot de falha com o HTML "redesenhado"
            Snapshot.objects.create(
                selector=sel, html_fragment=mutated, extracted_value="",
                status=Snapshot.FAILED, failure_reason=Snapshot.SELECTOR_EMPTY,
            )

            report = analyze_failure(sel.id)
            if not report:
                continue
            res = suggest_selectors(sel.id)
            injected += 1

            n_ok = 0
            if res and "error" not in res:
                for v in res.get("validations", []):
                    total_val += 1
                    if v.get("works"):
                        ok_val += 1
                        n_ok += 1
                if n_ok:
                    ev_valid += 1

            status = self.style.SUCCESS(f"{n_ok} válida(s)") if n_ok else self.style.ERROR("0 válida")
            self.stdout.write(
                f"[{used:13s}] #{sel.id} {sel.site.name} / {sel.name}: "
                f"{report['change_type']} → {status}"
            )

            if do_heal:
                event = sel.change_events.filter(resolved=False).order_by("-detected_at").first()
                if event and apply_recommendation(event.id):
                    healed += 1

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(f"Injeções válidas:      {injected}")
        self.stdout.write(f"Sugestões testadas:    {total_val}")
        if total_val:
            self.stdout.write(f"Precisão do LLM:       {ok_val/total_val*100:.1f}% ({ok_val}/{total_val})")
        if injected:
            self.stdout.write(f"Auto-recuperação:      {ev_valid/injected*100:.1f}% ({ev_valid}/{injected} eventos)")
        if do_heal:
            self.stdout.write(f"Seletores auto-curados: {healed}")
