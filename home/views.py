import json
import csv
from .models import *
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden, JsonResponse, HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .decorators import requiere_admin, requiere_gerente_o_superior, prevent_cache
from django.contrib import messages
from .models import PerfilEmpleado
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.utils import timezone
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from cotizaciones.utils_mantenimiento import verificar_mantenimientos_materiales
from django.views.decorators.csrf import csrf_exempt
from cotizaciones.models import Cotizacion, Cliente, TipoTrabajo, Solicitud_Web
from notificaciones.utils import crear_notificacion
from django.core.cache import cache
from cotizaciones.utils import enviar_email_con_reintentos, verificar_configuracion_email

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def index(request):
    return render(request, 'home/index.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            # Verificar que tenga perfil de empleado
            try:
                perfil = PerfilEmpleado.objects.get(user=user)
                if perfil.activo:
                    login(request, user)
                    
                    # ========== DETECTAR PETICIÓN DE APP MÓVIL ==========
                    if request.headers.get('Accept') == 'application/json':
                        return JsonResponse({
                            'success': True,
                            'usuario': {
                                'username': user.username,
                                'nombre': user.get_full_name(),
                                'email': user.email,
                                'cargo': perfil.cargo
                            }
                        })
                    # ========== FIN ==========
                    
                    return redirect('home:panel_empleados')
                else:
                    messages.error(request, 'Tu cuenta está desactivada. Contacta al administrador.')
            except PerfilEmpleado.DoesNotExist:
                messages.error(request, 'No tienes permisos de empleado.')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')
            
            # ========== DETECTAR PETICIÓN DE APP MÓVIL CON ERROR ==========
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({
                    'success': False,
                    'error': 'Usuario o contraseña incorrectos'
                }, status=401)
            # ========== FIN ==========
    
    return render(request, 'home/login.html')

def logout_view(request):
    logout(request)
    messages.success(request, 'Has cerrado sesión exitosamente.')
    response = redirect('home:login')
    
    # Prevenir caché del navegador
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    
    return response

def recuperar_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        user = User.objects.filter(email=email).first()
        
        if user:
            # Generar datos para el enlace
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            base_url = request.build_absolute_uri('/')[:-1]
            # La URL que el usuario clickeará
            url_reset = f"{base_url}{reverse('home:reset_password', kwargs={'uidb64': uid, 'token': token})}"
            
            # Contexto para el template de email
            context_email = {
                'user': user,
                'url_reset': url_reset,
                'config_empresa': ConfiguracionEmpresa.get_config(),
            }
            
            # Renderizar el HTML del correo
            html_content = render_to_string('home/emails/reset_password_email.html', context_email)
            subject = f"Restablecer Contraseña - {ConfiguracionEmpresa.get_config().nombre}"
            
            # USAR TU FUNCIÓN ROBUSTA DE REINTENTOS
            exito, mensaje = enviar_email_con_reintentos(
                subject=subject,
                html_content=html_content,
                recipient_list=[email],
                max_intentos=3,
                timeout_segundos=20,
                fail_silently=False
            )
            
            if exito:
                messages.success(request, '✅ Se ha enviado un enlace a tu correo.')
                return redirect('home:login')
            else:
                logger.error(f"Error SMTP en recuperación: {mensaje}")
                messages.error(request, '❌ No se pudo conectar con el servicio externo de correo.')
        else:
            # Por seguridad, no confirmamos si el email existe o no
            messages.success(request, 'Si el correo existe en nuestro sistema, recibirás un enlace pronto.')
            return redirect('home:login')
            
    return render(request, 'home/recuperar_password.html')

def recuperar_password(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        user = User.objects.filter(email=email).first()
        
        if user:
            try:
                # 1. Generar tokens de seguridad
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                base_url = request.build_absolute_uri('/')[:-1]
                url_reset = f"{base_url}{reverse('home:reset_password', kwargs={'uidb64': uid, 'token': token})}"
                
                # 2. Preparar el contenido
                # Si no tienes el modelo ConfiguracionEmpresa a mano, cámbialo por un string
                subject = "Restablecer Contraseña"
                context = {'user': user, 'url_reset': url_reset}
                html_message = render_to_string('home/emails/reset_password_email.html', context)
                
                # 3. Envío directo usando la configuración de settings.py
                # Esto es lo que suele fallar si el puerto 587 está bloqueado
                send_mail(
                    subject,
                    f"Usa este enlace: {url_reset}", # Mensaje en texto plano
                    settings.EMAIL_HOST_USER,
                    [email],
                    html_message=html_message,
                    fail_silently=False,
                )
                
                messages.success(request, '✅ Enlace enviado. Revisa tu bandeja de entrada.')
                return redirect('home:login')

            except Exception as e:
                # Esto evita el Error 500 y te dice qué pasó en la consola
                print(f"DEBUG ERROR: {str(e)}") 
                messages.error(request, f'❌ Error técnico: {str(e)}')
        else:
            messages.success(request, 'Si el correo existe, recibirás instrucciones.')
            return redirect('home:login')

    return render(request, 'home/recuperar_password.html')

@csrf_exempt
def solicitar_servicio_publico(request):
    """
    Vista pública para recibir solicitudes de servicio con protección anti-spam.
    """
    # 1. Obtener IP y verificar límite
    user_ip = get_client_ip(request)
    cache_key = f"limit_solicitud_{user_ip}"

    data = json.loads(request.body)

    # Engaña Bots
    if data.get('website_url_field'):
        return JsonResponse({'success': True, 'message': 'Solicitud procesada correctamente'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    # Si la IP está en caché, bloqueamos (429 Too Many Requests)
    if cache.get(cache_key):
        return JsonResponse({
            'success': False, 
            'error': 'Has enviado demasiadas solicitudes. Por favor, espera 5 minutos.'
        }, status=429)

    try:
        # Parsear datos
        data = json.loads(request.body)
        
        # --- PROTECCIÓN HONEYPOT ---
        # Si este campo (que debe estar oculto en el CSS) tiene contenido, es un BOT.
        if data.get('website_url_field'): 
            return JsonResponse({'success': True, 'message': 'Procesado (H)'}) 

        # Extraer datos
        nombre = data.get('nombre', '').strip()
        email = data.get('email', '').strip()
        telefono = data.get('telefono', '').strip()
        tipo_servicio = data.get('tipo_servicio', '').strip()
        ubicacion = data.get('ubicacion', '').strip()
        info_extra = data.get('info_extra', '').strip()
        es_personalizado = data.get('es_personalizado', False)
        
        # Validaciones básicas
        if not all([nombre, telefono, tipo_servicio, ubicacion]):
            return JsonResponse({'success': False, 'error': 'Faltan campos obligatorios'}, status=400)

        # 2. Guardar Solicitud (Solo strings, máxima seguridad)
        solicitud = Solicitud_Web.objects.create(
            nombre_solicitante=nombre,
            email_solicitante=email if email else None,
            telefono_solicitante=telefono,
            tipo_servicio_solicitado=tipo_servicio,
            ubicacion_trabajo=ubicacion,
            informacion_adicional=info_extra,
            es_servicio_personalizado=es_personalizado,
            estado='pendiente',
            ip_origen=user_ip,
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
        )

        # 3. Notificar a los administradores (Gerentes/Admin)
        try:
            usuarios_notificar = User.objects.filter(
                perfilempleado__cargo__in=['administrador', 'gerente']
            ).distinct() or User.objects.filter(is_staff=True)

            for usuario in usuarios_notificar:
                crear_notificacion(
                    usuario=usuario,
                    tipo='info',
                    titulo='🌐 Nueva Solicitud Web',
                    mensaje=f'Solicitud de {nombre}: {tipo_servicio}',
                    url='/cotizaciones/solicitudes-web/'
                )
        except Exception as e:
            print(f"⚠️ Error en notificaciones: {e}")

        # 4. ACTIVAR BLOQUEO DE IP (5 Minutos)
        # Solo lo activamos si la solicitud fue exitosa
        cache.set(cache_key, True, 300)

        return JsonResponse({
            'success': True,
            'message': '¡Solicitud enviada con éxito!',
            'numero_referencia': f"WEB-{solicitud.id:05d}"
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': 'Error interno de servidor'}, status=500)

@login_required
@require_http_methods(["GET"])
def obtener_tipos_trabajo_publicos(request):
    """
    Vista para obtener los tipos de trabajo activos
    """
    try:
        tipos = TipoTrabajo.objects.filter(activo=True).values('id', 'nombre', 'descripcion')
        return JsonResponse({
            'success': True,
            'tipos': list(tipos)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@prevent_cache
@login_required
def panel_empleados(request):
    verificar_mantenimientos_materiales(request)

    try:
        perfil = PerfilEmpleado.objects.get(user=request.user)
        
        # Definir funciones disponibles según el cargo
        funciones_disponibles = []
        
        if perfil.es_admin():
            funciones_disponibles = [
                {'nombre': 'Gestión de Usuarios', 'url': 'home:gestion_usuarios', 'icono': '👥'},
                {'nombre': 'Sistema de Cotizaciones', 'url': 'cotizaciones:dashboard', 'icono': '📊'},
                {'nombre': 'Tipos de Trabajos', 'url': 'cotizaciones:dashboard', 'icono': '⛏'},
                {'nombre': 'Gestión de Clientes', 'url': 'cotizaciones:gestionar_clientes', 'icono': '👤'},
                {'nombre': 'Catálogo de Servicios', 'url': 'cotizaciones:gestionar_servicios', 'icono': '🔧'},
                {'nombre': 'Catálogo de Materiales', 'url': 'cotizaciones:gestionar_materiales', 'icono': '📦'},
                {'nombre': 'Catálogo de Mano de Obra', 'url': 'cotizaciones:gestionar_categorias_empleados', 'icono': '👷'},
                {'nombre': 'Reportes Generales', 'url': 'cotizaciones:reportes_dashboard', 'icono': '📈'},
                {'nombre': 'Seguimiento de Trabajos', 'url': 'cotizaciones:seguimiento_trabajos', 'icono': '🔄'},
                {'nombre': 'Prestamos', 'url': 'cotizaciones:lista_prestamos', 'icono': '🧰'},
                {'nombre': 'Solicitudes Web', 'url': 'cotizaciones:lista_solicitudes_web', 'icono': '🌐'},
            ]
        elif perfil.es_gerente_o_superior():
            funciones_disponibles = [
            ]
        elif perfil.es_supervisor_o_superior():
            funciones_disponibles = [
            ]
        else:
            funciones_disponibles = [
                {'nombre': 'Mis Tareas', 'url': 'cotizaciones:mis_trabajos_empleado', 'icono': '📌'},
                {'nombre': 'Configuración', 'url': 'home:configuracion_usuario', 'icono': '⚙️'}
            ]
        
        context = {
            'perfil': perfil,
            'funciones_disponibles': funciones_disponibles,
        }
        return render(request, 'home/panel_empleados.html', context)
        
    except PerfilEmpleado.DoesNotExist:
        messages.error(request, 'No tienes permisos de empleado.')
        return redirect('index')

# Vistas para las diferentes funciones de Admin
@login_required
@requiere_gerente_o_superior
def gestion_usuarios(request):
    verificar_mantenimientos_materiales(request)
    """Vista principal del panel de gestión de usuarios"""
    
    # Obtener parámetros de filtro
    query = request.GET.get('q', '')
    cargo_filter = request.GET.get('cargo', '')
    activo_filter = request.GET.get('activo', '')
    
    # Query base
    empleados = PerfilEmpleado.objects.select_related('user').all()
    
    # Aplicar filtros
    if query:
        empleados = empleados.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__username__icontains=query) |
            Q(user__email__icontains=query) 
        )
    
    if cargo_filter:
        empleados = empleados.filter(cargo=cargo_filter)
    
    if activo_filter in ['0', '1']:
        empleados = empleados.filter(activo=activo_filter == '1')
    
    
    # Ordenar
    empleados = empleados.order_by('-fecha_creacion')
    
    # Paginación
    paginator = Paginator(empleados, 15)  # 15 empleados por página
    page = request.GET.get('page')
    empleados_page = paginator.get_page(page)
    
    # Estadísticas
    total_empleados = PerfilEmpleado.objects.count()
    empleados_activos = PerfilEmpleado.objects.filter(activo=True).count()
    empleados_inactivos = total_empleados - empleados_activos
    porcentaje_activos = round((empleados_activos / total_empleados * 100) if total_empleados > 0 else 0, 1)
    
    # Nuevos empleados en los últimos 30 días
    hace_30_dias = timezone.now() - timedelta(days=30)
    nuevos_mes = PerfilEmpleado.objects.filter(fecha_ingreso__gte=hace_30_dias.date()).count()
    
    # Opciones para filtros
    cargos_choices = PerfilEmpleado.CARGO_CHOICES
    
    # Construir parámetros URL para paginación
    url_params = ''
    if query:
        url_params += f'&q={query}'
    if cargo_filter:
        url_params += f'&cargo={cargo_filter}'
    if activo_filter:
        url_params += f'&activo={activo_filter}'
    
    context = {
        'empleados': empleados_page,
        'total_empleados': total_empleados,
        'empleados_activos': empleados_activos,
        'empleados_inactivos': empleados_inactivos,
        'porcentaje_activos': porcentaje_activos,
        'nuevos_mes': nuevos_mes,
        'cargos_choices': cargos_choices,
        'url_params': url_params,
    }
    
    return render(request, 'home/gestion_usuarios.html', context)

@login_required
@requiere_admin
@require_http_methods(["POST"])
def crear_usuario_api(request):
    """API para crear nuevo usuario"""
    try:
        with transaction.atomic():
            # Validar datos requeridos
            username = request.POST.get('username', '').strip()
            email = request.POST.get('email', '').strip()
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            password = request.POST.get('password', '').strip()
            rut = request.POST.get('rut', '').strip()
            cargo = request.POST.get('cargo')
            fecha_ingreso = request.POST.get('fecha_ingreso')
            
            if not all([username, email, first_name, last_name, password, rut, cargo, fecha_ingreso]):
                return JsonResponse({
                    'success': False, 
                    'message': 'Todos los campos obligatorios deben ser completados'
                })
            
            # Verificar que el username no exista
            if User.objects.filter(username=username).exists():
                return JsonResponse({
                    'success': False, 
                    'message': 'El nombre de usuario ya existe'
                })
            
            # Verificar que el email no exista
            if User.objects.filter(email=email).exists():
                return JsonResponse({
                    'success': False, 
                    'message': 'El email ya está registrado'
                })
            
            # Verificar que el RUT no exista
            rut_limpio = rut.replace('.', '').replace('-', '').upper()
            if PerfilEmpleado.objects.filter(rut__icontains=rut_limpio[:-2]).exists():
                return JsonResponse({
                    'success': False, 
                    'message': 'El RUT ya está registrado'
                })
            
            # Crear usuario
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=password
            )
            
            # Crear perfil
            perfil = PerfilEmpleado.objects.create(
                user=user,
                rut=rut,
                cargo=cargo,
                fecha_ingreso=fecha_ingreso,
                telefono=request.POST.get('telefono', '').strip() or None,
                salario=request.POST.get('salario') or None,
                activo=request.POST.get('activo') == 'on'
            )
            
            return JsonResponse({
                'success': True, 
                'message': f'Usuario {user.get_full_name()} creado exitosamente'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'message': f'Error al crear usuario: {str(e)}'
        })

@login_required
@requiere_admin
def obtener_usuario_api(request, user_id):
    """API para obtener datos de un usuario"""
    try:
        perfil = get_object_or_404(PerfilEmpleado, id=user_id)
        
        return JsonResponse({
            'success': True,
            'user': {
                'username': perfil.user.username,
                'email': perfil.user.email,
                'first_name': perfil.user.first_name,
                'last_name': perfil.user.last_name,
            },
            'perfil': {
                'rut': perfil.rut,
                'cargo': perfil.cargo,
                'fecha_ingreso': perfil.fecha_ingreso.strftime('%Y-%m-%d'),
                'telefono': perfil.telefono,
                'salario': float(perfil.salario) if perfil.salario else None,
                'activo': perfil.activo,
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'message': f'Error al obtener usuario: {str(e)}'
        })

@login_required
@requiere_admin
@require_http_methods(["POST"])
def actualizar_usuario_api(request, user_id):
    """API para actualizar usuario"""
    try:
        with transaction.atomic():
            perfil = get_object_or_404(PerfilEmpleado, id=user_id)
            user = perfil.user
            
            # Actualizar datos del usuario
            username = request.POST.get('username', '').strip()
            email = request.POST.get('email', '').strip()
            rut = request.POST.get('rut', '').strip()
            
            # Verificar username único (excluyendo el usuario actual)
            if username != user.username and User.objects.filter(username=username).exists():
                return JsonResponse({
                    'success': False, 
                    'message': 'El nombre de usuario ya existe'
                })
            
            # Verificar email único (excluyendo el usuario actual)
            if email != user.email and User.objects.filter(email=email).exists():
                return JsonResponse({
                    'success': False, 
                    'message': 'El email ya está registrado'
                })
            
            # Verificar RUT único (excluyendo el usuario actual)
            rut_limpio = rut.replace('.', '').replace('-', '').upper()
            perfil_rut_limpio = perfil.rut.replace('.', '').replace('-', '').upper()
            if rut_limpio != perfil_rut_limpio:
                if PerfilEmpleado.objects.filter(rut__icontains=rut_limpio[:-2]).exclude(id=perfil.id).exists():
                    return JsonResponse({
                        'success': False, 
                        'message': 'El RUT ya está registrado'
                    })
            
            # Actualizar usuario
            user.username = username
            user.email = email
            user.first_name = request.POST.get('first_name', '').strip()
            user.last_name = request.POST.get('last_name', '').strip()
            
            # Cambiar contraseña si se proporcionó
            password = request.POST.get('password', '').strip()
            if password:
                user.set_password(password)
            
            user.save()
            
            # Actualizar perfil
            perfil.rut = rut
            perfil.cargo = request.POST.get('cargo')
            perfil.fecha_ingreso = request.POST.get('fecha_ingreso')
            perfil.telefono = request.POST.get('telefono', '').strip() or None
            salario = request.POST.get('salario')
            perfil.salario = salario if salario else None
            perfil.activo = request.POST.get('activo') == 'on'
            perfil.save()
            
            return JsonResponse({
                'success': True, 
                'message': f'Usuario {user.get_full_name()} actualizado exitosamente'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'message': f'Error al actualizar usuario: {str(e)}'
        })

@login_required
@requiere_admin
@require_http_methods(["POST"])
def cambiar_estado_usuario_api(request, user_id):
    """API para activar/desactivar usuario"""
    try:
        perfil = get_object_or_404(PerfilEmpleado, id=user_id)
        
        # No permitir que el admin se desactive a sí mismo
        if perfil.user == request.user:
            return JsonResponse({
                'success': False, 
                'message': 'No puedes desactivar tu propia cuenta'
            })
        
        data = json.loads(request.body)
        nuevo_estado = data.get('activo', True)
        
        perfil.activo = nuevo_estado
        perfil.save()
        
        estado_texto = "activado" if nuevo_estado else "desactivado"
        
        return JsonResponse({
            'success': True, 
            'message': f'Usuario {perfil.nombre_completo} {estado_texto} exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'message': f'Error al cambiar estado: {str(e)}'
        })

@login_required
@requiere_admin
@require_http_methods(["DELETE"])
def eliminar_usuario_api(request, user_id):
    """API para eliminar usuario"""
    try:
        perfil = get_object_or_404(PerfilEmpleado, id=user_id)
        
        # No permitir que el admin se elimine a sí mismo
        if perfil.user == request.user:
            return JsonResponse({
                'success': False, 
                'message': 'No puedes eliminar tu propia cuenta'
            })
        
        nombre_completo = perfil.nombre_completo
        perfil.user.delete()  # Esto también eliminará el perfil por CASCADE
        
        return JsonResponse({
            'success': True, 
            'message': f'Usuario {nombre_completo} eliminado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'message': f'Error al eliminar usuario: {str(e)}'
        })

@login_required
@requiere_gerente_o_superior
def export_usuarios_csv(request):
    """Exportar usuarios a CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="empleados.csv"'
    response.write('\ufeff')  # BOM para UTF-8
    
    writer = csv.writer(response)
    writer.writerow([
        'RUT', 'Usuario', 'Nombre', 'Apellido', 'Email', 'Cargo',
        'Fecha Ingreso', 'Teléfono', 'Salario', 'Estado', 'Fecha Creación'
    ])
    
    empleados = PerfilEmpleado.objects.select_related('user').all()
    
    for perfil in empleados:
        writer.writerow([
            perfil.rut,
            perfil.user.username,
            perfil.user.first_name,
            perfil.user.last_name,
            perfil.user.email,
            perfil.get_cargo_display(),
            perfil.fecha_ingreso.strftime('%d/%m/%Y'),
            perfil.telefono or '',
            perfil.salario or '',
            'Activo' if perfil.activo else 'Inactivo',
            perfil.fecha_creacion.strftime('%d/%m/%Y %H:%M')
        ])
    
    return response

@login_required
def mi_perfil(request):
    """Vista para que el usuario vea y edite su perfil"""
    try:
        perfil = PerfilEmpleado.objects.get(user=request.user)
        
        if request.method == 'POST':
            # Actualizar datos del usuario
            request.user.first_name = request.POST.get('first_name', '').strip()
            request.user.last_name = request.POST.get('last_name', '').strip()
            request.user.email = request.POST.get('email', '').strip()
            
            # Cambiar contraseña si se proporcionó
            password_actual = request.POST.get('password_actual', '').strip()
            password_nueva = request.POST.get('password_nueva', '').strip()
            password_confirmar = request.POST.get('password_confirmar', '').strip()
            
            if password_nueva:
                # Verificar contraseña actual
                if not request.user.check_password(password_actual):
                    messages.error(request, 'La contraseña actual es incorrecta.')
                    return render(request, 'home/mi_perfil.html', {'perfil': perfil})
                
                # Verificar que las contraseñas coincidan
                if password_nueva != password_confirmar:
                    messages.error(request, 'Las contraseñas nuevas no coinciden.')
                    return render(request, 'home/mi_perfil.html', {'perfil': perfil})
                
                # Validar contraseña nueva
                if len(password_nueva) < 8:
                    messages.error(request, 'La contraseña debe tener al menos 8 caracteres.')
                    return render(request, 'home/mi_perfil.html', {'perfil': perfil})
                
                # Cambiar contraseña
                request.user.set_password(password_nueva)
                messages.success(request, 'Contraseña actualizada. Por favor inicia sesión nuevamente.')
            
            request.user.save()
            
            # Actualizar perfil
            perfil.telefono = request.POST.get('telefono', '').strip() or None
            perfil.save()
            
            # Si cambió contraseña, cerrar sesión
            if password_nueva:
                logout(request)
                return redirect('home:login')
            
            messages.success(request, 'Perfil actualizado exitosamente.')
            return redirect('home:mi_perfil')
        
        context = {
            'perfil': perfil,
        }
        return render(request, 'home/mi_perfil.html', context)
        
    except PerfilEmpleado.DoesNotExist:
        messages.error(request, 'No tienes un perfil de empleado.')
        return redirect('home:panel_empleados')

@login_required
def configuracion_usuario(request):
    """Vista para configuraciones personales del usuario"""
    from .models import ConfiguracionUsuario
    
    # Obtener o crear configuración
    config = ConfiguracionUsuario.obtener_o_crear(request.user)
    
    if request.method == 'POST':
        # Actualizar apariencia
        config.tema = request.POST.get('tema', 'light')
        config.tamano_fuente = request.POST.get('tamano_fuente', 'medium')
        config.idioma = request.POST.get('idioma', 'es')
        
        # Actualizar notificaciones
        config.notificaciones_email = request.POST.get('notificaciones_email') == 'on'
        config.notificaciones_sistema = request.POST.get('notificaciones_sistema') == 'on'
        
        # Actualizar herramientas
        config.herramienta_calculadora = request.POST.get('herramienta_calculadora') == 'on'
        config.herramienta_notas = request.POST.get('herramienta_notas') == 'on'
        config.herramienta_recordatorios = request.POST.get('herramienta_recordatorios') == 'on'
        config.herramienta_conversor = request.POST.get('herramienta_conversor') == 'on'
        
        # Actualizar preferencias
        config.mostrar_tutorial = request.POST.get('mostrar_tutorial') == 'on'
        config.compactar_sidebar = request.POST.get('compactar_sidebar') == 'on'
        
        items = request.POST.get('items_por_pagina', '15')
        try:
            config.items_por_pagina = int(items)
        except ValueError:
            config.items_por_pagina = 15
        
        config.save()
        messages.success(request, 'Configuración guardada exitosamente.')
        return redirect('home:configuracion_usuario')
    
    context = {
        'config': config,
    }
    return render(request, 'home/configuracion_usuario.html', context)

# HANDLERS DE ERRORES PERSONALIZADOS

def handler404(request, exception):
    """Página personalizada para error 404"""
    return render(request, 'errors/404.html', {
        'error_code': '404',
        'error_title': 'Página no encontrada',
        'error_message': 'Lo sentimos, la página que buscas no existe.',
        'url_solicitada': request.path,
    }, status=404)

def handler403(request, exception):
    """Página personalizada para error 403"""
    return render(request, 'errors/403.html', {
        'error_code': '403',
        'error_title': 'Acceso denegado',
        'error_message': 'No tienes permiso para acceder a esta página.',
    }, status=403)

def handler500(request):
    """Página personalizada para error 500"""
    return render(request, 'errors/500.html', {
        'error_code': '500',
        'error_title': 'Error del servidor',
        'error_message': 'Ha ocurrido un error. Estamos trabajando para solucionarlo.',
    }, status=500)


