from django.urls import path
from . import views

app_name = 'cotizaciones'

urlpatterns = [

    # Dashboard y listados principales
    path('', views.dashboard_cotizaciones, name='dashboard'),
    path('lista/', views.lista_cotizaciones, name='lista'),
    
    # CRUD de cotizaciones
    path('crear/', views.crear_cotizacion, name='crear'),
    path('<int:pk>/', views.detalle_cotizacion, name='detalle'),
    path('<int:pk>/editar/', views.editar_cotizacion, name='editar'),
    path('<int:pk>/pdf/', views.generar_pdf_cotizacion, name='generar_pdf'),
    path('<int:pk>/estado/', views.cambiar_estado_cotizacion, name='cambiar_estado'),
    
    # Gestión de items de cotización (AJAX)
    path('<int:cotizacion_pk>/item-servicio/', views.agregar_item_servicio, name='agregar_item_servicio'),
    path('<int:cotizacion_pk>/item-material/', views.agregar_item_material, name='agregar_item_material'),
    path('<int:cotizacion_pk>/item-mano-obra/', views.agregar_item_mano_obra, name='agregar_item_mano_obra'),
    path('<int:cotizacion_pk>/gastos-traslado/', views.actualizar_gastos_traslado, name='actualizar_gastos_traslado'),
    
    # Eliminar items (AJAX)
    path('<int:cotizacion_pk>/item-servicio/<int:item_pk>/eliminar/', views.eliminar_item_servicio, name='eliminar_item_servicio'),
    path('<int:cotizacion_pk>/item-material/<int:item_pk>/eliminar/', views.eliminar_item_material, name='eliminar_item_material'),
    path('<int:cotizacion_pk>/item-mano-obra/<int:item_pk>/eliminar/', views.eliminar_item_mano_obra, name='eliminar_item_mano_obra'),
    
    # APIs para formularios dinámicos
    path('api/categoria/<int:categoria_id>/servicios/', views.obtener_servicios_categoria, name='servicios_categoria'),
    path('api/servicio/<int:servicio_id>/parametros/', views.obtener_parametros_servicio, name='parametros_servicio'),
    
    # Plantillas
    path('<int:cotizacion_pk>/plantilla/<int:plantilla_pk>/aplicar/', views.aplicar_plantilla, name='aplicar_plantilla'),
    
    # Gestión de catálogos
    path('clientes/', views.gestionar_clientes, name='gestionar_clientes'),
    path('servicios/', views.gestionar_servicios, name='gestionar_servicios'),
    path('materiales/', views.gestionar_materiales, name='gestionar_materiales'),
    path('<int:pk>/eliminar/', views.eliminar_cotizacion, name='eliminar_cotizacion'),
    path('<int:pk>/completar/', views.completar_cotizacion, name='completar_cotizacion'),

    #Crud Clientes
    path('cliente/crear/', views.crear_cliente, name='crear_cliente'),
    path('cliente/<int:cliente_id>/editar/', views.editar_cliente, name='editar_cliente'),
    path('cliente/<int:cliente_id>/eliminar/', views.eliminar_cliente, name='eliminar_cliente'),  
    path('cliente/<int:cliente_id>/', views.obtener_cliente, name='obtener_cliente'),
    path('cliente/<int:cliente_id>/representantes/', views.obtener_representantes_cliente, name='obtener_representantes_cliente'),

    # Crud servicios
    path('servicio/crear/', views.crear_servicio, name='crear_servicio'),
    path('servicio/<int:servicio_id>/', views.obtener_servicio, name='obtener_servicio'),
    path('servicio/<int:servicio_id>/editar/', views.editar_servicio, name='editar_servicio'),
    path('servicio/<int:servicio_id>/eliminar/', views.eliminar_servicio, name='eliminar_servicio'),
    # Gestión de categorías
    path('categoria-servicio/crear/', views.crear_categoria_servicio, name='crear_categoria_servicio'),

    # Parámetros de servicios
    path('servicio/<int:servicio_id>/parametros/', views.obtener_parametros_servicio, name='obtener_parametros_servicio'),
    path('servicio/<int:servicio_id>/parametros/gestionar/', views.gestionar_parametros_servicio, name='gestionar_parametros_servicio'),
    path('servicio/<int:servicio_id>/parametro/crear/', views.crear_parametro_servicio, name='crear_parametro_servicio'),
    path('parametro/<int:parametro_id>/editar/', views.editar_parametro_servicio, name='editar_parametro_servicio'),
    path('parametro/<int:parametro_id>/eliminar/', views.eliminar_parametro_servicio, name='eliminar_parametro_servicio'),

    # Crud materiales
    path('material/crear/', views.crear_material, name='crear_material'),
    path('material/<int:material_id>/', views.obtener_material, name='obtener_material'),
    path('material/<int:material_id>/editar/', views.editar_material, name='editar_material'),
    path('material/<int:material_id>/eliminar/', views.eliminar_material, name='eliminar_material'),

    # Funciones adicionales de materiales
    path('material/validar-codigo/', views.validar_codigo_material, name='validar_codigo_material'),
    path('material/importar/', views.importar_materiales_csv, name='importar_materiales_csv'),
    
    # Mantenimiento de materiales
    path('material/<int:material_id>/registrar-mantenimiento/', views.registrar_mantenimiento_material, name='registrar_mantenimiento_material'),
    path('api/alertas-mantenimiento/', views.obtener_alertas_mantenimiento, name='obtener_alertas_mantenimiento'),

    # Gestión de categorías de empleados
    path('categorias-empleados/', views.gestionar_categorias_empleados, name='gestionar_categorias_empleados'),
    path('categoria-empleado/crear/', views.crear_categoria_empleado, name='crear_categoria_empleado'),
    path('categoria-empleado/<int:categoria_id>/editar/', views.editar_categoria_empleado, name='editar_categoria_empleado'),
    path('categoria-empleado/<int:categoria_id>/eliminar/', views.eliminar_categoria_empleado, name='eliminar_categoria_empleado'),
    
    # Asignación de empleados a categorías
    path('empleado-categoria/asignar/', views.asignar_empleado_categoria, name='asignar_empleado_categoria'),
    path('empleado-categoria/<int:asignacion_id>/eliminar/', views.eliminar_empleado_categoria, name='eliminar_empleado_categoria'),
    
    # AJAX para empleados por categoría
    path('api/categoria-empleado/<int:categoria_id>/empleados/', views.obtener_empleados_categoria, name='empleados_categoria'),
    
    # Asignar empleados a mano de obra
    path('<int:cotizacion_pk>/item-mano-obra/<int:item_pk>/empleados/', views.gestionar_empleados_mano_obra, name='gestionar_empleados_mano_obra'),
    path('<int:cotizacion_pk>/item-mano-obra/<int:item_pk>/empleado/agregar/', views.agregar_empleado_mano_obra, name='agregar_empleado_mano_obra'),
    path('<int:cotizacion_pk>/item-mano-obra/<int:item_pk>/empleado/<int:empleado_id>/eliminar/', views.eliminar_empleado_mano_obra, name='eliminar_empleado_mano_obra'),
    
    # Vista de empleados - Sus trabajos
    path('mis-trabajos/', views.mis_trabajos_empleado, name='mis_trabajos_empleado'),
    path('trabajo/<int:trabajo_id>/actualizar/', views.actualizar_trabajo_empleado, name='actualizar_trabajo_empleado'),
    path('trabajo/<int:trabajo_id>/completar/', views.completar_trabajo_empleado, name='completar_trabajo_empleado'),

    # Resportes
    path('reportes/', views.reportes_dashboard, name='reportes_dashboard'),
    path('api/datos-dashboard/', views.datos_dashboard_reportes, name='datos_dashboard_reportes'),
    path('api/cotizaciones-mes/', views.obtener_cotizaciones_mes, name='obtener_cotizaciones_mes'),
    
    # URLs de exportación
    path('clientes/exportar/', views.exportar_clientes, name='exportar_clientes'),
    path('servicios/exportar/', views.exportar_servicios, name='exportar_servicios'),
    path('materiales/exportar/', views.exportar_materiales, name='exportar_materiales'),
    path('cotizaciones/exportar/', views.exportar_cotizaciones, name='exportar_cotizaciones'),

    # Sistema de Email
    path('<int:pk>/enviar-email/', views.enviar_cotizacion_email, name='enviar_email'),
    path('<int:pk>/reenviar/', views.reenviar_cotizacion, name='reenviar'),
    
    # URLs públicas (sin login) para cliente
    path('ver-publica/<str:token>/', views.ver_cotizacion_publica, name='ver_publica'),
    path('responder/<str:token>/<str:accion>/', views.responder_cotizacion, name='responder'),

    # Nuevos endpoints para reportes interactivos
    path('api/cotizaciones-por-estado/', views.obtener_cotizaciones_por_estado, name='obtener_cotizaciones_por_estado'),
    path('api/cotizaciones-por-cliente/', views.obtener_cotizaciones_por_cliente, name='obtener_cotizaciones_por_cliente'),
    path('api/cotizaciones-por-servicio/', views.obtener_cotizaciones_por_servicio, name='obtener_cotizaciones_por_servicio'),

    # Seguimiento de trabajos
    path('seguimiento-trabajos/', views.seguimiento_trabajos_aprobados, name='seguimiento_trabajos'),
    path('seguimiento-trabajos/<int:cotizacion_id>/trabajo/<int:trabajo_id>/detalle/', views.obtener_detalle_trabajo, name='detalle_trabajo'),
    path('seguimiento-trabajos/exportar/', views.exportar_trabajos, name='exportar_trabajos'),

    # Sistema de Préstamos
    path('prestamos/', views.lista_prestamos, name='lista_prestamos'),
    path('prestamos/crear/', views.crear_prestamo, name='crear_prestamo'),
    path('prestamos/<int:pk>/datos/', views.obtener_datos_prestamo, name='obtener_datos_prestamo'),
    path('prestamos/<int:pk>/editar/', views.editar_prestamo, name='editar_prestamo'),
    path('prestamos/<int:pk>/eliminar/', views.eliminar_prestamo, name='eliminar_prestamo'),
    path('api/material/verificar-disponible/', views.verificar_material_disponible, name='verificar_material_disponible'),

]