from django.core.management.base import BaseCommand
from notificaciones.models import Notificacion

class Command(BaseCommand):
    help = 'Elimina notificaciones leídas de más de 6 meses (excepto importantes)'

    def handle(self, *args, **options):
        cantidad = Notificacion.limpiar_notificaciones_antiguas()
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ Se eliminaron {cantidad} notificaciones antiguas')
        )
        
        # Estadísticas
        total = Notificacion.objects.count()
        no_leidas = Notificacion.objects.filter(leida=False).count()
        importantes = Notificacion.objects.filter(importante=True).count()
        
        self.stdout.write(f'📊 Estadísticas actuales:')
        self.stdout.write(f'   - Total: {total} notificaciones')
        self.stdout.write(f'   - No leídas: {no_leidas}')
        self.stdout.write(f'   - Importantes: {importantes}')






