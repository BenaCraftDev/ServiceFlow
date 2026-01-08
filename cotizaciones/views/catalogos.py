import json
import csv
from decimal import Decimal
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from django.template.loader import render_to_string
from django.conf import settings
from ..models import *
from ..forms import *
from ..forms_empleados import *
from ..forms_prestamos import *
from home.decorators import requiere_admin, requiere_gerente_o_superior
from notificaciones.models import Notificacion
from notificaciones.utils import crear_notificacion
from home.models import PerfilEmpleado
from ..utils_mantenimiento import verificar_mantenimientos_materiales


# === Crud Tipo de Trabajo === 

@login_required
@requiere_gerente_o_superior
def gestionar_tipos_trabajo(request):
    """Vista principal para gestionar tipos de trabajo"""
    
    busqueda = request.GET.get('busqueda', '').strip()
    estado_filtro = request.GET.get('estado', '').strip()
    
    # Query base
    tipos = TipoTrabajo.objects.all()
    
    # Aplicar filtros
    if busqueda:
        tipos = tipos.filter(
            Q(nombre__icontains=busqueda) |
            Q(descripcion__icontains=busqueda)
        )
    
    if estado_filtro == 'activo':
        tipos = tipos.filter(activo=True)
    elif estado_filtro == 'inactivo':
        tipos = tipos.filter(activo=False)
    
    # Estadísticas
    tipos_activos = TipoTrabajo.objects.filter(activo=True).count()
    tipos_inactivos = TipoTrabajo.objects.filter(activo=False).count()
    cotizaciones_count = Cotizacion.objects.count()
    
    # Prefetch para optimizar consultas
    tipos = tipos.prefetch_related('cotizacion_set').order_by('nombre')
    
    context = {
        'tipos': tipos,
        'tipos_activos': tipos_activos,
        'tipos_inactivos': tipos_inactivos,
        'cotizaciones_count': cotizaciones_count,
        'busqueda': busqueda,
        'estado_filtro': estado_filtro,
    }
    
    return render(request, 'cotizaciones/tipos_trabajo/gestionar_tipos_trabajo.html', context)

@login_required
@requiere_gerente_o_superior
def crear_tipo_trabajo(request):
    """Crear nuevo tipo de trabajo"""
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        activo = request.POST.get('activo') == 'on'
        
        if not nombre:
            messages.error(request, 'El nombre del tipo de trabajo es obligatorio')
            return redirect('cotizaciones:gestionar_tipos_trabajo')
        
        # Verificar si ya existe
        if TipoTrabajo.objects.filter(nombre__iexact=nombre).exists():
            messages.error(request, f'Ya existe un tipo de trabajo con el nombre "{nombre}"')
            return redirect('cotizaciones:gestionar_tipos_trabajo')
        
        try:
            tipo = TipoTrabajo.objects.create(
                nombre=nombre,
                descripcion=descripcion if descripcion else None,
                activo=activo
            )
            
            messages.success(request, f'Tipo de trabajo "{tipo.nombre}" creado exitosamente')
            
            # Crear notificación
            crear_notificacion(
                request.user,
                tipo='success',
                titulo='Tipo de Trabajo Creado',
                mensaje=f'Se ha creado el tipo de trabajo "{tipo.nombre}"',
                url=f'/cotizaciones/tipos-trabajo/'
            )
            
        except Exception as e:
            messages.error(request, f'Error al crear el tipo de trabajo: {str(e)}')
        
        return redirect('cotizaciones:gestionar_tipos_trabajo')
    
    return redirect('cotizaciones:gestionar_tipos_trabajo')

@login_required
@requiere_gerente_o_superior
def editar_tipo_trabajo(request, tipo_id):
    """Editar tipo de trabajo existente"""
    tipo = get_object_or_404(TipoTrabajo, id=tipo_id)
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        activo = request.POST.get('activo') == 'on'
        
        if not nombre:
            messages.error(request, 'El nombre del tipo de trabajo es obligatorio')
            return redirect('cotizaciones:gestionar_tipos_trabajo')
        
        # Verificar si el nuevo nombre ya existe (excepto el actual)
        if TipoTrabajo.objects.filter(nombre__iexact=nombre).exclude(id=tipo_id).exists():
            messages.error(request, f'Ya existe otro tipo de trabajo con el nombre "{nombre}"')
            return redirect('cotizaciones:gestionar_tipos_trabajo')
        
        try:
            tipo.nombre = nombre
            tipo.descripcion = descripcion if descripcion else None
            tipo.activo = activo
            tipo.save()
            
            messages.success(request, f'Tipo de trabajo "{tipo.nombre}" actualizado exitosamente')
            
            # Crear notificación
            crear_notificacion(
                request.user,
                tipo='info',
                titulo='Tipo de Trabajo Actualizado',
                mensaje=f'Se ha actualizado el tipo de trabajo "{tipo.nombre}"',
                url=f'/cotizaciones/tipos-trabajo/'
            )
            
        except Exception as e:
            messages.error(request, f'Error al actualizar el tipo de trabajo: {str(e)}')
        
        return redirect('cotizaciones:gestionar_tipos_trabajo')
    
    return redirect('cotizaciones:gestionar_tipos_trabajo')

