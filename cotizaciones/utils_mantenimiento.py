from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Q
import math
import hashlib


def calcular_dias_alerta(dias_entre_mantenimiento):
    if dias_entre_mantenimiento >= 365:
        return 30
    elif dias_entre_mantenimiento >= 30:
        return 7
    else:
        return math.ceil(dias_entre_mantenimiento * 0.25)


def obtener_estado_material(material):
    # Verificar datos necesarios
    if not material.requiere_mantenimiento or not material.activo:
        return {'estado': 'sin_datos', 'dias': None, 'dias_alerta': None, 'hash': None}
    
    if not material.fecha_ultimo_mantenimiento or not material.dias_entre_mantenimiento:
        return {'estado': 'sin_datos', 'dias': None, 'dias_alerta': None, 'hash': None}
    
    # Calcular días hasta próximo mantenimiento
    dias = material.dias_hasta_proximo_mantenimiento()
    
    if dias is None:
        return {'estado': 'sin_datos', 'dias': None, 'dias_alerta': None, 'hash': None}
    
    # ⭐ PRIORIDAD: Manual primero, automático si no existe
    if material.dias_alerta_previa and material.dias_alerta_previa > 0:
        dias_alerta = material.dias_alerta_previa
        origen_alerta = 'manual'
    else:
        dias_alerta = calcular_dias_alerta(material.dias_entre_mantenimiento)
        origen_alerta = 'automatico'
    
    # Determinar estado
    if dias < 0:
        estado = 'vencido'
    elif dias <= dias_alerta:
        estado = 'proximo'
    else:
        estado = 'ok'
    
    # Hash para detectar cambios
    estado_str = f"{material.id}:{estado}:{dias}"
    estado_hash = hashlib.md5(estado_str.encode()).hexdigest()
    
    return {
        'estado': estado,
        'dias': dias,
        'dias_alerta': dias_alerta,
        'origen_alerta': origen_alerta,  # 'manual' o 'automatico'
        'hash': estado_hash
    }


def verificar_mantenimientos_materiales(request):
    if not request.user.is_authenticated:
        return
    
    # Verificar admin
    es_admin = request.user.is_superuser
    
    try:
        if hasattr(request.user, 'perfilempleado'):
            es_admin = es_admin or request.user.perfilempleado.cargo == 'admin'
        elif hasattr(request.user, 'perfil'):
            es_admin = es_admin or request.user.perfil.cargo == 'admin'
    except:
        pass
    
    if not es_admin:
        return
    
    # Importar modelos
    from .models import Material
    from notificaciones.models import Notificacion
    
    # Obtener materiales
    materiales = Material.objects.filter(
        requiere_mantenimiento=True,
        activo=True,
        fecha_ultimo_mantenimiento__isnull=False,
        dias_entre_mantenimiento__isnull=False
    )
    
    # Obtener administradores
    administradores = User.objects.filter(is_superuser=True, is_active=True)
    
    try:
        try:
            from home.models import PerfilEmpleado
        except ImportError:
            from .models import PerfilEmpleado
        admins_perfil = User.objects.filter(perfilempleado__cargo='admin', is_active=True)
        administradores = administradores | admins_perfil
    except:
        pass
    
    try:
        admins_perfil_alt = User.objects.filter(perfil__cargo='admin', is_active=True)
        administradores = administradores | admins_perfil_alt
    except:
        pass
    
    if not administradores.exists():
        return
    
    # Estados guardados
    estados_guardados = request.session.get('estados_materiales_mantenimiento', {})
    estados_actuales = {}
    
    # Procesar cada material
    for material in materiales:
        info_estado = obtener_estado_material(material)
        
        if info_estado['estado'] == 'sin_datos':
            continue
        
        # Si está ok
        if info_estado['estado'] == 'ok':
            estados_actuales[str(material.id)] = info_estado['hash']
            
            # Limpiar notificaciones antiguas
            Notificacion.objects.filter(
                Q(titulo__icontains=material.codigo) & Q(titulo__icontains='Mantenimiento'),
                leida=False
            ).delete()
            
            continue
        
        # Guardar estado actual
        estados_actuales[str(material.id)] = info_estado['hash']
        
        # Obtener estado anterior
        estado_anterior = estados_guardados.get(str(material.id), None)
        
        # Si cambió, notificar
        if estado_anterior != info_estado['hash']:
            # Limpiar notificaciones antiguas
            Notificacion.objects.filter(
                Q(titulo__icontains=material.codigo) & Q(titulo__icontains='Mantenimiento'),
                leida=False
            ).delete()
            
            # Crear notificaciones
            modo = "manual" if info_estado['origen_alerta'] == 'manual' else "automático"
            
            for admin in administradores:
                if info_estado['estado'] == 'vencido':
                    Notificacion.objects.create(
                        usuario=admin,
                        titulo=f'🚨 URGENTE: Mantenimiento VENCIDO - {material.codigo}',
                        mensaje=f'El material "{material.nombre}" tiene su mantenimiento vencido hace {abs(info_estado["dias"])} día(s). Margen de alerta ({modo}): {info_estado["dias_alerta"]} días.',
                        tipo='danger',
                        url=f'/cotizaciones/materiales/?buscar={material.codigo}'
                    )
                else:  # 'proximo'
                    Notificacion.objects.create(
                        usuario=admin,
                        titulo=f'⚠️ Mantenimiento próximo - {material.codigo}',
                        mensaje=f'El material "{material.nombre}" necesitará mantenimiento en {info_estado["dias"]} día(s). Margen de alerta ({modo}): {info_estado["dias_alerta"]} días.',
                        tipo='warning',
                        url=f'/cotizaciones/materiales/?buscar={material.codigo}'
                    )
    
    # Guardar estados
    request.session['estados_materiales_mantenimiento'] = estados_actuales
    request.session.modified = True


