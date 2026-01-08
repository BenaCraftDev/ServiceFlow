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

@login_required
def mis_trabajos_empleado(request):
    """Vista de trabajos para empleados corregida"""
    try:
        perfil_empleado = request.user.perfilempleado
    except PerfilEmpleado.DoesNotExist:
        messages.error(request, 'No tienes un perfil de empleado asignado')
        return redirect('home:panel_empleados')
    
    # Obtener trabajos del empleado - SOLO DE COTIZACIONES APROBADAS
    trabajos = TrabajoEmpleado.objects.filter(
        empleado=perfil_empleado,
        cotizacion__estado='aprobada'
    ).select_related('cotizacion', 'item_mano_obra', 'empleado').order_by('-fecha_inicio')
    
    # Filtros
    estado_filtro = request.GET.get('estado', '')
    if estado_filtro and trabajos.exists():
        trabajos = trabajos.filter(estado=estado_filtro)
    
    # Estadísticas
    from django.db.models import Sum
    stats = {
        'pendientes': trabajos.filter(estado='pendiente').count(),
        'en_progreso': trabajos.filter(estado='en_progreso').count(),
        'completados': trabajos.filter(estado='completado').count(),
        'total_horas': trabajos.aggregate(total=Sum('horas_trabajadas'))['total'] or 0
    }
    
    context = {
        'trabajos': trabajos,
        'stats': stats,
        'estado_filtro': estado_filtro,
        'estados_choices': [
            ('pendiente', 'Pendiente'),
            ('en_progreso', 'En Progreso'),
            ('completado', 'Completado'),
            ('suspendido', 'Suspendido'),
        ],
        'perfil_empleado': perfil_empleado,
        'model_exists': True,
    }

    # Detectar si la petición es desde la app móvil o requiere JSON
    if request.headers.get('Accept') == 'application/json' or request.GET.get('format') == 'json':
        trabajos_data = []
        
        for trabajo in trabajos:
            # IMPORTANTE: Convertimos Decimal a float para que el JSON lo entienda
            h_estimadas = float(trabajo.horas_estimadas or 0)
            h_trabajadas = float(trabajo.horas_trabajadas or 0)
            
            # Si por alguna razón la BD tiene 0 pero el item tiene horas, rescatamos el dato
            if h_estimadas <= 0 and trabajo.item_mano_obra:
                h_estimadas = float(trabajo.item_mano_obra.horas or 0)

            trabajos_data.append({
                'id': trabajo.id,
                'numero_cotizacion': trabajo.cotizacion.numero_cotizacion,
                'cliente': trabajo.cotizacion.cliente.nombre,
                'descripcion': trabajo.item_mano_obra.categoria_empleado.nombre if trabajo.item_mano_obra else 'Sin descripción',
                'estado': trabajo.estado,
                'horas_estimadas': h_estimadas,  # <--- DATO CORREGIDO
                'horas_trabajadas': h_trabajadas,
                'fecha_asignacion': trabajo.fecha_asignacion.strftime('%Y-%m-%d') if trabajo.fecha_asignacion else None,
                'fecha_entrega': trabajo.cotizacion.fecha_estimada.strftime('%Y-%m-%d') if trabajo.cotizacion.fecha_estimada else None,
                'observaciones': trabajo.observaciones_empleado or '',
            })
        
        return JsonResponse({
            'success': True,
            'trabajos': trabajos_data,
            'estadisticas': stats
        })
    
    return render(request, 'cotizaciones/mis_trabajos_empleado.html', context)

@login_required
@require_http_methods(["POST"])
def actualizar_trabajo_empleado(request, trabajo_id):
    """Actualizar estado y detalles de trabajo por empleado"""
    try:
        perfil_empleado = request.user.perfilempleado
        trabajo = get_object_or_404(
            TrabajoEmpleado,
            pk=trabajo_id,
            empleado=perfil_empleado
        )
        
        data = json.loads(request.body)
        
        # Actualizar campos permitidos
        trabajo.estado = data.get('estado', trabajo.estado)
        trabajo.horas_trabajadas = data.get('horas_trabajadas', trabajo.horas_trabajadas)
        trabajo.observaciones_empleado = data.get('observaciones_empleado', trabajo.observaciones_empleado)
        
        # Manejar fechas de inicio y fin
        if data.get('estado') == 'en_progreso' and not trabajo.fecha_inicio:
            trabajo.fecha_inicio = timezone.now()
        elif data.get('estado') == 'completado':
            if not trabajo.fecha_fin:
                trabajo.fecha_fin = timezone.now()
        
        trabajo.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Trabajo actualizado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@require_http_methods(["POST"])
