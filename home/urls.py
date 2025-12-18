from django.urls import path
from . import views

app_name = 'home'

urlpatterns = [
    path('', views.index, name='index'),
    path('R8M2QKx7f9AL/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('panel-empleados/', views.panel_empleados, name='panel_empleados'),
    path('mi-perfil/', views.mi_perfil, name='mi_perfil'),
    path('mi-configuracion/', views.configuracion_usuario, name='configuracion_usuario'),
    
    # URLs para gestión de usuarios
    path('usuarios/', views.gestion_usuarios, name='gestion_usuarios'),
    path('usuarios/export-csv/', views.export_usuarios_csv, name='export_usuarios_csv'),
    
    # APIs para CRUD de usuarios
    path('usuarios/api/create/', views.crear_usuario_api, name='crear_usuario_api'),
    path('usuarios/api/get/<int:user_id>/', views.obtener_usuario_api, name='obtener_usuario_api'),
    path('usuarios/api/update/<int:user_id>/', views.actualizar_usuario_api, name='actualizar_usuario_api'),
    path('usuarios/api/toggle-status/<int:user_id>/', views.cambiar_estado_usuario_api, name='cambiar_estado_usuario_api'),
    path('usuarios/api/delete/<int:user_id>/', views.eliminar_usuario_api, name='eliminar_usuario_api'),

    # Recuperar Password
    path('recuperar-password/', views.recuperar_password, name='recuperar_password'),
    path('reset-password/<uidb64>/<token>/', views.reset_password, name='reset_password'),
    
    # Solicitud pública (sin login)
    path('solicitar-servicio/', views.solicitar_servicio_publico, name='solicitar_servicio_publico'),
    path('api/tipos-trabajo/', views.obtener_tipos_trabajo_publicos, name='tipos_trabajo_publicos'),
]