from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .models import Notificacion

@login_required
def obtener_notificaciones(request):
    """Obtiene las últimas 10 notificaciones del usuario"""
    notificaciones = Notificacion.objects.filter(usuario=request.user)[:10]
    no_leidas = Notificacion.objects.filter(usuario=request.user, leida=False).count()
    
    data = {
        'notificaciones': [{
            'id': n.id,
            'titulo': n.titulo,
            'mensaje': n.mensaje,
            'tipo': n.tipo,
            'leida': n.leida,
            'url': n.url,
            'fecha': n.fecha_creacion.strftime('%d/%m/%Y %H:%M')
        } for n in notificaciones],
        'no_leidas': no_leidas
    }
    
    return JsonResponse(data)

@login_required
@require_POST
def marcar_leida(request, notificacion_id):
    """Marca una notificación como leída"""
    notificacion = get_object_or_404(Notificacion, id=notificacion_id, usuario=request.user)
    notificacion.leida = True
    notificacion.save()
    
    no_leidas = Notificacion.objects.filter(usuario=request.user, leida=False).count()
    
    return JsonResponse({'success': True, 'no_leidas': no_leidas})

@login_required
@require_POST
def marcar_todas_leidas(request):
    """Marca todas las notificaciones como leídas"""
    Notificacion.objects.filter(usuario=request.user, leida=False).update(leida=True)
    
    return JsonResponse({'success': True, 'no_leidas': 0})

@login_required
def lista_notificaciones(request):
    """Vista completa de todas las notificaciones"""
    notificaciones = Notificacion.objects.filter(usuario=request.user)
    
    return render(request, 'notificaciones/lista.html', {
        'notificaciones': notificaciones
    })