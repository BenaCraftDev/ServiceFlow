from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Sum, Q
from django.contrib.auth import authenticate
from cotizaciones.models import TrabajoEmpleado, EvidenciaTrabajo, GastoTrabajo
from home.models import PerfilEmpleado
from notificaciones.models import Notificacion
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from functools import wraps
import json
import base64
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# ============================================================
# HELPER: Autenticación JWT para vistas basadas en funciones
# ============================================================
def jwt_required(view_func):
    """Decorador que reemplaza @jwt_required usando JWT"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        auth = JWTAuthentication()
        try:
            result = auth.authenticate(request)
            if result is None:
                return JsonResponse({'success': False, 'error': 'Token requerido'}, status=401)
            request.user, _ = result
        except (InvalidToken, TokenError) as e:
            return JsonResponse({'success': False, 'error': 'Token inválido o expirado'}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper




# ==================== TRABAJOS ====================

@csrf_exempt
@jwt_required
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




@jwt_required
@csrf_exempt
@require_http_methods(["POST"])
def actualizar_trabajo_empleado(request, trabajo_id):
    """API para app móvil - Actualizar trabajo"""
    try:
        perfil_empleado = request.user.perfilempleado
        
        # ✅ Admin puede actualizar cualquier trabajo
        if perfil_empleado.cargo == 'admin':
            trabajo = get_object_or_404(TrabajoEmpleado, id=trabajo_id)
        else:
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


@jwt_required
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
@jwt_required
@csrf_exempt
@require_http_methods(["POST"])
def subir_evidencia_trabajo(request, trabajo_id):
    """API para app móvil - Subir foto de evidencia a Cloudinary"""
    import logging
    import cloudinary.uploader
    logger = logging.getLogger(__name__)
    
    try:
        perfil_empleado = request.user.perfilempleado
        trabajo = get_object_or_404(TrabajoEmpleado, id=trabajo_id, empleado=perfil_empleado)
        
        logger.info(f"📸 Subiendo evidencia para trabajo {trabajo_id}")
        
        data = json.loads(request.body)
        imagen_base64 = data.get('imagen')
        descripcion = data.get('descripcion', '')
        
        if not imagen_base64:
            return JsonResponse({'success': False, 'error': 'No se proporcionó imagen'}, status=400)
        
        # Decodificar base64
        try:
            if 'base64,' in imagen_base64:
                imagen_base64 = imagen_base64.split('base64,')[1]
            imagen_data = base64.b64decode(imagen_base64)
            logger.info(f"✅ Imagen decodificada: {len(imagen_data)} bytes")
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Error decodificando imagen: {str(e)}'}, status=400)
        
        # Subir directamente a Cloudinary
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        public_id = f'evidencias_trabajos/{trabajo_id}/evidencia_{timestamp}'
        
        resultado = cloudinary.uploader.upload(
            imagen_data,
            public_id=public_id,
            resource_type='image',
            format='jpg'
        )
        
        imagen_url = resultado.get('secure_url')
        cloudinary_public_id = resultado.get('public_id')
        logger.info(f"✅ Subida a Cloudinary OK: {imagen_url}")
        
        # Crear registro en BD con el public_id de Cloudinary
        evidencia = EvidenciaTrabajo.objects.create(
            trabajo=trabajo,
            imagen=cloudinary_public_id,
            descripcion=descripcion
        )
        
        logger.info(f"✅ Evidencia creada ID: {evidencia.id}")
        
        # Verificar almacenamiento después de cada subida (en background)
        try:
            from app_movil.cloudinary_monitor import verificar_y_gestionar_almacenamiento
            verificar_y_gestionar_almacenamiento()
        except Exception as e:
            logger.warning(f"⚠️ Error verificando almacenamiento: {e}")
        
        return JsonResponse({
            'success': True,
            'message': 'Evidencia subida correctamente',
            'evidencia': {
                'id': evidencia.id,
                'url': imagen_url,
                'descripcion': evidencia.descripcion,
                'fecha_subida': evidencia.fecha_subida.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Error general: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@jwt_required
def obtener_evidencias_trabajo(request, trabajo_id):
    """API para app móvil - Obtener evidencias de un trabajo desde Cloudinary"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        perfil_empleado = request.user.perfilempleado
        
        if perfil_empleado.cargo == 'admin':
            trabajo = get_object_or_404(TrabajoEmpleado, id=trabajo_id)
        else:
            trabajo = get_object_or_404(TrabajoEmpleado, id=trabajo_id, empleado=perfil_empleado)
        
        evidencias = trabajo.evidencias.all().order_by('-fecha_subida')
        
        logger.info(f"🔍 Obteniendo evidencias - Trabajo ID: {trabajo_id}")
        logger.info(f"🔍 Total evidencias: {evidencias.count()}")
        
        evidencias_data = []
        for evidencia in evidencias:
            # URL directa de Cloudinary (no necesita build_absolute_uri)
            url = evidencia.imagen.url if evidencia.imagen else None
            
            logger.info(f"  ✅ Evidencia ID: {evidencia.id}")
            logger.info(f"  🔗 URL Cloudinary: {url}")
            
            evidencias_data.append({
                'id': evidencia.id,
                'url': url,  # URL directa de Cloudinary
                'descripcion': evidencia.descripcion or '',
                'fecha_subida': evidencia.fecha_subida.isoformat()
            })
        
        return JsonResponse({
            'success': True,
            'evidencias': evidencias_data
        })
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo evidencias: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@jwt_required
def obtener_todas_evidencias_admin(request):
    """API para admin - Ver TODAS las evidencias del sistema"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        perfil = PerfilEmpleado.objects.get(user=request.user)
        
        # Solo admins pueden acceder
        if perfil.cargo != 'admin':
            return JsonResponse({
                'success': False,
                'error': 'Acceso denegado. Solo administradores.'
            }, status=403)
        
        # Obtener todas las evidencias
        evidencias = (
            EvidenciaTrabajo.objects
            .select_related('trabajo__empleado__user', 'trabajo__cotizacion__cliente')
            .order_by('-fecha_subida')
        )
        
        # Filtrar por trabajo si se especifica
        trabajo_id = request.GET.get('trabajo_id')
        if trabajo_id:
            evidencias = evidencias.filter(trabajo_id=trabajo_id)
        
        logger.info(f"🔍 Admin obteniendo {evidencias.count()} evidencias")
        
        evidencias_data = []
        for evidencia in evidencias:
            # Calcular días desde subida (ya que no hay fecha_expiracion)
            dias_desde_subida = (timezone.now() - evidencia.fecha_subida).days
            
            evidencias_data.append({
                'id': evidencia.id,
                'url': evidencia.imagen.url if evidencia.imagen else None,  # URL Cloudinary
                'descripcion': evidencia.descripcion or '',
                'fecha_subida': evidencia.fecha_subida.isoformat(),
                'dias_desde_subida': dias_desde_subida,
                'trabajo': {
                    'id': evidencia.trabajo.id,
                    'cotizacion_numero': evidencia.trabajo.cotizacion.numero if evidencia.trabajo.cotizacion else 'N/A',
                    'cliente': evidencia.trabajo.cotizacion.cliente.nombre if evidencia.trabajo.cotizacion and evidencia.trabajo.cotizacion.cliente else 'N/A'
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
        logger.error(f"❌ Error obteniendo evidencias admin: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@jwt_required
def descargar_evidencia(request, evidencia_id):
    """API para app móvil - Descargar evidencia desde Cloudinary"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        perfil_empleado = request.user.perfilempleado
        
        if perfil_empleado.cargo == 'admin':
            evidencia = get_object_or_404(EvidenciaTrabajo, id=evidencia_id)
        else:
            evidencia = get_object_or_404(
                EvidenciaTrabajo, 
                id=evidencia_id,
                trabajo__empleado=perfil_empleado
            )
        
        logger.info(f"📥 Descargando evidencia {evidencia_id}")
        
        # Retornar URL de descarga directa de Cloudinary
        if evidencia.imagen:
            download_url = evidencia.imagen.url
            logger.info(f"🔗 URL descarga: {download_url}")
            
            return JsonResponse({
                'success': True,
                'download_url': download_url,
                'filename': f'evidencia_{evidencia.id}.jpg'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Evidencia sin imagen'
            }, status=404)
        
    except Exception as e:
        logger.error(f"❌ Error descargando evidencia: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@jwt_required
@csrf_exempt
@require_http_methods(["POST"])
def eliminar_evidencia(request, evidencia_id):
    """API para admin y empleados - Eliminar evidencia de Cloudinary"""
    import logging
    import cloudinary.uploader
    logger = logging.getLogger(__name__)
    
    try:
        perfil = request.user.perfilempleado
        evidencia = get_object_or_404(EvidenciaTrabajo, id=evidencia_id)
        
        # Verificar permisos: admin o dueño del trabajo
        if perfil.cargo != 'admin' and evidencia.trabajo.empleado != perfil:
            return JsonResponse({
                'success': False,
                'error': 'Acceso denegado. Solo puedes eliminar tus propias evidencias.'
            }, status=403)
        
        logger.info(f"🗑️ Eliminando evidencia ID: {evidencia_id}")
        
        # Guardar info antes de eliminar
        info = {
            'id': evidencia.id,
            'trabajo_id': evidencia.trabajo.id,
            'descripcion': evidencia.descripcion,
        }
        
        # Eliminar archivo de Cloudinary usando public_id
        if evidencia.imagen:
            try:
                public_id = evidencia.imagen.public_id
                cloudinary.uploader.destroy(public_id, resource_type='image')
                logger.info(f"✅ Archivo eliminado de Cloudinary: {public_id}")
            except Exception as e:
                logger.warning(f"⚠️ No se pudo eliminar de Cloudinary: {e}")
        
        # Eliminar registro de base de datos
        evidencia.delete()
        logger.info(f"✅ Evidencia {evidencia_id} eliminada de BD")
        
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
        logger.error(f"❌ Error eliminando evidencia: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@jwt_required
def verificar_almacenamiento_cloudinary(request):
    """Endpoint para verificar y gestionar almacenamiento de Cloudinary"""
    import logging
    logger = logging.getLogger(__name__)
    try:
        perfil = PerfilEmpleado.objects.get(user=request.user)
        if perfil.cargo != 'admin':
            return JsonResponse({'success': False, 'error': 'Solo administradores'}, status=403)

        from app_movil.cloudinary_monitor import verificar_y_gestionar_almacenamiento
        resultado = verificar_y_gestionar_almacenamiento()

        return JsonResponse({'success': True, 'resultado': resultado})
    except Exception as e:
        logger.error(f"❌ Error verificando almacenamiento: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

# ==================== GASTOS ====================

@jwt_required
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


@jwt_required
def obtener_gastos_trabajo(request, trabajo_id):
    """API para app móvil - Obtener gastos de un trabajo"""
    try:
        perfil_empleado = request.user.perfilempleado
        if perfil_empleado.cargo == 'admin':
            trabajo = get_object_or_404(TrabajoEmpleado, id=trabajo_id)
        else:
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

@jwt_required
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


@jwt_required
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


@jwt_required
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


@jwt_required
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





def enviar_push_a_empleado(perfil_empleado, titulo, mensaje):
    """Helper - Enviar push notification a un empleado via Expo"""
    import urllib.request
    import urllib.error

    try:
        token = perfil_empleado.expo_push_token
        if not token:
            print(f"⚠️ Empleado {perfil_empleado} no tiene push token")
            return False

        payload = json.dumps({
            "to": token,
            "title": titulo,
            "body": mensaje,
            "sound": "default",
            "priority": "high",
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://exp.host/--/api/v2/push/send",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            resultado = json.loads(response.read().decode("utf-8"))
            print(f"✅ Push enviado a {perfil_empleado}: {resultado}")
            return True

    except Exception as e:
        print(f"❌ Error enviando push a {perfil_empleado}: {e}")
        return False

# ==================== LOGIN JWT ====================

@csrf_exempt
@require_http_methods(["POST"])
def login_movil_jwt(request):
    """Login para app móvil - Devuelve tokens JWT"""
    try:
        # Aceptar tanto FormData como JSON
        if request.content_type and 'application/json' in request.content_type:
            data = json.loads(request.body)
            username = data.get('username')
            password = data.get('password')
        else:
            username = request.POST.get('username')
            password = request.POST.get('password')

        if not username or not password:
            return JsonResponse({
                'success': False,
                'error': 'Usuario y contraseña son obligatorios'
            }, status=400)

        user = authenticate(request, username=username, password=password)

        if user is None:
            return JsonResponse({
                'success': False,
                'error': 'Credenciales incorrectas'
            }, status=401)

        if not user.is_active:
            return JsonResponse({
                'success': False,
                'error': 'Usuario inactivo'
            }, status=401)

        # Generar tokens JWT
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        # Obtener datos del perfil
        try:
            perfil = PerfilEmpleado.objects.get(user=user)
            nombre = user.get_full_name() or user.username
            cargo = perfil.cargo
        except PerfilEmpleado.DoesNotExist:
            nombre = user.username
            cargo = None

        logger.info(f"✅ Login JWT exitoso: {username}")

        return JsonResponse({
            'success': True,
            'access': access_token,
            'refresh': refresh_token,
            'usuario': {
                'username': user.username,
                'nombre': nombre,
                'email': user.email,
                'cargo': cargo,
            }
        })

    except Exception as e:
        logger.error(f"❌ Error en login JWT: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def refresh_token_movil(request):
    """Renovar access token usando refresh token"""
    try:
        data = json.loads(request.body)
        refresh_token = data.get('refresh')

        if not refresh_token:
            return JsonResponse({'success': False, 'error': 'Refresh token requerido'}, status=400)

        refresh = RefreshToken(refresh_token)
        access_token = str(refresh.access_token)

        return JsonResponse({
            'success': True,
            'access': access_token,
        })

    except TokenError as e:
        return JsonResponse({'success': False, 'error': 'Token inválido o expirado'}, status=401)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# ==================== PUSH NOTIFICATIONS ====================

@jwt_required
@csrf_exempt
@require_http_methods(["POST"])
def registrar_push_token(request):
    """Guarda el Expo Push Token del dispositivo del empleado"""
    try:
        data = json.loads(request.body)
        token = data.get('token', '').strip()

        if not token:
            return JsonResponse({'success': False, 'error': 'Token vacío'}, status=400)

        perfil = PerfilEmpleado.objects.get(user=request.user)
        perfil.expo_push_token = token
        perfil.save()

        return JsonResponse({'success': True, 'message': 'Token registrado'})

    except PerfilEmpleado.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Perfil no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)