@login_required
@requiere_gerente_o_superior
def obtener_datos_tipo_trabajo(request, tipo_id):
    """Obtener datos de un tipo de trabajo para edición (JSON)"""
    try:
        tipo = TipoTrabajo.objects.get(id=tipo_id)
        
        data = {
            'success': True,
            'tipo': {
                'id': tipo.id,
                'nombre': tipo.nombre,
                'descripcion': tipo.descripcion or '',
                'activo': tipo.activo,
            }
        }
        return JsonResponse(data)
        
    except TipoTrabajo.DoesNotExist:
        return JsonResponse({
            'success': False,
            'mensaje': 'Tipo de trabajo no encontrado'
        }, status=404)

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def eliminar_tipo_trabajo(request, tipo_id):
    """Eliminar tipo de trabajo"""
    try:
        tipo = TipoTrabajo.objects.get(id=tipo_id)
        
        # Verificar si tiene cotizaciones asociadas
        if tipo.cotizacion_set.exists():
            return JsonResponse({
                'success': False,
                'mensaje': f'No se puede eliminar: el tipo de trabajo "{tipo.nombre}" tiene {tipo.cotizacion_set.count()} cotizaciones asociadas'
            })
        
        nombre = tipo.nombre
        tipo.delete()
        
        messages.success(request, f'Tipo de trabajo "{nombre}" eliminado exitosamente')
        
        # Crear notificación
        crear_notificacion(
            request.user,
            tipo='warning',
            titulo='Tipo de Trabajo Eliminado',
            mensaje=f'Se ha eliminado el tipo de trabajo "{nombre}"',
            url=f'/cotizaciones/tipos-trabajo/'
        )
        
        return JsonResponse({
            'success': True,
            'mensaje': 'Tipo de trabajo eliminado exitosamente'
        })
        
    except TipoTrabajo.DoesNotExist:
        return JsonResponse({
            'success': False,
            'mensaje': 'Tipo de trabajo no encontrado'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'mensaje': f'Error al eliminar: {str(e)}'
        }, status=500)

# === Crud Clientes === 

