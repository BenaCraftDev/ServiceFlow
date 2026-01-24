# app_movil/views.py
# API REST para la aplicación móvil

from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db.models import Sum, Q
from cotizaciones.models import TrabajoEmpleado, EvidenciaTrabajo, GastoTrabajo
from home.models import PerfilEmpleado
from notificaciones.models import Notificacion
import json
import base64
from datetime import datetime

from django.contrib.auth import authenticate, login
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def login_movil(request):
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'Método no permitido'
        }, status=405)

    usuario = request.POST.get('username')
    contrasena = request.POST.get('password')

    if not usuario or not contrasena:
        return JsonResponse({
            'success': False,
            'error': 'Usuario y contraseña son obligatorios'
        }, status=400)

    user = authenticate(request, username=usuario, password=contrasena)

    if user is None:
        # ❌ LOGIN INCORRECTO
        return JsonResponse({
            'success': False,
            'error': 'Credenciales incorrectas'
        }, status=401)

    # ✅ LOGIN CORRECTO
    login(request, user)

    return JsonResponse({
        'success': True,
        'usuario': {
            'username': user.username
        }
    }, status=200)



# ==================== TRABAJOS ====================

@csrf_exempt
@login_required
def mis_trabajos_empleado(request):
    try:
        perfil = PerfilEmpleado.objects.get(user=request.user)
        
        # ✅ Si el usuario es admin, ve TODAS las cotizaciones aprobadas
        if perfil.cargo == 'admin':
            trabajos = (
                TrabajoEmpleado.objects
                .select_related('cotizacion', 'item_mano_obra', 'empleado__user')
                .filter(cotizacion__estado='aprobada')
                .order_by('-fecha_inicio')
            )
        else:
            # Si es empleado normal, solo ve las suyas
            trabajos = (
                TrabajoEmpleado.objects
                .select_related('cotizacion', 'item_mano_obra')
                .filter(
                    empleado=perfil,
                    cotizacion__estado='aprobada'
                )
                .order_by('-fecha_inicio')
            )

        data = []

        for trabajo in trabajos:
            cot = trabajo.cotizacion
            
            # Incluir info del empleado asignado (útil para el admin)
            empleado_info = {
                'id': trabajo.empleado.id,
                'nombre': trabajo.empleado.user.get_full_name() or trabajo.empleado.user.username
            }

            data.append({
                'id': trabajo.id,
                'numero_cotizacion': cot.numero if cot else '',
                'cliente': cot.cliente.nombre if cot and cot.cliente else 'N/A',
                'descripcion': (
                    trabajo.item_mano_obra.descripcion
                    if trabajo.item_mano_obra else 'Sin descripción'
                ),
                'estado': trabajo.estado,
                'fecha_inicio': (
                    trabajo.fecha_inicio.strftime('%Y-%m-%d')
                    if trabajo.fecha_inicio else None
                ),
                'fecha_entrega': (
                    cot.fecha_realizacion.strftime('%Y-%m-%d')
                    if cot and cot.fecha_realizacion else None
                ),
                'horas_trabajadas': float(trabajo.horas_trabajadas or 0),
                'observaciones': trabajo.observaciones_empleado or '',
                'tiene_gastos': hasattr(trabajo, 'gastos'),
                'empleado_asignado': empleado_info,  # ✅ NUEVO
                'es_admin': perfil.cargo == 'admin'  # ✅ NUEVO
            })

        return JsonResponse({
            'success': True,
            'total': len(data),
            'trabajos': data,
            'es_admin': perfil.cargo == 'admin'  # ✅ NUEVO
        }, status=200)

    except PerfilEmpleado.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Perfil de empleado no encontrado'
        }, status=404)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)