def completar_trabajo_empleado(request, trabajo_id):
    """Marcar trabajo como completado"""
    try:
        perfil_empleado = request.user.perfilempleado
        trabajo = get_object_or_404(
            TrabajoEmpleado,
            pk=trabajo_id,
            empleado=perfil_empleado
        )
        
        trabajo.estado = 'completado'
        trabajo.fecha_fin = timezone.now()
        trabajo.save()
        
        # También actualizar la asignación en ItemManoObraEmpleado
        asignacion = ItemManoObraEmpleado.objects.filter(
            item_mano_obra=trabajo.item_mano_obra,
            empleado=perfil_empleado
        ).first()
        
        if asignacion:
            asignacion.marcar_completado()
        
        return JsonResponse({
            'success': True,
            'message': 'Trabajo marcado como completado'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

# === Crud Mano de Obra ===

@login_required
@requiere_gerente_o_superior
def gestionar_empleados_mano_obra(request, cotizacion_pk, item_pk):
    """Gestionar empleados asignados a un item de mano de obra"""
    cotizacion = get_object_or_404(Cotizacion, pk=cotizacion_pk)
    item_mano_obra = get_object_or_404(ItemManoObra, pk=item_pk, cotizacion=cotizacion)
    
    # Obtener empleados ya asignados
    empleados_asignados = ItemManoObraEmpleado.objects.filter(
        item_mano_obra=item_mano_obra
    ).select_related('empleado__user')
    
    # Calcular estadísticas
    total_horas_asignadas = sum(asignacion.horas_asignadas for asignacion in empleados_asignados)
    empleados_completados = empleados_asignados.filter(completado=True).count()
    
    # Obtener categorías disponibles para filtrar empleados
    try:
        categorias_empleados = CategoriaEmpleado.objects.filter(activo=True)
    except:
        categorias_empleados = []
    
    context = {
        'cotizacion': cotizacion,
        'item_mano_obra': item_mano_obra,
        'empleados_asignados': empleados_asignados,
        'categorias_empleados': categorias_empleados,
        'total_horas_asignadas': total_horas_asignadas,
        'empleados_completados': empleados_completados,
    }
    
    return render(request, 'cotizaciones/gestionar_empleados_mano_obra.html', context)

@login_required
@requiere_gerente_o_superior
@require_http_methods(["GET"])
def obtener_categoria_empleado(request, categoria_id):
    """Obtener datos de una categoría de empleado para edición"""
    try:
        categoria = get_object_or_404(CategoriaEmpleado, pk=categoria_id)
        
        return JsonResponse({
            'success': True,
            'categoria': {
                'id': categoria.id,
                'nombre': categoria.nombre,
                'descripcion': categoria.descripcion,
                'orden': categoria.orden,
                'activo': categoria.activo
            }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=404)

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def agregar_empleado_mano_obra(request, cotizacion_pk, item_pk):
    """Agregar empleado a item de mano de obra"""
    try:
        cotizacion = get_object_or_404(Cotizacion, pk=cotizacion_pk)
        item_mano_obra = get_object_or_404(ItemManoObra, pk=item_pk, cotizacion=cotizacion)
        
        data = json.loads(request.body)
        empleado_id = data.get('empleado_id')
        
        # ASEGURAR QUE LAS HORAS SEAN NUMÉRICAS:
        # Intentamos obtener horas_asignadas, si no viene o es vacío, usamos las del item_mano_obra
        try:
            horas_asignadas = float(data.get('horas_asignadas', 0))
            if horas_asignadas <= 0:
                horas_asignadas = float(item_mano_obra.horas or 0)
        except (ValueError, TypeError):
            horas_asignadas = float(item_mano_obra.horas or 0)

        observaciones = data.get('observaciones', '')
        empleado = get_object_or_404(PerfilEmpleado, pk=empleado_id)
        
        valor_final = horas_asignadas if horas_asignadas > 0 else float(item_mano_obra.horas or 1.0)

        # Verificar si ya está asignado
        if ItemManoObraEmpleado.objects.filter(item_mano_obra=item_mano_obra, empleado=empleado).exists():
            return JsonResponse({
                'success': False,
                'error': 'El empleado ya está asignado a este trabajo'
            })
        
        with transaction.atomic():
            # 1. Crear asignación técnica
            asignacion = ItemManoObraEmpleado.objects.create(
                item_mano_obra=item_mano_obra,
                empleado=empleado,
                horas_asignadas=horas_asignadas,
                observaciones=observaciones
            )
            
            # 2. Crear registro en TrabajoEmpleado para la vista del empleado
            # FORZAMOS el guardado de horas_estimadas aquí
            trabajo = TrabajoEmpleado.objects.create(
                empleado=empleado,
                cotizacion=cotizacion,
                item_mano_obra=item_mano_obra,
                horas_estimadas=valor_final, # <--- Este es el campo clave
                observaciones_empleado=observaciones,
                defaults={
                    'estado': 'pendiente',
                    'horas_estimadas': item_mano_obra.horas,  # <--- ESTA ES LA LÍNEA QUE FALTA
                }
            ) 
        
        return JsonResponse({
            'success': True,
            'asignacion_id': asignacion.id,
            'horas_guardadas': horas_asignadas, # Enviamos esto para debugear en el navegador
            'message': f'{empleado.nombre_completo} asignado con {horas_asignadas} hrs.'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@requiere_gerente_o_superior
@require_http_methods(["DELETE"])
def eliminar_empleado_mano_obra(request, cotizacion_pk, item_pk, empleado_id):
    """Eliminar empleado de item de mano de obra"""
    try:
        cotizacion = get_object_or_404(Cotizacion, pk=cotizacion_pk)
        item_mano_obra = get_object_or_404(ItemManoObra, pk=item_pk, cotizacion=cotizacion)
        empleado = get_object_or_404(PerfilEmpleado, pk=empleado_id)
        
        # Eliminar asignación
        asignacion = get_object_or_404(
            ItemManoObraEmpleado,
            item_mano_obra=item_mano_obra,
            empleado=empleado
        )
        
        # También eliminar de TrabajoEmpleado
        trabajo_empleado = TrabajoEmpleado.objects.filter(
            empleado=empleado,
            item_mano_obra=item_mano_obra
        ).first()
        
        with transaction.atomic():
            asignacion.delete()
            if trabajo_empleado:
                trabajo_empleado.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'{empleado.nombre_completo} removido del trabajo'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


