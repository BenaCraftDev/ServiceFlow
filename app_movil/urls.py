from django.urls import path
from . import views

app_name = 'app_movil'

urlpatterns = [
    path('mis-trabajos/', views.mis_trabajos_empleado, name='mis_trabajos'),
    path('trabajo/<int:trabajo_id>/actualizar/', views.actualizar_trabajo_empleado, name='actualizar_trabajo'),
    path('trabajo/<int:trabajo_id>/completar/', views.completar_trabajo_empleado, name='completar_trabajo'),
]