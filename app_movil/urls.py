from django.urls import path
from . import views

app_name = 'app_movil'

urlpatterns = [
    # Trabajos
    path('mis-trabajos/', views.mis_trabajos_empleado, name='mis_trabajos'),
    path('trabajo/<int:trabajo_id>/actualizar/', views.actualizar_trabajo_empleado, name='actualizar_trabajo'),
    path('trabajo/<int:trabajo_id>/completar/', views.completar_trabajo_empleado, name='completar_trabajo'),
    
    # Notificaciones
    path('notificaciones/', views.obtener_notificaciones_empleado, name='notificaciones'),
    path('notificacion/<int:notificacion_id>/marcar-leida/', views.marcar_notificacion_leida, name='marcar_leida'),
    path('notificaciones/marcar-todas-leidas/', views.marcar_todas_notificaciones_leidas, name='marcar_todas_leidas'),
    
    # Evidencias
    path('trabajo/<int:trabajo_id>/evidencias/', views.obtener_evidencias_trabajo, name='evidencias_trabajo'),
    path('trabajo/<int:trabajo_id>/evidencia/subir/', views.subir_evidencia_trabajo, name='subir_evidencia'),
    
    # Gastos
    path('trabajo/<int:trabajo_id>/gastos/', views.obtener_gastos_trabajo, name='gastos_trabajo'),
    path('trabajo/<int:trabajo_id>/gastos/registrar/', views.registrar_gasto_trabajo, name='registrar_gasto'),
]