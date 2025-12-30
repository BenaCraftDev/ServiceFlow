from django.urls import path
from . import views

app_name = 'notificaciones'

urlpatterns = [
    # Notificaciones
    path('obtener/', views.obtener_notificaciones, name='obtener'),
    path('marcar-leida/<int:notificacion_id>/', views.marcar_leida, name='marcar_leida'),
    path('marcar-todas-leidas/', views.marcar_todas_leidas, name='marcar_todas_leidas'),
    path('toggle-importante/<int:notificacion_id>/', views.toggle_importante, name='toggle_importante'),
    path('lista/', views.lista_notificaciones, name='lista'),
    path('limpiar/', views.limpiar_notificaciones, name='limpiar'),

    # Vista principal del calendario
    path('calendario/', views.vista_calendario, name='calendario'),
    path('api/calendario-eventos/', views.obtener_eventos_calendario, name='calendario_eventos'),
    
    # CRUD de notas
    path('api/nota/crear/', views.crear_nota, name='crear_nota'),
    path('api/nota/<int:nota_id>/', views.obtener_nota, name='obtener_nota'),
    path('api/nota/<int:nota_id>/editar/', views.editar_nota, name='editar_nota'),
    path('api/nota/<int:nota_id>/eliminar/', views.eliminar_nota, name='eliminar_nota'),
    
    # Consultas adicionales
    path('api/notas-rango/', views.obtener_notas_rango, name='notas_rango'),
    path('api/calendario-estadisticas/', views.estadisticas_calendario, name='calendario_estadisticas'),
]