from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from cotizaciones.models import TrabajoEmpleado, EvidenciaTrabajo, GastoTrabajo
from home.models import PerfilEmpleado
from notificaciones.models import Notificacion
from django.utils import timezone
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import json
import base64

# ==================== TRABAJOS ====================

@login_required
@csrf_exempt
def mis_trabajos_empleado(request):
    """API para app móvil - Obtener trabajos del empleado"""
    try:
        perfil_empleado = request.user.perfilempleado
    except PerfilEmpleado.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'No tienes un perfil de empleado asignado'
        }, status=403)
    
    # Obtener trabajos del empleado
    trabajos = TrabajoEmpleado.objects.filter(empleado=perfil_empleado).select_related(
        'cotizacion',
        'cotizacion__cliente',
        'item_mano_obra'
    ).prefetch_related('evidencias').order_by('-fecha_inicio')
    
    # Calcular estadísticas
    from django.db.models import Sum
    trabajos_pendientes = trabajos.filter(estado='pendiente').count()
    trabajos_en_progreso = trabajos.filter(estado='en_progreso').count()
    trabajos_completados = trabajos.filter(estado='completado').count()
    total_horas_trabajadas = trabajos.aggregate(total=Sum('horas_trabajadas'))['total'] or 0
    
    # Construir lista de trabajos
    trabajos_data = []
    for trabajo in trabajos:
        cotizacion = trabajo.cotizacion
        item_mano_obra = trabajo.item_mano_obra
        
        # Descripción legible
        descripcion = item_mano_obra.descripcion if item_mano_obra else 'Sin descripción'
        
        # Contar evidencias y gastos
        num_evidencias = trabajo.evidencias.count()
        tiene_gastos = hasattr(trabajo, 'gastos')
        
        trabajos_data.append({
            'id': trabajo.id,
            'numero_cotizacion': cotizacion.numero,
            'cliente': cotizacion.get_nombre_cliente() if hasattr(cotizacion, 'get_nombre_cliente') else (cotizacion.cliente.nombre if cotizacion.cliente else 'Cliente eliminado'),
            'descripcion': descripcion,
            'estado': trabajo.estado,
            'fecha_inicio': trabajo.fecha_inicio.strftime('%Y-%m-%d') if trabajo.fecha_inicio else None,
            'fecha_entrega': cotizacion.fecha_vencimiento.strftime('%Y-%m-%d') if cotizacion.fecha_vencimiento else None,
            'horas_trabajadas': float(trabajo.horas_trabajadas or 0),
            'observaciones': trabajo.observaciones_empleado or '',
            'num_evidencias': num_evidencias,
            'tiene_gastos': tiene_gastos,
        })
    
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
@csrf_exempt
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
@csrf_exempt
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

# ==================== NOTIFICACIONES ====================

