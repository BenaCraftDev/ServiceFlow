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
                    return redirect('home:panel_empleados')
                else:
                    messages.error(request, 'Tu cuenta está desactivada. Contacta al administrador.')
            except PerfilEmpleado.DoesNotExist:
                messages.error(request, 'No tienes permisos de empleado.')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')
    
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
    """Vista para solicitar recuperación de contraseña"""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        
        try:
            user = User.objects.get(email=email)
            
            # Verificar que tenga perfil de empleado activo
            try:
                perfil = PerfilEmpleado.objects.get(user=user)
                if not perfil.activo:
                    messages.error(request, 'Tu cuenta está desactivada. Contacta al administrador.')
                    return render(request, 'home/recuperar_password.html')
            except PerfilEmpleado.DoesNotExist:
                messages.error(request, 'No se encontró un perfil de empleado asociado a este correo.')
                return render(request, 'home/recuperar_password.html')
            
            # Generar token y uid
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Crear enlace de recuperación
            reset_url = request.build_absolute_uri(
                reverse('home:reset_password', kwargs={'uidb64': uid, 'token': token})
            )
            
            # Preparar email
            subject = 'Recuperación de Contraseña - Panel de Empleados'
            message = f"""
Hola {user.get_full_name() or user.username},

Has solicitado restablecer tu contraseña para el Panel de Empleados.

Haz clic en el siguiente enlace para crear una nueva contraseña:
{reset_url}

Este enlace expirará en 24 horas.

Si no solicitaste este cambio, puedes ignorar este correo de forma segura.

Saludos,
Equipo de Administración
            """
            
            # Enviar email
            try:
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
                messages.success(
                    request, 
                    'Se ha enviado un enlace de recuperación a tu correo electrónico. Por favor revisa tu bandeja de entrada.'
                )
            except Exception as e:
                messages.error(
                    request, 
                    'Error al enviar el correo. Por favor contacta al administrador.'
                )
                print(f"Error al enviar email: {str(e)}")
            
        except User.DoesNotExist:
            # Por seguridad, mostramos el mismo mensaje aunque el usuario no exista
            messages.success(
                request, 
                'Si el correo existe en nuestro sistema, recibirás un enlace de recuperación.'
            )
    
    return render(request, 'home/recuperar_password.html')

def reset_password(request, uidb64, token):
    """Vista para restablecer la contraseña con el token"""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    
    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            password1 = request.POST.get('password1')
            password2 = request.POST.get('password2')
            
            if password1 and password2:
                if password1 == password2:
                    # Validaciones básicas de contraseña
                    if len(password1) < 8:
                        messages.error(request, 'La contraseña debe tener al menos 8 caracteres.')
                    elif not any(char.isdigit() for char in password1):
                        messages.error(request, 'La contraseña debe contener al menos un número.')
                    elif not any(char.isupper() for char in password1):
                        messages.error(request, 'La contraseña debe contener al menos una mayúscula.')
                    elif not any(char.islower() for char in password1):
                        messages.error(request, 'La contraseña debe contener al menos una minúscula.')
                    else:
                        # Cambiar contraseña
                        user.set_password(password1)
                        user.save()
                        messages.success(
                            request, 
                            'Tu contraseña ha sido cambiada exitosamente. Ya puedes iniciar sesión.'
                        )
                        return redirect('home:login')
                else:
                    messages.error(request, 'Las contraseñas no coinciden.')
            else:
                messages.error(request, 'Por favor completa ambos campos.')
        
        return render(request, 'home/reset_password.html', {
            'validlink': True,
            'uidb64': uidb64,
            'token': token
        })
    else:
        messages.error(
            request, 
            'El enlace de recuperación es inválido o ha expirado. Por favor solicita uno nuevo.'
        )
        return redirect('home:recuperar_password')

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
                {'nombre': 'Gestión de Clientes', 'url': 'cotizaciones:gestionar_clientes', 'icono': '👤'},
                {'nombre': 'Catálogo de Servicios', 'url': 'cotizaciones:gestionar_servicios', 'icono': '🔧'},
                {'nombre': 'Catálogo de Materiales', 'url': 'cotizaciones:gestionar_materiales', 'icono': '📦'},
                {'nombre': 'Catálogo de Mano de Obra', 'url': 'cotizaciones:gestionar_categorias_empleados', 'icono': '👷'},
                {'nombre': 'Reportes Generales', 'url': 'cotizaciones:reportes_dashboard', 'icono': '📈'},
                {'nombre': 'Seguimiento de Trabajos', 'url': 'cotizaciones:seguimiento_trabajos', 'icono': '🔄'},
                {'nombre': 'Prestamos', 'url': 'cotizaciones:lista_prestamos', 'icono': '🧰'},
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




