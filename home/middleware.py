from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import logout
from .models import PerfilEmpleado

class PerfilEmpleadoMiddleware:
    """Middleware que verifica el estado del perfil del empleado en cada request"""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # URLs que no requieren verificación
        exempt_urls = [
            '/login/', 
            '/logout/', 
            '/admin/',
            '/static/',
            '/media/',
            '/',  # página principal
        ]
        
        # Si la URL está exenta, continuar
        if any(request.path.startswith(url) for url in exempt_urls):
            return self.get_response(request)
        
        # Solo verificar usuarios autenticados
        if request.user.is_authenticated:
            try:
                perfil = PerfilEmpleado.objects.get(user=request.user)
                
                # Si el perfil está inactivo, cerrar sesión
                if not perfil.activo:
                    messages.error(request, 'Tu cuenta ha sido desactivada.')
                    logout(request)
                    return redirect('login')
                    
            except PerfilEmpleado.DoesNotExist:
                # Si no tiene perfil de empleado, cerrar sesión
                messages.error(request, 'Perfil de empleado no encontrado.')
                logout(request)
                return redirect('login')
        
        return self.get_response(request)