@login_required
@csrf_exempt
def obtener_notificaciones_empleado(request):
    """API para app móvil - Obtener notificaciones"""
    try:
        notificaciones = Notificacion.objects.filter(
            usuario=request.user
        ).order_by('-fecha_creacion')[:50]
        
        notificaciones_data = []
        for notif in notificaciones:
            notificaciones_data.append({
                'id': notif.id,
                'titulo': notif.titulo,
                'mensaje': notif.mensaje,
                'tipo': notif.tipo,
                'leida': notif.leida,
                'importante': notif.importante,
                'url': notif.url or '',
                'fecha_creacion': notif.fecha_creacion.isoformat(),
            })
        
        no_leidas = notificaciones.filter(leida=False).count()
        
        return JsonResponse({
            'success': True,
            'notificaciones': notificaciones_data,
            'no_leidas': no_leidas
        })
    except Exception as e:
        import traceback
        print(f"❌ Error en notificaciones: {str(e)}")
        print(traceback.format_exc())
        
        return JsonResponse({
            'success': False,
            'error': str(e),
            'notificaciones': [],
            'no_leidas': 0
        }, status=500)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def marcar_notificacion_leida(request, notificacion_id):
    """API para app móvil - Marcar notificación como leída"""
    try:
        notificacion = Notificacion.objects.get(
            id=notificacion_id,
            usuario=request.user
        )
        notificacion.marcar_como_leida()
        
        return JsonResponse({
            'success': True,
            'message': 'Notificación marcada como leída'
        })
    except Notificacion.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Notificación no encontrada'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def marcar_todas_notificaciones_leidas(request):
    """API para app móvil - Marcar todas como leídas"""
    try:
        ahora = timezone.now()
        notificaciones = Notificacion.objects.filter(
            usuario=request.user,
            leida=False
        )
        
        for notif in notificaciones:
            notif.leida = True
            notif.fecha_leida = ahora
            notif.save()
        
        updated = notificaciones.count()
        
        return JsonResponse({
            'success': True,
            'message': f'{updated} notificaciones marcadas'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

# ==================== EVIDENCIAS ====================

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def subir_evidencia_trabajo(request, trabajo_id):
    """API para app móvil - Subir foto de evidencia"""
    try:
        perfil_empleado = request.user.perfilempleado
        trabajo = TrabajoEmpleado.objects.get(pk=trabajo_id, empleado=perfil_empleado)
        
        data = json.loads(request.body)
        imagen_base64 = data.get('imagen')
        descripcion = data.get('descripcion', '')
        
        if not imagen_base64:
            return JsonResponse({'success': False, 'error': 'No se envió imagen'}, status=400)
        
        # Decodificar base64
        try:
            if 'base64,' in imagen_base64:
                imagen_base64 = imagen_base64.split('base64,')[1]
            
            imagen_data = base64.b64decode(imagen_base64)
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Error decodificando: {str(e)}'}, status=400)
        
        # Guardar archivo
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f'evidencias_trabajos/{timezone.now().year}/{timezone.now().month:02d}/{timezone.now().day:02d}/trabajo_{trabajo_id}_{timestamp}.jpg'
        path = default_storage.save(filename, ContentFile(imagen_data))
        
        # Crear registro en BD
        evidencia = EvidenciaTrabajo.objects.create(
            trabajo=trabajo,
            imagen=path,
            descripcion=descripcion
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Evidencia subida exitosamente',
            'evidencia': {
                'id': evidencia.id,
                'url': evidencia.imagen.url if evidencia.imagen else '',
                'descripcion': evidencia.descripcion,
                'fecha_subida': evidencia.fecha_subida.isoformat()
            }
        })
        
    except TrabajoEmpleado.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Trabajo no encontrado'}, status=404)
    except Exception as e:
        import traceback
        print(f"❌ Error subiendo evidencia: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@csrf_exempt
def obtener_evidencias_trabajo(request, trabajo_id):
    """API para app móvil - Obtener evidencias de un trabajo"""
    try:
        perfil_empleado = request.user.perfilempleado
        trabajo = TrabajoEmpleado.objects.get(pk=trabajo_id, empleado=perfil_empleado)
        
        evidencias = EvidenciaTrabajo.objects.filter(trabajo=trabajo).order_by('-fecha_subida')
        
        evidencias_data = [{
            'id': e.id,
            'url': e.imagen.url if e.imagen else '',
            'descripcion': e.descripcion or '',
            'fecha_subida': e.fecha_subida.isoformat()
        } for e in evidencias]
        
        return JsonResponse({
            'success': True,
            'evidencias': evidencias_data
        })
        
    except TrabajoEmpleado.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Trabajo no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# ==================== GASTOS ====================

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def registrar_gasto_trabajo(request, trabajo_id):
    """API para app móvil - Registrar gastos de trabajo"""
    try:
        perfil_empleado = request.user.perfilempleado
        trabajo = TrabajoEmpleado.objects.get(pk=trabajo_id, empleado=perfil_empleado)
        
        data = json.loads(request.body)
        
        # Obtener o crear gastos
        gastos, created = GastoTrabajo.objects.get_or_create(trabajo=trabajo)
        
        # Actualizar campos
        gastos.materiales = float(data.get('materiales', 0))
        gastos.materiales_detalle = data.get('materiales_detalle', '')
        gastos.transporte = float(data.get('transporte', 0))
        gastos.transporte_detalle = data.get('transporte_detalle', '')
        gastos.otros = float(data.get('otros', 0))
        gastos.otros_detalle = data.get('otros_detalle', '')
        
        gastos.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Gastos registrados exitosamente',
            'gastos': {
                'materiales': float(gastos.materiales),
                'materiales_detalle': gastos.materiales_detalle,
                'transporte': float(gastos.transporte),
                'transporte_detalle': gastos.transporte_detalle,
                'otros': float(gastos.otros),
                'otros_detalle': gastos.otros_detalle,
                'total': float(gastos.total)
            }
        })
        
    except TrabajoEmpleado.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Trabajo no encontrado'}, status=404)
    except Exception as e:
        import traceback
        print(f"❌ Error registrando gastos: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@csrf_exempt
def obtener_gastos_trabajo(request, trabajo_id):
    """API para app móvil - Obtener gastos de un trabajo"""
    try:
        perfil_empleado = request.user.perfilempleado
        trabajo = TrabajoEmpleado.objects.get(pk=trabajo_id, empleado=perfil_empleado)
        
        try:
            gastos = trabajo.gastos
            gastos_data = {
                'materiales': float(gastos.materiales),
                'materiales_detalle': gastos.materiales_detalle or '',
                'transporte': float(gastos.transporte),
                'transporte_detalle': gastos.transporte_detalle or '',
                'otros': float(gastos.otros),
                'otros_detalle': gastos.otros_detalle or '',
                'total': float(gastos.total)
            }
        except GastoTrabajo.DoesNotExist:
            gastos_data = {
                'materiales': 0,
                'materiales_detalle': '',
                'transporte': 0,
                'transporte_detalle': '',
                'otros': 0,
                'otros_detalle': '',
                'total': 0
            }
        
        return JsonResponse({
            'success': True,
            'gastos': gastos_data
        })
        
    except TrabajoEmpleado.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Trabajo no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)