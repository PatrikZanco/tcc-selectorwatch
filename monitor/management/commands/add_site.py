from django.core.management.base import BaseCommand

from monitor.models import Site


class Command(BaseCommand):
    help = "Cadastra um novo site para monitoramento"

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="Nome do site")
        parser.add_argument("--url", required=True, help="URL alvo")
        parser.add_argument(
            "--interval", type=int, default=60, help="Intervalo de verificação em minutos (padrão: 60)"
        )

    def handle(self, *args, **options):
        site, created = Site.objects.get_or_create(
            url=options["url"],
            defaults={
                "name": options["name"],
                "check_interval_minutes": options["interval"],
            },
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS(f"Site '{site.name}' cadastrado (id={site.id})")
            )
        else:
            self.stdout.write(
                self.style.WARNING(f"Site já existe (id={site.id}): {site.name}")
            )