@login_required
@csrf_exempt
@require_http_methods(["POST"])
def actualizar_trabajo_empleado(request, trabajo_id):
    """API para app móvil - Actualizar trabajo"""
    try:
        perfil_empleado = request.user.perfilempleado
        trabajo = get_object_or_404(TrabajoEmpleado, id=trabajo_id, empleado=perfil_empleado)
        
        data = json.loads(request.body)
        
        # Actualizar observaciones del empleado
        if 'observaciones_empleado' in data:
            trabajo.observaciones_empleado = data['observaciones_empleado']
        
        # Actualizar estado
        if 'estado' in data:
            estado = data['estado']
            trabajo.estado = estado
            
            # Actualizar fechas según estado
            if estado == 'en_progreso' and not trabajo.fecha_inicio:
                trabajo.fecha_inicio = timezone.now()
            elif estado == 'completado' and not trabajo.fecha_fin:
                trabajo.fecha_fin = timezone.now()
        
        # Actualizar horas trabajadas
        if 'horas_trabajadas' in data:
            trabajo.horas_trabajadas = float(data['horas_trabajadas'])
        
        trabajo.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Trabajo actualizado correctamente',
            'trabajo': {
                'id': trabajo.id,
                'estado': trabajo.estado,
                'horas_trabajadas': float(trabajo.horas_trabajadas or 0),
                'observaciones_empleado': trabajo.observaciones_empleado or '',
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def completar_trabajo_empleado(request, trabajo_id):
    """API para app móvil - Completar trabajo"""
    try:
        perfil_empleado = request.user.perfilempleado
        trabajo = get_object_or_404(TrabajoEmpleado, id=trabajo_id, empleado=perfil_empleado)
        
        trabajo.estado = 'completado'
        if not trabajo.fecha_fin:
            trabajo.fecha_fin = timezone.now()
        trabajo.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Trabajo completado exitosamente'
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
        trabajo = get_object_or_404(TrabajoEmpleado, id=trabajo_id, empleado=perfil_empleado)
        
        data = json.loads(request.body)
        imagen_base64 = data.get('imagen')
        descripcion = data.get('descripcion', '')
        
        if not imagen_base64:
            return JsonResponse({
                'success': False,
                'error': 'No se proporcionó imagen'
            }, status=400)
        
        # Decodificar base64
        try:
            # Remover el prefijo data:image/...;base64, si existe
            if 'base64,' in imagen_base64:
                imagen_base64 = imagen_base64.split('base64,')[1]
            
            imagen_data = base64.b64decode(imagen_base64)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Error decodificando imagen: {str(e)}'
            }, status=400)
        
        # Generar nombre de archivo
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'evidencias_trabajos/{trabajo_id}/evidencia_{timestamp}.jpg'
        
        # Guardar archivo
        path = default_storage.save(filename, ContentFile(imagen_data))
        
        # Crear registro de evidencia
        evidencia = EvidenciaTrabajo.objects.create(
            trabajo=trabajo,
            imagen=path,
            descripcion=descripcion
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Evidencia subida correctamente',
            'evidencia': {
                'id': evidencia.id,
                'url': request.build_absolute_uri(evidencia.imagen.url),
                'descripcion': evidencia.descripcion,
                'fecha_subida': evidencia.fecha_subida.isoformat()
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
def obtener_evidencias_trabajo(request, trabajo_id):
    """API para app móvil - Obtener evidencias de un trabajo"""
    try:
        perfil_empleado = request.user.perfilempleado
        
        # ✅ Si es admin, puede ver cualquier trabajo
        if perfil_empleado.cargo == 'admin':
            trabajo = get_object_or_404(TrabajoEmpleado, id=trabajo_id)
        else:
            # Si es empleado normal, solo ve las suyas
            trabajo = get_object_or_404(TrabajoEmpleado, id=trabajo_id, empleado=perfil_empleado)
        
        evidencias = trabajo.evidencias.all().order_by('-fecha_subida')
        
        evidencias_data = []
        for evidencia in evidencias:
            # Calcular días restantes hasta expiración
            dias_restantes = (evidencia.fecha_expiracion - timezone.now()).days
            
            evidencias_data.append({
                'id': evidencia.id,
                'url': request.build_absolute_uri(evidencia.imagen.url),
                'descripcion': evidencia.descripcion or '',
                'fecha_subida': evidencia.fecha_subida.isoformat(),
                'fecha_expiracion': evidencia.fecha_expiracion.isoformat(),
                'dias_restantes': dias_restantes,
                'expira_pronto': dias_restantes <= 30,  # Alerta si quedan ≤30 días
            })
        
        return JsonResponse({
            'success': True,
            'evidencias': evidencias_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
def obtener_todas_evidencias_admin(request):
    """API para admin - Ver TODAS las evidencias del sistema"""
    try:
        perfil = PerfilEmpleado.objects.get(user=request.user)
        
        # Solo admins pueden acceder
        if perfil.cargo != 'admin':
            return JsonResponse({
                'success': False,
                'error': 'Acceso denegado. Solo administradores.'
            }, status=403)
        
        # Obtener todas las evidencias
        from app_movil.models import EvidenciaTrabajo
        
        evidencias = (
            EvidenciaTrabajo.objects
            .select_related('trabajo__empleado__user', 'cotizacion__cliente')
            .order_by('-fecha_subida')
        )
        
        # Filtrar por cotización si se especifica
        cotizacion_id = request.GET.get('cotizacion_id')
        if cotizacion_id:
            evidencias = evidencias.filter(cotizacion_id=cotizacion_id)
        
        evidencias_data = []
        for evidencia in evidencias:
            dias_restantes = (evidencia.fecha_expiracion - timezone.now()).days
            
            evidencias_data.append({
                'id': evidencia.id,
                'url': request.build_absolute_uri(evidencia.imagen.url),
                'descripcion': evidencia.descripcion or '',
                'fecha_subida': evidencia.fecha_subida.isoformat(),
                'fecha_expiracion': evidencia.fecha_expiracion.isoformat(),
                'dias_restantes': dias_restantes,
                'cotizacion': {
                    'id': evidencia.cotizacion.id,
                    'numero': evidencia.cotizacion.numero,
                    'cliente': evidencia.cotizacion.cliente.nombre if evidencia.cotizacion.cliente else 'N/A'
                },
                'empleado': {
                    'id': evidencia.trabajo.empleado.id,
                    'nombre': evidencia.trabajo.empleado.user.get_full_name() or evidencia.trabajo.empleado.user.username
                }
            })
        
        return JsonResponse({
            'success': True,
            'total': len(evidencias_data),
            'evidencias': evidencias_data
        })
        
    except PerfilEmpleado.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Perfil de empleado no encontrado'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
def descargar_evidencia(request, evidencia_id):
    """API para app móvil - Descargar evidencia específica"""
    try:
        perfil_empleado = request.user.perfilempleado  # ← FALTABA ESTO
        
        if perfil_empleado.cargo == 'admin':
            evidencia = get_object_or_404(EvidenciaTrabajo, id=evidencia_id)
        else:
            evidencia = get_object_or_404(
                EvidenciaTrabajo, 
                id=evidencia_id,
                trabajo__empleado=perfil_empleado
            )
        
        # Abrir y leer el archivo
        imagen_file = evidencia.imagen.open('rb')
        response = HttpResponse(imagen_file.read(), content_type='image/jpeg')
        response['Content-Disposition'] = f'attachment; filename="evidencia_{evidencia.id}.jpg"'
        imagen_file.close()
        
        return response
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def eliminar_evidencia(request, evidencia_id):
    """API para admin - Eliminar evidencia manualmente"""
    try:
        perfil = request.user.perfilempleado
        
        # Solo admins pueden eliminar
        if perfil.cargo != 'admin':
            return JsonResponse({
                'success': False,
                'error': 'Acceso denegado. Solo administradores pueden eliminar evidencias.'
            }, status=403)
        
        evidencia = get_object_or_404(EvidenciaTrabajo, id=evidencia_id)
        
        # Guardar info antes de eliminar
        info = {
            'id': evidencia.id,
            'trabajo_id': evidencia.trabajo.id,
            'descripcion': evidencia.descripcion
        }
        
        # Eliminar (el método delete() del modelo se encarga del archivo físico)
        evidencia.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Evidencia eliminada correctamente',
            'evidencia_eliminada': info
        })
        
    except PerfilEmpleado.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Perfil no encontrado'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

# ==================== GASTOS ====================

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def registrar_gasto_trabajo(request, trabajo_id):
    """API para app móvil - Registrar gastos de trabajo"""
    try:
        perfil_empleado = request.user.perfilempleado
        trabajo = get_object_or_404(TrabajoEmpleado, id=trabajo_id, empleado=perfil_empleado)
        
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
            'message': 'Gastos registrados correctamente',
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
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
def obtener_gastos_trabajo(request, trabajo_id):
    """API para app móvil - Obtener gastos de un trabajo"""
    try:
        perfil_empleado = request.user.perfilempleado
        trabajo = get_object_or_404(TrabajoEmpleado, id=trabajo_id, empleado=perfil_empleado)
        
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
            gastos_data = None
        
        return JsonResponse({
            'success': True,
            'gastos': gastos_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


# ==================== NOTIFICACIONES ====================

@login_required
def obtener_notificaciones_empleado(request):
    """API para app móvil - Obtener notificaciones del empleado"""
    try:
        # Obtener notificaciones del usuario
        notificaciones = Notificacion.objects.filter(
            usuario=request.user
        ).order_by('-fecha_creacion')[:50]
        
        notificaciones_data = []
        for notif in notificaciones:
            notificaciones_data.append({
                'id': notif.id,
                'tipo': notif.tipo,
                'titulo': notif.titulo,
                'mensaje': notif.mensaje,
                'leida': notif.leida,
                'url': notif.url or '',
                'fecha': notif.fecha_creacion.strftime('%Y-%m-%d %H:%M:%S'),
            })
        
        # Contar no leídas
        no_leidas = Notificacion.objects.filter(
            usuario=request.user,
            leida=False
        ).count()
        
        return JsonResponse({
            'success': True,
            'notificaciones': notificaciones_data,
            'no_leidas': no_leidas
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def marcar_notificacion_leida(request, notificacion_id):
    """API para app móvil - Marcar notificación como leída"""
    try:
        notificacion = get_object_or_404(
            Notificacion,
            id=notificacion_id,
            usuario=request.user
        )
        
        notificacion.leida = True
        notificacion.save()
        
        # Contar no leídas restantes
        no_leidas = Notificacion.objects.filter(
            usuario=request.user,
            leida=False
        ).count()
        
        return JsonResponse({
            'success': True,
            'message': 'Notificación marcada como leída',
            'no_leidas': no_leidas
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def marcar_todas_notificaciones_leidas(request):
    """API para app móvil - Marcar todas las notificaciones como leídas"""
    try:
        Notificacion.objects.filter(
            usuario=request.user,
            leida=False
        ).update(leida=True)
        
        return JsonResponse({
            'success': True,
            'message': 'Todas las notificaciones marcadas como leídas',
            'no_leidas': 0
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def eliminar_notificacion(request, notificacion_id):
    """API para app móvil - Eliminar notificación"""
    try:
        notificacion = get_object_or_404(
            Notificacion,
            id=notificacion_id,
            usuario=request.user
        )
        
        notificacion.delete()
        
        # Contar no leídas restantes
        no_leidas = Notificacion.objects.filter(
            usuario=request.user,
            leida=False
        ).count()
        
        return JsonResponse({
            'success': True,
            'message': 'Notificación eliminada',
            'no_leidas': no_leidas
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)