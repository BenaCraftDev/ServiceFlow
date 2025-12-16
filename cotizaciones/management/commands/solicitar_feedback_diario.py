from django.core.management.base import BaseCommand
from cotizaciones.views import solicitar_feedback_automatico

class Command(BaseCommand):
    help = 'Solicita feedback a clientes 7 días después de finalizar'

    def handle(self, *args, **kwargs):
        self.stdout.write('🔄 Iniciando solicitud de feedback...')
        
        resultados = solicitar_feedback_automatico()
        
        self.stdout.write(self.style.SUCCESS(
            f'✅ Completado: {resultados["enviados"]} enviados, '
            f'{resultados["fallidos"]} fallidos'
        ))
        
        if resultados['errores']:
            for error in resultados['errores']:
                self.stdout.write(self.style.ERROR(
                    f'❌ {error["cotizacion"]}: {error["error"]}'
                ))

# EJECUTAR CON:
# python manage.py solicitar_feedback_diario

# AGREGAR AL CRONTAB (ejecutar diario a las 9 AM):
# 0 9 * * * cd /path/to/project && python manage.py solicitar_feedback_diario