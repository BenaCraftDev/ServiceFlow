from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import Notificacion

@login_required
def obtener_notificaciones(request):
    """
    Obtiene SOLO las notificaciones NO LEÍDAS para la bandeja (dropdown).
    Máximo 15 notificaciones más recientes.
    """
    # Solo notificaciones NO LEÍDAS
    notificaciones = Notificacion.objects.filter(
        usuario=request.user,
        leida=False
    ).order_by('-fecha_creacion')[:15]
    
    no_leidas = Notificacion.objects.filter(usuario=request.user, leida=False).count()
    
    data = {
        'notificaciones': [{
            'id': n.id,
            'titulo': n.titulo,
            'mensaje': n.mensaje,
            'tipo': n.tipo,
            'leida': n.leida,
            'importante': n.importante,
            'url': n.url,
            'fecha': n.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
            'hace': calcular_tiempo_transcurrido(n.fecha_creacion)
        } for n in notificaciones],
        'no_leidas': no_leidas
    }
    
    return JsonResponse(data)

@login_required
@require_POST
def marcar_leida(request, notificacion_id):
    """Marca una notificación como leída y guarda la fecha"""
    notificacion = get_object_or_404(Notificacion, id=notificacion_id, usuario=request.user)
    
    if not notificacion.leida:
        notificacion.leida = True
        notificacion.fecha_leida = timezone.now()
        notificacion.save()
    
    no_leidas = Notificacion.objects.filter(usuario=request.user, leida=False).count()
    
    return JsonResponse({'success': True, 'no_leidas': no_leidas})

@login_required
@require_POST
def marcar_todas_leidas(request):
    """Marca todas las notificaciones como leídas"""
    ahora = timezone.now()
    notificaciones = Notificacion.objects.filter(usuario=request.user, leida=False)
    
    for notif in notificaciones:
        notif.leida = True
        notif.fecha_leida = ahora
        notif.save()
    
    return JsonResponse({'success': True, 'no_leidas': 0})

@login_required
@require_POST
def toggle_importante(request, notificacion_id):
    """Alterna el estado de importante de una notificación"""
    notificacion = get_object_or_404(Notificacion, id=notificacion_id, usuario=request.user)
    importante = notificacion.toggle_importante()
    
    return JsonResponse({'success': True, 'importante': importante})

@login_required
def lista_notificaciones(request):
    """
    Vista completa de TODAS las notificaciones (leídas y no leídas).
    Permite filtrar por estado.
    """
    # Obtener filtro
    filtro = request.GET.get('filtro', 'todas')
    
    # Consulta base
    notificaciones = Notificacion.objects.filter(usuario=request.user)
    
    # Aplicar filtros
    if filtro == 'no_leidas':
        notificaciones = notificaciones.filter(leida=False)
    elif filtro == 'importantes':
        notificaciones = notificaciones.filter(importante=True)
    
    # Estadísticas
    total = Notificacion.objects.filter(usuario=request.user).count()
    no_leidas = Notificacion.objects.filter(usuario=request.user, leida=False).count()
    importantes = Notificacion.objects.filter(usuario=request.user, importante=True).count()
    
    return render(request, 'notificaciones/lista.html', {
        'notificaciones': notificaciones,
        'filtro_actual': filtro,
        'stats': {
            'total': total,
            'no_leidas': no_leidas,
            'importantes': importantes
        }
    })

@login_required
@require_POST
def limpiar_notificaciones(request):
    """
    Elimina manualmente las notificaciones antiguas (leídas, no importantes, +6 meses).
    También puede ejecutarse automáticamente con un cron job.
    """
    cantidad = Notificacion.limpiar_notificaciones_antiguas()
    
    return JsonResponse({
        'success': True, 
        'eliminadas': cantidad,
        'mensaje': f'Se eliminaron {cantidad} notificaciones antiguas.'
    })

# Función auxiliar
def calcular_tiempo_transcurrido(fecha):
    """Calcula el tiempo transcurrido de forma legible"""
    ahora = timezone.now()
    diferencia = ahora - fecha
    
    segundos = diferencia.total_seconds()
    minutos = segundos / 60
    horas = minutos / 60
    dias = diferencia.days
    
    if segundos < 60:
        return "Justo ahora"
    elif minutos < 60:
        return f"Hace {int(minutos)} min"
    elif horas < 24:
        return f"Hace {int(horas)} h"
    elif dias == 1:
        return "Ayer"
    elif dias < 7:
        return f"Hace {dias} días"
    elif dias < 30:
        semanas = dias // 7
        return f"Hace {semanas} {'semana' if semanas == 1 else 'semanas'}"
    elif dias < 365:
        meses = dias // 30
        return f"Hace {meses} {'mes' if meses == 1 else 'meses'}"
    else:
        años = dias // 365
        return f"Hace {años} {'año' if años == 1 else 'años'}"