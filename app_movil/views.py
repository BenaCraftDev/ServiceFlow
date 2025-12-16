from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from cotizaciones.models import TrabajoEmpleado
from home.models import PerfilEmpleado
from django.utils import timezone
import json

@login_required
def mis_trabajos_empleado(request):
    """API para app móvil - Obtener trabajos del empleado"""
    try:
        perfil_empleado = request.user.perfilempleado
    except PerfilEmpleado.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'No tienes un perfil de empleado asignado'
        }, status=403)
    
    trabajos = TrabajoEmpleado.objects.filter(empleado=perfil_empleado).order_by('-id')
    
    from django.db.models import Sum
    trabajos_pendientes = trabajos.filter(estado='pendiente').count()
    trabajos_en_progreso = trabajos.filter(estado='en_progreso').count()
    trabajos_completados = trabajos.filter(estado='completado').count()
    total_horas_trabajadas = trabajos.aggregate(total=Sum('horas_trabajadas'))['total'] or 0
    
    trabajos_data = []
    for trabajo in trabajos:
        try:
            trabajos_data.append({
                'id': trabajo.id,
                'numero_cotizacion': trabajo.item_mano_obra.cotizacion.numero_cotizacion if trabajo.item_mano_obra else 'N/A',
                'cliente': trabajo.item_mano_obra.cotizacion.cliente.nombre if trabajo.item_mano_obra else 'N/A',
                'descripcion': str(trabajo.item_mano_obra) if trabajo.item_mano_obra else 'Sin descripción',
                'estado': trabajo.estado,
                'fecha_asignacion': trabajo.fecha_asignacion.strftime('%Y-%m-%d') if trabajo.fecha_asignacion else None,
                'fecha_entrega': trabajo.item_mano_obra.cotizacion.fecha_estimada.strftime('%Y-%m-%d') if trabajo.item_mano_obra and trabajo.item_mano_obra.cotizacion.fecha_estimada else None,
                'horas_trabajadas': float(trabajo.horas_trabajadas or 0),
                'observaciones': trabajo.observaciones_empleado or '',
            })
        except:
            continue
    
    return JsonResponse({
        'success': True,
        'trabajos': trabajos_data,
        'estadisticas': {
            'pendientes': trabajos_pendientes,
            'en_progreso': trabajos_en_progreso,
            'completados': trabajos_completados,
            'horas_totales': float(total_horas_trabajadas)
        }
    })

@login_required
@require_http_methods(["POST"])
def actualizar_trabajo_empleado(request, trabajo_id):
    """API para app móvil - Actualizar trabajo"""
    try:
        perfil_empleado = request.user.perfilempleado
        trabajo = TrabajoEmpleado.objects.get(pk=trabajo_id, empleado=perfil_empleado)
        
        data = json.loads(request.body)
        trabajo.estado = data.get('estado', trabajo.estado)
        trabajo.horas_trabajadas = data.get('horas_trabajadas', trabajo.horas_trabajadas)
        trabajo.observaciones_empleado = data.get('observaciones_empleado', trabajo.observaciones_empleado)
        
        if data.get('estado') == 'en_progreso' and not trabajo.fecha_inicio:
            trabajo.fecha_inicio = timezone.now()
        elif data.get('estado') == 'completado' and not trabajo.fecha_fin:
            trabajo.fecha_fin = timezone.now()
        
        trabajo.save()
        return JsonResponse({'success': True, 'message': 'Trabajo actualizado exitosamente'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@require_http_methods(["POST"])
def completar_trabajo_empleado(request, trabajo_id):
    """API para app móvil - Completar trabajo"""
    try:
        perfil_empleado = request.user.perfilempleado
        trabajo = TrabajoEmpleado.objects.get(pk=trabajo_id, empleado=perfil_empleado)
        
        trabajo.estado = 'completado'
        if not trabajo.fecha_fin:
            trabajo.fecha_fin = timezone.now()
        trabajo.save()
        
        return JsonResponse({'success': True, 'message': 'Trabajo completado exitosamente'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)