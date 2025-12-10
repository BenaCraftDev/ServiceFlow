from django.urls import path
from . import views

app_name = 'notificaciones'

urlpatterns = [
    # Obtener notificaciones para la bandeja (solo no leídas)
    path('obtener/', views.obtener_notificaciones, name='obtener'),
    
    # Marcar como leída
    path('marcar-leida/<int:notificacion_id>/', views.marcar_leida, name='marcar_leida'),
    
    # Marcar todas como leídas
    path('marcar-todas-leidas/', views.marcar_todas_leidas, name='marcar_todas_leidas'),
    
    # Toggle importante (estrella)
    path('toggle-importante/<int:notificacion_id>/', views.toggle_importante, name='toggle_importante'),
    
    # Lista completa de notificaciones
    path('lista/', views.lista_notificaciones, name='lista'),
    
    # Limpiar notificaciones antiguas (opcional - puede ejecutarse con cron)
    path('limpiar/', views.limpiar_notificaciones, name='limpiar'),
]