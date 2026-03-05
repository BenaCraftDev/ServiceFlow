# app_movil/cloudinary_monitor.py
import cloudinary
import cloudinary.api
import logging
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

LIMITE_GB = 25.0
UMBRAL_NOTIFICAR = 0.80   # 80% → notificar
UMBRAL_LIMPIAR   = 0.90   # 90% → limpiar


def obtener_uso_cloudinary():
    """Obtiene el uso actual de almacenamiento en Cloudinary."""
    try:
        resultado = cloudinary.api.usage()
        bytes_usados = resultado.get('storage', {}).get('usage', 0)
        gb_usados = bytes_usados / (1024 ** 3)
        porcentaje = gb_usados / LIMITE_GB
        return {
            'gb_usados': round(gb_usados, 3),
            'gb_limite': LIMITE_GB,
            'porcentaje': round(porcentaje, 4),
            'porcentaje_display': f"{porcentaje * 100:.1f}%"
        }
    except Exception as e:
        logger.error(f"❌ Error obteniendo uso de Cloudinary: {e}")
        return None


def notificar_almacenamiento_lleno(uso):
    """Crea notificación para todos los admins sobre almacenamiento alto."""
    try:
        from django.contrib.auth.models import User
        from notificaciones.models import Notificacion
        from home.models import PerfilEmpleado

        admins = PerfilEmpleado.objects.filter(cargo='admin').select_related('user')

        for perfil in admins:
            # Evitar notificaciones duplicadas del mismo día
            hoy = timezone.now().date()
            ya_notificado = Notificacion.objects.filter(
                usuario=perfil.user,
                titulo__icontains='Almacenamiento Cloudinary',
                fecha_creacion__date=hoy
            ).exists()

            if not ya_notificado:
                Notificacion.objects.create(
                    usuario=perfil.user,
                    titulo=f"⚠️ Almacenamiento Cloudinary al {uso['porcentaje_display']}",
                    mensaje=(
                        f"El almacenamiento de evidencias está al {uso['porcentaje_display']} "
                        f"({uso['gb_usados']} GB de {uso['gb_limite']} GB). "
                        f"Se recomienda revisar y eliminar evidencias antiguas."
                    ),
                    tipo='warning',
                )
        logger.info(f"✅ Notificación de almacenamiento enviada a {admins.count()} admins")
    except Exception as e:
        logger.error(f"❌ Error creando notificación: {e}")


def limpiar_evidencias_antiguas():
    """
    Elimina evidencias de tareas completadas hace más de 30 días.
    Se llama cuando el almacenamiento supera el 90%.
    Retorna la cantidad de evidencias eliminadas.
    """
    try:
        from cotizaciones.models import EvidenciaTrabajo, TrabajoEmpleado

        fecha_limite = timezone.now() - timedelta(days=30)

        # Trabajos completados hace más de 30 días
        trabajos_viejos = TrabajoEmpleado.objects.filter(
            estado='completado',
            fecha_fin__lt=fecha_limite
        ).values_list('id', flat=True)

        evidencias = EvidenciaTrabajo.objects.filter(
            trabajo_id__in=trabajos_viejos
        ).order_by('fecha_subida')

        total = evidencias.count()
        if total == 0:
            logger.info("ℹ️ No hay evidencias antiguas para eliminar")
            return 0

        eliminadas = 0
        for evidencia in evidencias:
            try:
                if evidencia.imagen:
                    public_id = evidencia.imagen.public_id
                    cloudinary.uploader.destroy(public_id, resource_type='image')
                evidencia.delete()
                eliminadas += 1
            except Exception as e:
                logger.warning(f"⚠️ Error eliminando evidencia {evidencia.id}: {e}")

        logger.info(f"✅ {eliminadas}/{total} evidencias antiguas eliminadas")
        return eliminadas

    except Exception as e:
        logger.error(f"❌ Error en limpieza automática: {e}")
        return 0


def verificar_y_gestionar_almacenamiento():
    """
    Función principal. Verificar uso y actuar según umbrales.
    Llamar desde un endpoint o tarea programada.
    """
    uso = obtener_uso_cloudinary()
    if not uso:
        return {'error': 'No se pudo obtener uso de Cloudinary'}

    resultado = {
        'uso': uso,
        'notificacion_enviada': False,
        'limpieza_ejecutada': False,
        'evidencias_eliminadas': 0,
    }

    logger.info(f"📊 Cloudinary: {uso['porcentaje_display']} usado ({uso['gb_usados']} GB)")

    # 90%+ → limpiar automáticamente
    if uso['porcentaje'] >= UMBRAL_LIMPIAR:
        logger.warning(f"🚨 Almacenamiento al {uso['porcentaje_display']} - Iniciando limpieza")
        eliminadas = limpiar_evidencias_antiguas()
        resultado['limpieza_ejecutada'] = True
        resultado['evidencias_eliminadas'] = eliminadas
        notificar_almacenamiento_lleno(uso)
        resultado['notificacion_enviada'] = True

    # 80%+ → solo notificar
    elif uso['porcentaje'] >= UMBRAL_NOTIFICAR:
        logger.warning(f"⚠️ Almacenamiento al {uso['porcentaje_display']} - Notificando")
        notificar_almacenamiento_lleno(uso)
        resultado['notificacion_enviada'] = True

    return resultado