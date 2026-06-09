from django.core.management.base import BaseCommand, CommandError

from monitor.diagnostics import analyze_failure
from monitor.llm import suggest_selectors


class Command(BaseCommand):
    help = "Diagnostica a falha de um seletor e consulta o LLM para sugestões de correção"

    def add_arguments(self, parser):
        parser.add_argument("selector_id", type=int, help="ID do seletor a diagnosticar")
        parser.add_argument(
            "--no-llm",
            action="store_true",
            help="Executa apenas o diagnóstico de diff, sem consultar o LLM",
        )

    def handle(self, *args, **options):
        sid = options["selector_id"]

        self.stdout.write(f"Analisando diferenças no HTML para seletor id={sid}...")
        report = analyze_failure(sid)

        if not report:
            self.stdout.write(
                self.style.WARNING(
                    "Nenhuma falha recente encontrada ou seletor já está funcionando."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f"Tipo de mudança detectada: {report['change_type']}")
        )

        if options["no_llm"]:
            self.stdout.write("\nDiff (primeiros 1000 chars):")
            self.stdout.write(report["diff_summary"][:1000])
            return

        self.stdout.write("Consultando LLM (Claude) para sugestões de correção...")
        result = suggest_selectors(sid)

        if not result:
            self.stdout.write(self.style.WARNING("Nenhum evento de falha pendente para este seletor."))
            return

        if "error" in result:
            raise CommandError(f"Erro na consulta ao LLM: {result['error']}")

        self.stdout.write(f"\n{self.style.HTTP_INFO('Raciocínio do LLM:')}")
        self.stdout.write(result["reasoning"])

        self.stdout.write(f"\n{self.style.HTTP_INFO('Seletores sugeridos:')}")
        for i, (sug, val) in enumerate(
            zip(result["suggestions"], result["validations"]), 1
        ):
            works = self.style.SUCCESS("FUNCIONA") if val["works"] else self.style.ERROR("NÃO FUNCIONA")
            self.stdout.write(
                f"  {i}. [{sug['confidence'].upper()}] [{works}] {sug['selector']}"
            )
            self.stdout.write(f"     → {sug['explanation']}")
            if val.get("extracted"):
                self.stdout.write(f"     Extraiu: {val['extracted'][0][:80]}")