@login_required
@requiere_gerente_o_superior
def gestionar_clientes(request):
    """Gestión de clientes"""
    clientes = Cliente.objects.all().order_by('nombre')
    
    busqueda = request.GET.get('busqueda', '')
    if busqueda:
        clientes = clientes.filter(
            Q(nombre__icontains=busqueda) |
            Q(rut__icontains=busqueda) |
            Q(email__icontains=busqueda)
        )
    
    paginator = Paginator(clientes, 20)
    page = request.GET.get('page')
    clientes = paginator.get_page(page)
    
    return render(request, 'cotizaciones/gestionar_clientes.html', {
        'clientes': clientes,
        'busqueda': busqueda
    })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def crear_cliente(request):
    """Crear nuevo cliente vía AJAX"""
    try:
        data = json.loads(request.body)
        
        with transaction.atomic():
            # Crear cliente SIN los campos 'atencion' y 'activo'
            cliente = Cliente.objects.create(
                nombre=data.get('nombre'),
                rut=data.get('rut', ''),
                telefono=data.get('telefono', ''),
                email=data.get('email', ''),
                direccion=data.get('direccion', '')
            )
            
            # Crear representantes si existen
            representantes = data.get('representantes', [])
            for idx, nombre_rep in enumerate(representantes):
                if nombre_rep.strip():  # Solo si no está vacío
                    RepresentanteCliente.objects.create(
                        cliente=cliente,
                        nombre=nombre_rep.strip(),
                        orden=idx
                    )
        
        return JsonResponse({
            'success': True,
            'cliente_id': cliente.id,
            'message': 'Cliente creado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["PUT"])
def editar_cliente(request, cliente_id):
    """Editar cliente existente vía AJAX"""
    try:
        cliente = get_object_or_404(Cliente, pk=cliente_id)
        data = json.loads(request.body)
        
        with transaction.atomic():
            # Actualizar datos básicos del cliente
            cliente.nombre = data.get('nombre', cliente.nombre)
            cliente.rut = data.get('rut', cliente.rut)
            cliente.telefono = data.get('telefono', cliente.telefono)
            cliente.email = data.get('email', cliente.email)
            cliente.direccion = data.get('direccion', cliente.direccion)
            cliente.save()
            
            # Actualizar representantes
            # Eliminar los existentes
            cliente.representantes.all().delete()
            
            # Crear los nuevos
            representantes = data.get('representantes', [])
            for idx, nombre_rep in enumerate(representantes):
                if nombre_rep.strip():
                    RepresentanteCliente.objects.create(
                        cliente=cliente,
                        nombre=nombre_rep.strip(),
                        orden=idx
                    )
        
        return JsonResponse({
            'success': True,
            'message': 'Cliente actualizado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["DELETE"])
def eliminar_cliente(request, cliente_id):
    """Eliminar cliente vía AJAX"""
    try:
        cliente = get_object_or_404(Cliente, pk=cliente_id)
        nombre_cliente = cliente.nombre
        
        # Los representantes se eliminarán automáticamente por CASCADE
        cliente.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Cliente {nombre_cliente} eliminado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["GET"])
def obtener_cliente(request, cliente_id):
    """Obtener datos de un cliente vía AJAX"""
    try:
        cliente = get_object_or_404(Cliente, pk=cliente_id)
        
        # Obtener lista de representantes
        representantes = list(cliente.representantes.values_list('nombre', flat=True))
        
        return JsonResponse({
            'success': True,
            'cliente': {
                'id': cliente.id,
                'nombre': cliente.nombre,
                'rut': cliente.rut or '',
                'telefono': cliente.telefono or '',
                'email': cliente.email or '',
                'direccion': cliente.direccion or '',
                'representantes': representantes
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
def obtener_representantes_cliente(request, cliente_id):
    """Obtener representantes de un cliente vía AJAX"""
    try:
        representantes = RepresentanteCliente.objects.filter(
            cliente_id=cliente_id
        ).values('id', 'nombre').order_by('orden', 'nombre')
        
        return JsonResponse({
            'success': True,
            'representantes': list(representantes)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

# === Crud Servicios === 

@login_required
@requiere_gerente_o_superior
def gestionar_servicios(request):
    verificar_mantenimientos_materiales(request)
    """Gestión de servicios base"""
    servicios = ServicioBase.objects.select_related('categoria').order_by('categoria__nombre', 'nombre')
    categorias = CategoriaServicio.objects.filter(activo=True)
    
    categoria_filtro = request.GET.get('categoria', '')
    if categoria_filtro:
        servicios = servicios.filter(categoria_id=categoria_filtro)
    
    # Estadísticas adicionales
    servicios_parametrizables = servicios.filter(es_parametrizable=True).count()
    servicios_activos = servicios.filter(activo=True).count()
    
    return render(request, 'cotizaciones/gestionar_servicios.html', {
        'servicios': servicios,
        'categorias': categorias,
        'categoria_filtro': categoria_filtro,
        'servicios_parametrizables': servicios_parametrizables,
        'servicios_activos': servicios_activos,
    })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def crear_servicio(request):
    """Crear nuevo servicio vía AJAX"""
    try:
        data = json.loads(request.body)
        
        # Obtener la categoría
        categoria = get_object_or_404(CategoriaServicio, pk=data.get('categoria_id'))
        
        servicio = ServicioBase.objects.create(
            categoria=categoria,
            nombre=data.get('nombre'),
            descripcion=data.get('descripcion'),
            precio_base=data.get('precio_base'),
            unidad=data.get('unidad', 'UND'),
            es_parametrizable=data.get('es_parametrizable', False),
            activo=data.get('activo', True)
        )
        
        return JsonResponse({
            'success': True,
            'servicio_id': servicio.id,
            'message': 'Servicio creado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["GET"])
def obtener_servicio(request, servicio_id):
    """Obtener datos de un servicio vía AJAX"""
    try:
        servicio = get_object_or_404(ServicioBase, pk=servicio_id)
        
        return JsonResponse({
            'success': True,
            'servicio': {
                'id': servicio.id,
                'categoria_id': servicio.categoria.id,
                'nombre': servicio.nombre,
                'descripcion': servicio.descripcion,
                'precio_base': float(servicio.precio_base),
                'unidad': servicio.unidad,
                'es_parametrizable': servicio.es_parametrizable,
                'activo': servicio.activo
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["PUT"])
def editar_servicio(request, servicio_id):
    """Editar servicio existente vía AJAX"""
    try:
        servicio = get_object_or_404(ServicioBase, pk=servicio_id)
        data = json.loads(request.body)
        
        # Actualizar categoría si se proporciona
        if data.get('categoria_id'):
            categoria = get_object_or_404(CategoriaServicio, pk=data.get('categoria_id'))
            servicio.categoria = categoria
        
        servicio.nombre = data.get('nombre', servicio.nombre)
        servicio.descripcion = data.get('descripcion', servicio.descripcion)
        servicio.precio_base = data.get('precio_base', servicio.precio_base)
        servicio.unidad = data.get('unidad', servicio.unidad)
        servicio.es_parametrizable = data.get('es_parametrizable', servicio.es_parametrizable)
        servicio.activo = data.get('activo', servicio.activo)
        servicio.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Servicio actualizado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["DELETE"])
def eliminar_servicio(request, servicio_id):
    """Eliminar servicio vía AJAX"""
    try:
        servicio = get_object_or_404(ServicioBase, pk=servicio_id)
        nombre_servicio = servicio.nombre
        servicio.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Servicio {nombre_servicio} eliminado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

# === Crud Parametros === 

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def crear_categoria_servicio(request):
    """Crear nueva categoría de servicio vía AJAX"""
    try:
        data = json.loads(request.body)
        
        categoria = CategoriaServicio.objects.create(
            nombre=data.get('nombre'),
            descripcion=data.get('descripcion', ''),
            orden=data.get('orden', 0),
            activo=True
        )
        
        return JsonResponse({
            'success': True,
            'categoria_id': categoria.id,
            'message': 'Categoría creada exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def crear_parametro_servicio(request, servicio_id):
    """Crear nuevo parámetro para un servicio"""
    try:
        servicio = get_object_or_404(ServicioBase, pk=servicio_id)
        data = json.loads(request.body)
        
        parametro = ParametroServicio.objects.create(
            servicio=servicio,
            nombre=data.get('nombre'),
            tipo=data.get('tipo'),
            requerido=data.get('requerido', True),
            opciones=data.get('opciones', ''),
            valor_por_defecto=data.get('valor_por_defecto', ''),
            orden=data.get('orden', 0)
        )
        
        return JsonResponse({
            'success': True,
            'parametro_id': parametro.id,
            'message': 'Parámetro creado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["PUT"])
def editar_parametro_servicio(request, parametro_id):
    """Editar parámetro existente"""
    try:
        parametro = get_object_or_404(ParametroServicio, pk=parametro_id)
        data = json.loads(request.body)
        
        parametro.nombre = data.get('nombre', parametro.nombre)
        parametro.tipo = data.get('tipo', parametro.tipo)
        parametro.requerido = data.get('requerido', parametro.requerido)
        parametro.opciones = data.get('opciones', parametro.opciones)
        parametro.valor_por_defecto = data.get('valor_por_defecto', parametro.valor_por_defecto)
        parametro.orden = data.get('orden', parametro.orden)
        parametro.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Parámetro actualizado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["DELETE"])
def eliminar_parametro_servicio(request, parametro_id):
    """Eliminar parámetro"""
    try:
        parametro = get_object_or_404(ParametroServicio, pk=parametro_id)
        nombre_parametro = parametro.nombre
        parametro.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Parámetro {nombre_parametro} eliminado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
def gestionar_parametros_servicio(request, servicio_id):
    """Vista para gestionar parámetros de un servicio"""
    servicio = get_object_or_404(ServicioBase, pk=servicio_id)
    parametros = servicio.parametros.all().order_by('orden')
    
    context = {
        'servicio': servicio,
        'parametros': parametros,
        'tipos_parametro': ParametroServicio.TIPO_CHOICES
    }
    
    return render(request, 'cotizaciones/gestionar_parametros.html', context)

# === Crud Categorias Empleados ===

@login_required
@requiere_gerente_o_superior
def gestionar_categorias_empleados(request):
    """Gestión de categorías de empleados"""
    try:
        # Importar modelos
        from ..models import CategoriaEmpleado, EmpleadoCategoria
        
        # Obtener categorías con prefetch para optimizar consultas
        categorias = CategoriaEmpleado.objects.prefetch_related('empleados').all().order_by('orden', 'nombre')
        
        # Obtener empleados disponibles para asignación
        empleados_disponibles = PerfilEmpleado.objects.filter(
            activo=True
        ).exclude(
            cargo='admin'  
        ).select_related('user').order_by('user__first_name')
        
        # Obtener asignaciones actuales para mostrar en la tabla
        asignaciones_actuales = EmpleadoCategoria.objects.filter(
            activo=True
        ).select_related('empleado__user', 'categoria').order_by('categoria__orden', 'empleado__user__first_name')
        
        context = {
            'categorias': categorias,
            'empleados_disponibles': empleados_disponibles,
            'asignaciones_actuales': asignaciones_actuales,
            'total_empleados': empleados_disponibles.count()
        }
        
        return render(request, 'cotizaciones/gestionar_categorias_empleados.html', context)
        
    except ImportError:
        messages.error(request, 'Los modelos de categorías de empleados no están configurados. Ejecuta las migraciones.')
        return redirect('home:panel_empleados')
    except Exception as e:
        messages.error(request, f'Error al cargar categorías: {str(e)}')
        return redirect('home:panel_empleados')

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def crear_categoria_empleado(request):
    """Crear nueva categoría de empleado"""
    try:
        data = json.loads(request.body)
        
        categoria = CategoriaEmpleado.objects.create(
            nombre=data.get('nombre'),
            descripcion=data.get('descripcion', ''),
            orden=data.get('orden', 0),
            activo=data.get('activo', True)
        )
        
        return JsonResponse({
            'success': True,
            'categoria_id': categoria.id,
            'message': 'Categoría creada exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["PUT"])
def editar_categoria_empleado(request, categoria_id):
    """Editar categoría de empleado"""
    try:
        categoria = get_object_or_404(CategoriaEmpleado, pk=categoria_id)
        data = json.loads(request.body)
        
        categoria.nombre = data.get('nombre', categoria.nombre)
        categoria.descripcion = data.get('descripcion', categoria.descripcion)
        categoria.orden = data.get('orden', categoria.orden)
        categoria.activo = data.get('activo', categoria.activo)
        categoria.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Categoría actualizada exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["DELETE"])
def eliminar_categoria_empleado(request, categoria_id):
    """Eliminar categoría de empleado"""
    try:
        categoria = get_object_or_404(CategoriaEmpleado, pk=categoria_id)
        nombre_categoria = categoria.nombre
        categoria.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Categoría {nombre_categoria} eliminada exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def asignar_empleado_categoria(request):
    """Asignar empleado a categoría"""
    try:
        data = json.loads(request.body)
        
        empleado = get_object_or_404(PerfilEmpleado, pk=data.get('empleado_id'))
        categoria = get_object_or_404(CategoriaEmpleado, pk=data.get('categoria_id'))
        
        # Verificar si ya existe la asignación
        asignacion_existente = EmpleadoCategoria.objects.filter(
            empleado=empleado,
            categoria=categoria
        ).first()
        
        if asignacion_existente:
            return JsonResponse({
                'success': False,
                'error': 'El empleado ya está asignado a esta categoría'
            })
        
        asignacion = EmpleadoCategoria.objects.create(
            empleado=empleado,
            categoria=categoria,
            activo=True
        )
        
        return JsonResponse({
            'success': True,
            'asignacion_id': asignacion.id,
            'message': f'{empleado.nombre_completo} asignado a {categoria.nombre}'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["DELETE"])
def eliminar_empleado_categoria(request, asignacion_id):
    """Eliminar asignación de empleado a categoría"""
    try:
        asignacion = get_object_or_404(EmpleadoCategoria, pk=asignacion_id)
        empleado_nombre = asignacion.empleado.nombre_completo
        categoria_nombre = asignacion.categoria.nombre
        asignacion.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'{empleado_nombre} removido de {categoria_nombre}'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
def obtener_empleados_categoria(request, categoria_id):
    """Obtener empleados de una categoría específica"""
    empleados = PerfilEmpleado.objects.filter(
        activo=True,
        cargo='empleado',
        categorias_trabajo__categoria_id=categoria_id,
        categorias_trabajo__activo=True
    ).select_related('user').distinct()
    
    empleados_data = []
    for empleado in empleados:
        empleados_data.append({
            'id': empleado.id,
            'nombre': empleado.nombre_completo,
            'telefono': empleado.telefono or '',
        })
    
    return JsonResponse(empleados_data, safe=False)

