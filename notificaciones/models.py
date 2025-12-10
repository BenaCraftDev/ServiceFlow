from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

class Notificacion(models.Model):
    TIPO_CHOICES = [
        ('info', 'Información'),
        ('success', 'Éxito'),
        ('warning', 'Advertencia'),
        ('danger', 'Urgente'),
    ]
    
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notificaciones')
    titulo = models.CharField(max_length=100)
    mensaje = models.TextField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='info')
    leida = models.BooleanField(default=False)
    importante = models.BooleanField(default=False)  # NUEVO: Para marcar como importante
    fecha_leida = models.DateTimeField(null=True, blank=True)  # NUEVO: Fecha en que se leyó
    url = models.CharField(max_length=255, blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-fecha_creacion']
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'
    
    def __str__(self):
        return f"{self.titulo} - {self.usuario.username}"
    
    def marcar_como_leida(self):
        """Marca la notificación como leída y guarda la fecha"""
        if not self.leida:
            self.leida = True
            self.fecha_leida = timezone.now()
            self.save()
    
    def toggle_importante(self):
        """Alterna el estado de importante"""
        self.importante = not self.importante
        self.save()
        return self.importante
    
    def debe_eliminarse(self):
        """
        Verifica si la notificación debe ser eliminada automáticamente.
        Se elimina si:
        - Está leída
        - No está marcada como importante
        - Han pasado 6 meses desde que se leyó
        """
        if self.importante or not self.leida or not self.fecha_leida:
            return False
        
        seis_meses_atras = timezone.now() - timedelta(days=180)
        return self.fecha_leida < seis_meses_atras
    
    @classmethod
    def limpiar_notificaciones_antiguas(cls):
        """
        Elimina automáticamente las notificaciones antiguas que cumplen los criterios.
        Este método puede llamarse periódicamente desde un cron job o tarea programada.
        """
        seis_meses_atras = timezone.now() - timedelta(days=180)
        
        notificaciones_a_eliminar = cls.objects.filter(
            leida=True,
            importante=False,
            fecha_leida__lt=seis_meses_atras
        )
        
        cantidad = notificaciones_a_eliminar.count()
        notificaciones_a_eliminar.delete()
        
        return cantidad