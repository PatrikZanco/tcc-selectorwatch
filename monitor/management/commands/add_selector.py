from django.core.management.base import BaseCommand, CommandError

from monitor.models import Selector, Site


class Command(BaseCommand):
    help = "Adiciona um seletor a um site cadastrado"

    def add_arguments(self, parser):
        parser.add_argument("--site-id", type=int, required=True, help="ID do site")
        parser.add_argument("--name", required=True, help="Nome descritivo do seletor")
        parser.add_argument("--selector", required=True, help="String do seletor CSS ou XPath")
        parser.add_argument(
            "--type",
            dest="selector_type",
            choices=["css", "xpath"],
            default="css",
            help="Tipo do seletor (padrão: css)",
        )
        parser.add_argument(
            "--expected",
            dest="expected_type",
            choices=["text", "number", "url", "any"],
            default="any",
            help="Tipo de dado esperado (padrão: any)",
        )
        parser.add_argument(
            "--min-results",
            type=int,
            default=1,
            help="Quantidade mínima de resultados esperados (padrão: 1)",
        )

    def handle(self, *args, **options):
        try:
            site = Site.objects.get(id=options["site_id"])
        except Site.DoesNotExist:
            raise CommandError(f"Site id={options['site_id']} não encontrado.")

        sel = Selector.objects.create(
            site=site,
            name=options["name"],
            selector=options["selector"],
            selector_type=options["selector_type"],
            expected_type=options["expected_type"],
            min_results=options["min_results"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Seletor '{sel.name}' adicionado ao site '{site.name}' (id={sel.id})"
            )
        )
