from django.core.management.base import BaseCommand
from app_movil.models import EvidenciaTrabajo

class Command(BaseCommand):
    help = 'Elimina evidencias de trabajo que han expirado (más de 6 meses)'

    def handle(self, *args, **options):
        count = EvidenciaTrabajo.limpiar_expiradas()
        self.stdout.write(
            self.style.SUCCESS(f'✅ Se eliminaron {count} evidencias expiradas')
        )