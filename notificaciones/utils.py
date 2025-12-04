from django.contrib.auth.models import User

def crear_notificacion(usuario, titulo, mensaje, tipo='info', url=None, **kwargs):
    """
    Crea una notificación para un usuario
    
    Params:
    - usuario: User object o user_id
    - titulo: str
    - mensaje: str
    - tipo: 'info', 'success', 'warning', 'danger'
    - url: str (opcional) - URL a donde redirigir al hacer click
    - **kwargs: cualquier otro parámetro (como datos_extra) se ignora automáticamente
    
    Returns:
    - Notificacion object o None si hay error
    """
    from .models import Notificacion
    
    # Convertir usuario_id a User object si es necesario
    if isinstance(usuario, int):
        try:
            usuario = User.objects.get(id=usuario)
        except User.DoesNotExist:
            print(f"❌ Error: Usuario con id {usuario} no existe")
            return None
    
    # Crear notificación ignorando kwargs adicionales
    try:
        notificacion = Notificacion.objects.create(
            usuario=usuario,
            titulo=titulo,
            mensaje=mensaje,
            tipo=tipo,
            url=url if url else None
        )
        return notificacion
    except Exception as e:
        print(f"❌ Error al crear notificación: {e}")
        return None


def notificar_cotizacion_creada(cotizacion, usuario_creador):
    """Notifica cuando se crea una cotización"""
    return crear_notificacion(
        usuario=usuario_creador,
        titulo='📝 Cotización Creada',
        mensaje=f'Se creó la cotización #{cotizacion.numero} para {cotizacion.get_nombre_cliente()}',
        tipo='success',
        url=f'/cotizaciones/detalle/{cotizacion.id}/'
    )


def notificar_cotizacion_aprobada(cotizacion, usuario):
    """Notifica cuando se aprueba una cotización"""
    return crear_notificacion(
        usuario=usuario,
        titulo='✅ Cotización Aprobada',
        mensaje=f'La cotización #{cotizacion.numero} ha sido aprobada',
        tipo='success',
        url=f'/cotizaciones/detalle/{cotizacion.id}/'
    )


def notificar_cotizacion_rechazada(cotizacion, usuario):
    """Notifica cuando se rechaza una cotización"""
    return crear_notificacion(
        usuario=usuario,
        titulo='❌ Cotización Rechazada',
        mensaje=f'La cotización #{cotizacion.numero} ha sido rechazada',
        tipo='warning',
        url=f'/cotizaciones/detalle/{cotizacion.id}/'
    )


def notificar_cotizacion_vencida(cotizacion, usuario):
    """Notifica cuando vence una cotización"""
    return crear_notificacion(
        usuario=usuario,
        titulo='⏰ Cotización Vencida',
        mensaje=f'La cotización #{cotizacion.numero} ha vencido',
        tipo='danger',
        url=f'/cotizaciones/detalle/{cotizacion.id}/'
    )


def notificar_a_todos_admins(titulo, mensaje, tipo='info', url=None):
    """Notifica a todos los administradores"""
    admins = User.objects.filter(is_staff=True)
    notificaciones = []
    for admin in admins:
        notif = crear_notificacion(admin, titulo, mensaje, tipo, url)
        if notif:
            notificaciones.append(notif)
    return notificaciones