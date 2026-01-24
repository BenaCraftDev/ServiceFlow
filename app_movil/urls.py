# app_movil/urls.py
from django.urls import path
from . import views

app_name = 'app_movil'

urlpatterns = [
    # TRABAJOS
    path('mis-trabajos/', views.mis_trabajos_empleado, name='mis_trabajos'),
    path('trabajo/<int:trabajo_id>/actualizar/', views.actualizar_trabajo_empleado, name='actualizar_trabajo'),
    path('trabajo/<int:trabajo_id>/completar/', views.completar_trabajo_empleado, name='completar_trabajo'),
    
    # EVIDENCIAS
    path('trabajo/<int:trabajo_id>/evidencia/subir/', views.subir_evidencia_trabajo, name='subir_evidencia'),
    path('trabajo/<int:trabajo_id>/evidencias/', views.obtener_evidencias_trabajo, name='obtener_evidencias'),
    path('evidencia/<int:evidencia_id>/descargar/', views.descargar_evidencia, name='descargar_evidencia'),
    path('admin/evidencias/', views.obtener_todas_evidencias_admin, name='admin_evidencias'),
    path('evidencia/<int:evidencia_id>/eliminar/', views.eliminar_evidencia, name='eliminar_evidencia'),
    
    # GASTOS
    path('trabajo/<int:trabajo_id>/gastos/registrar/', views.registrar_gasto_trabajo, name='registrar_gastos'),
    path('trabajo/<int:trabajo_id>/gastos/', views.obtener_gastos_trabajo, name='obtener_gastos'),
    
    # NOTIFICACIONES
    path('notificaciones/', views.obtener_notificaciones_empleado, name='notificaciones'),
    path('notificacion/<int:notificacion_id>/marcar-leida/', views.marcar_notificacion_leida, name='marcar_notificacion_leida'),
    path('notificaciones/marcar-todas-leidas/', views.marcar_todas_notificaciones_leidas, name='marcar_todas_leidas'),
    path('notificacion/<int:notificacion_id>/eliminar/', views.eliminar_notificacion, name='eliminar_notificacion'),
]