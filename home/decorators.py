from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.contrib import messages
from .models import PerfilEmpleado


def requiere_cargo(cargos_permitidos):
    """
    Decorador que verifica que el usuario tenga uno de los cargos permitidos
    Verifica en tiempo real contra la base de datos
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            try:
                # Verificación en tiempo real desde la BD
                perfil = PerfilEmpleado.objects.get(user=request.user)
                
                # Verificar que el perfil esté activo
                if not perfil.activo:
                    messages.error(request, 'Tu cuenta ha sido desactivada.')
                    return redirect('login')
                
                # Verificar cargo
                if perfil.cargo not in cargos_permitidos:
                    messages.error(request, 'No tienes permisos para acceder a esta función.')
                    return redirect('panel_empleados')
                
                return view_func(request, *args, **kwargs)
                
            except PerfilEmpleado.DoesNotExist:
                messages.error(request, 'Perfil de empleado no encontrado.')
                return redirect('login')
                
        return wrapper
    return decorator

def requiere_admin(view_func):
    """Decorador específico para funciones de administrador"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            perfil = PerfilEmpleado.objects.get(user=request.user)
            if not perfil.es_admin() or not perfil.activo:
                return render(request, 'home/error.html')
            return view_func(request, *args, **kwargs)
        except PerfilEmpleado.DoesNotExist:
            return render(request, 'home/error.html')
    return wrapper

def requiere_gerente_o_superior(view_func):
    """Decorador para gerentes y superiores"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            perfil = PerfilEmpleado.objects.get(user=request.user)
            if not perfil.es_gerente_o_superior() or not perfil.activo:
                return render(request, 'home/error.html')
            return view_func(request, *args, **kwargs)
        except PerfilEmpleado.DoesNotExist:
            return render(request, 'home/error.html')
    return wrapper

def prevent_cache(view_func):
    """Decorador para prevenir que las páginas se almacenen en caché"""
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
    return wrapped_view

def user_must_be_authenticated(view_func):
    """Decorador que redirige al login si el usuario no está autenticado"""
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Debes iniciar sesión para acceder a esta página.')
            return redirect('home:login')
        return view_func(request, *args, **kwargs)
    return wrapped_view