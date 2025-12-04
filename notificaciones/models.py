from django.db import models
from django.contrib.auth.models import User

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
    url = models.CharField(max_length=255, blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-fecha_creacion']
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'
    
    def __str__(self):
        return f"{self.titulo} - {self.usuario.username}"