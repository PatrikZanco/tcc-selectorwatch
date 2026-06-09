import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Inicia o monitoramento contínuo de todos os seletores ativos"

    def handle(self, *args, **options):
        from monitor.scheduler import build_scheduler

        self.stdout.write(
            self.style.SUCCESS(
                "Iniciando SelectorWatch — monitoramento contínuo. Pressione Ctrl+C para parar."
            )
        )

        scheduler = build_scheduler()

        if not scheduler.get_jobs():
            self.stdout.write(
                self.style.WARNING(
                    "Nenhum seletor ativo encontrado. "
                    "Adicione sites e seletores via 'python manage.py add_site' e 'python manage.py add_selector'."
                )
            )
            return

        self.stdout.write(f"{len(scheduler.get_jobs())} job(s) agendado(s).")

        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            self.stdout.write("\nScheduler encerrado.")
