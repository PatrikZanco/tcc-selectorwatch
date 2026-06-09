from django.core.management.base import BaseCommand

from monitor.scraper import check_all_selectors, check_selector


class Command(BaseCommand):
    help = "Verifica seletores manualmente (sem scheduler)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--id",
            dest="selector_id",
            type=int,
            default=None,
            help="ID do seletor específico (omita para verificar todos)",
        )

    def handle(self, *args, **options):
        sid = options["selector_id"]

        if sid:
            results = [check_selector(sid)]
        else:
            self.stdout.write("Verificando todos os seletores ativos...")
            results = check_all_selectors()

        for r in results:
            status = r.get("status", "?")
            if status == "ok":
                symbol = self.style.SUCCESS("[ OK ]")
            elif status == "failed":
                symbol = self.style.ERROR("[FALHA]")
            else:
                symbol = self.style.WARNING(f"[{status.upper()}]")

            line = f"{symbol} #{r.get('selector_id', '?')} {r.get('selector_name', '')} ({r.get('site_name', '')}): {r.get('message', status)}"
            self.stdout.write(line)

            if status == "ok" and r.get("values"):
                self.stdout.write(f"         Extraído: {r['values'][0][:100]}")