def forzar_verificacion_mantenimientos(request):
    """Fuerza verificación limpiando estados guardados."""
    if 'estados_materiales_mantenimiento' in request.session:
        del request.session['estados_materiales_mantenimiento']
    verificar_mantenimientos_materiales(request)


def obtener_info_mantenimiento_material(material):
    """Obtiene información completa del mantenimiento."""
    info_estado = obtener_estado_material(material)
    
    return {
        'codigo': material.codigo,
        'nombre': material.nombre,
        'estado': info_estado['estado'],
        'dias_hasta_mantenimiento': info_estado['dias'],
        'dias_alerta_configurados': info_estado['dias_alerta'],
        'origen_alerta': info_estado.get('origen_alerta', 'automatico'),
        'dias_entre_mantenimiento': material.dias_entre_mantenimiento,
        'fecha_ultimo_mantenimiento': material.fecha_ultimo_mantenimiento,
        'requiere_notificacion': info_estado['estado'] in ['vencido', 'proximo']
    }


def obtener_todos_materiales_estado():
    """Obtiene estado de todos los materiales agrupados."""
    from .models import Material
    
    materiales = Material.objects.filter(
        requiere_mantenimiento=True,
        activo=True,
        fecha_ultimo_mantenimiento__isnull=False,
        dias_entre_mantenimiento__isnull=False
    )
    
    resultado = {
        'vencidos': [],
        'proximos': [],
        'ok': [],
        'sin_datos': []
    }
    
    for material in materiales:
        info = obtener_info_mantenimiento_material(material)
        resultado[info['estado']].append(info)
    
    # Ordenar
    resultado['vencidos'].sort(key=lambda x: x['dias_hasta_mantenimiento'])
    resultado['proximos'].sort(key=lambda x: x['dias_hasta_mantenimiento'])
    
    return resultado


def debug_verificacion_mantenimientos(request):
    """Debugging con información del sistema híbrido."""
    from .models import Material
    from notificaciones.models import Notificacion
    from django.contrib.auth.models import User
    
    debug_info = {
        'usuario_autenticado': request.user.is_authenticated,
        'usuario': str(request.user) if request.user.is_authenticated else 'Anónimo',
        'es_admin': False,
        'materiales_por_estado': {
            'vencidos': [],
            'proximos': [],
            'ok': [],
            'sin_datos': []
        },
        'administradores': [],
        'estados_en_sesion': {},
        'notificaciones_existentes': 0
    }
    
    if not request.user.is_authenticated:
        debug_info['error'] = 'Usuario no autenticado'
        return debug_info
    
    # Verificar admin
    es_admin = request.user.is_superuser
    
    if hasattr(request.user, 'perfilempleado'):
        debug_info['cargo'] = request.user.perfilempleado.cargo
        es_admin = es_admin or request.user.perfilempleado.cargo == 'admin'
    
    debug_info['es_admin'] = es_admin
    
    if not es_admin:
        debug_info['error'] = 'Usuario no es administrador'
        return debug_info
    
    # Obtener estados
    estados = obtener_todos_materiales_estado()
    debug_info['materiales_por_estado'] = estados
    
    # Administradores
    administradores = User.objects.filter(is_superuser=True, is_active=True)
    try:
        try:
            from home.models import PerfilEmpleado
        except ImportError:
            from .models import PerfilEmpleado
        admins_perfil = User.objects.filter(perfilempleado__cargo='admin', is_active=True)
        administradores = administradores | admins_perfil
    except:
        pass
    
    debug_info['administradores'] = [u.username for u in administradores]
    debug_info['estados_en_sesion'] = request.session.get('estados_materiales_mantenimiento', {})
    
    # Notificaciones
    notif_hoy = Notificacion.objects.filter(
        fecha_creacion__date=timezone.now().date()
    )
    debug_info['notificaciones_existentes'] = notif_hoy.count()
    debug_info['detalles_notificaciones'] = [
        {
            'usuario': n.usuario.username,
            'titulo': n.titulo,
            'tipo': n.tipo,
            'leida': n.leida
        } for n in notif_hoy
    ]
    
    return debug_info


def limpiar_notificaciones_material(material_codigo):
    """Limpia notificaciones de un material."""
    from notificaciones.models import Notificacion
    
    count = Notificacion.objects.filter(
        Q(titulo__icontains=material_codigo) & Q(titulo__icontains='Mantenimiento'),
        leida=False
    ).delete()[0]
    
    return count


def resetear_estado_material(request, material_id):
    """Resetea estado guardado de un material."""
    estados = request.session.get('estados_materiales_mantenimiento', {})
    
    if str(material_id) in estados:
        del estados[str(material_id)]
        request.session['estados_materiales_mantenimiento'] = estados
        request.session.modified = True






