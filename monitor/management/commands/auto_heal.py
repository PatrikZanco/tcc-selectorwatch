from django.core.management.base import BaseCommand

from monitor.healing import apply_recommendation
from monitor.models import ChangeEvent


class Command(BaseCommand):
    help = "Aplica a melhor sugestão validada aos eventos de falha pendentes (self-healing)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--id",
            dest="event_id",
            type=int,
            default=None,
            help="ID do evento específico (omita para curar todos os pendentes)",
        )

    def handle(self, *args, **options):
        eid = options["event_id"]

        if eid:
            events = ChangeEvent.objects.filter(id=eid)
        else:
            events = ChangeEvent.objects.filter(
                resolved=False, validation_results__isnull=False
            ).order_by("detected_at")

        healed = skipped = 0
        for ev in events:
            result = apply_recommendation(ev.id)
            if result:
                healed += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[CURADO] #{ev.id} {result['selector_name']}: "
                        f"{result['old_selector']!r} → {result['new_selector']!r} "
                        f"(extraiu {result['extracted']})"
                    )
                )
            else:
                skipped += 1

        self.stdout.write(
            f"\n{healed} evento(s) curado(s), {skipped} sem sugestão válida para aplicar."
        )
