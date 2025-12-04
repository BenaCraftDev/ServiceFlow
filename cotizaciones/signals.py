from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Material


@receiver(post_save, sender=Material)
def resetear_estado_en_cambio_mantenimiento(sender, instance, created, **kwargs):
    """
    Signal que se ejecuta después de guardar un Material.
    
    Si la fecha de mantenimiento cambió, resetea el estado guardado
    para forzar una nueva verificación en el próximo ciclo.
    
    Esto asegura que:
    - Si un material recibe mantenimiento, se reevalúa su estado
    - Si un material vuelve a necesitar mantenimiento, se notifica
    - El sistema siempre refleja el estado actual real
    """
    # Solo procesar si tiene mantenimiento habilitado
    if not instance.requiere_mantenimiento:
        return
    
    # Si es creación, no hacer nada (todavía no hay estado previo)
    if created:
        return
    
    # Verificar si cambió la fecha de mantenimiento comparando con la BD
    try:
        old_instance = Material.objects.get(pk=instance.pk)
        
        # Si la fecha cambió, limpiar notificaciones y resetear estado
        if old_instance.fecha_ultimo_mantenimiento != instance.fecha_ultimo_mantenimiento:
            from .utils_mantenimiento import limpiar_notificaciones_material
            
            # Limpiar notificaciones antiguas
            limpiar_notificaciones_material(instance.codigo)
            
            # El estado se reseteará automáticamente en la próxima verificación
            # porque el hash del estado será diferente
            
    except Material.DoesNotExist:
        pass






