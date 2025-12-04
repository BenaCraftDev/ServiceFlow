from django.urls import path
from . import views

app_name = 'notificaciones'

urlpatterns = [
    path('obtener/', views.obtener_notificaciones, name='obtener'),
    path('marcar-leida/<int:notificacion_id>/', views.marcar_leida, name='marcar_leida'),
    path('marcar-todas-leidas/', views.marcar_todas_leidas, name='marcar_todas_leidas'),
    path('lista/', views.lista_notificaciones, name='lista'),
]