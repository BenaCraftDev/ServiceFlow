from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_http_methods
from django.utils import timezone
from django.db.models import Q
from datetime import datetime, timedelta
from .models import Notificacion

# ============================================
# VISTAS ORIGINALES DE NOTIFICACIONES
# ============================================

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


# ============================================
# VISTAS DEL CALENDARIO
# ============================================

# Importar modelos necesarios (agregar estos imports al principio del archivo si no existen)
try:
    from .models import NotaCalendario
except ImportError:
    NotaCalendario = None

try:
    from cotizaciones.models import Cotizacion, Material, RegistroMantenimiento
except ImportError:
    Cotizacion = None
    Material = None
    RegistroMantenimiento = None

@login_required
def vista_calendario(request):
    """
    Vista principal del calendario
    """
    return render(request, 'notificaciones/calendario.html')

@login_required
def obtener_eventos_calendario(request):
    """
    API endpoint que devuelve todos los eventos del mes:
    - Trabajos (cotizaciones)
    - Mantenciones (materiales)
    - Préstamos (devoluciones)
    - Notas (personales)
    """
    from cotizaciones.models import Cotizacion, Material, PrestamoMaterial
    from datetime import timedelta
    
    try:
        mes = int(request.GET.get('mes', timezone.now().month))
        anio = int(request.GET.get('anio', timezone.now().year))
        
        # Fecha inicio y fin del mes
        fecha_inicio = datetime(anio, mes, 1).date()
        if mes == 12:
            fecha_fin = datetime(anio + 1, 1, 1).date()
        else:
            fecha_fin = datetime(anio, mes + 1, 1).date()
        
        # ============================================
        # 1. TRABAJOS - Cotizaciones con fecha
        # ============================================
        trabajos = Cotizacion.objects.filter(
            fecha_realizacion__isnull=False,
            fecha_realizacion__gte=fecha_inicio,
            fecha_realizacion__lt=fecha_fin
        ).exclude(
            estado__in=['borrador', 'rechazada', 'vencida']
        )
        
        trabajos_data = []
        for trabajo in trabajos:
            cliente_nombre = trabajo.cliente.nombre if trabajo.cliente else trabajo.cliente_nombre_respaldo or 'Sin cliente'
            
            trabajos_data.append({
                'id': trabajo.id,
                'numero': trabajo.numero,
                'referencia': trabajo.referencia or 'Sin referencia',
                'fecha': trabajo.fecha_realizacion.isoformat(),
                'cliente': cliente_nombre,
                'lugar': trabajo.lugar or 'Sin lugar',
                'estado': trabajo.estado
            })
        
        # ============================================
        # 2. MANTENCIONES - Materiales próximos
        # ============================================
        mantenciones_data = []
        try:
            # Obtener TODOS los materiales que requieren mantenimiento
            materiales_mantencion = Material.objects.filter(
                requiere_mantenimiento=True,
                fecha_ultimo_mantenimiento__isnull=False,
                dias_entre_mantenimiento__isnull=False
            )
            
            hoy = timezone.now().date()
            
            for material in materiales_mantencion:
                # CALCULAR la fecha próxima de mantenimiento
                fecha_proximo = material.fecha_ultimo_mantenimiento + timedelta(days=material.dias_entre_mantenimiento)
                
                # Verificar si está en el rango del mes
                if fecha_inicio <= fecha_proximo < fecha_fin:
                    dias_restantes = (fecha_proximo - hoy).days
                    
                    if dias_restantes < 0:
                        urgencia = 'vencida'
                        estado_texto = f'Vencida hace {abs(dias_restantes)} días'
                    elif dias_restantes <= 3:
                        urgencia = 'urgente'
                        estado_texto = f'Vence en {dias_restantes} días'
                    else:
                        urgencia = 'programada'
                        estado_texto = f'En {dias_restantes} días'
                    
                    mantenciones_data.append({
                        'material_id': material.id,
                        'material': material.nombre,
                        'codigo': material.codigo if hasattr(material, 'codigo') else '',
                        'tipo_mantenimiento': material.tipo_mantenimiento or 'Preventivo',
                        'fecha': fecha_proximo.isoformat(),
                        'urgencia': urgencia,
                        'estado_texto': estado_texto,
                        'descripcion': f"Mantención {material.tipo_mantenimiento or 'preventiva'} - {estado_texto}"
                    })
                    
        except Exception as e:
            import traceback
            print(f"⚠️  Error al cargar mantenciones: {e}")
            traceback.print_exc()
        
        # ============================================
        # 3. PRÉSTAMOS - Devoluciones programadas
        # ============================================
        prestamos_data = []
        try:
            prestamos = PrestamoMaterial.objects.filter(
                fecha_devolucion__gte=fecha_inicio,
                fecha_devolucion__lt=fecha_fin
            ).select_related('material', 'usuario_registro')
            
            for prestamo in prestamos:
                dias_restantes = prestamo.dias_restantes()
                
                if dias_restantes < 0:
                    urgencia = 'vencido'
                    estado_texto = f'Vencido hace {abs(dias_restantes)} días'
                elif dias_restantes <= 3:
                    urgencia = 'proximo'
                    estado_texto = f'Vence en {dias_restantes} días'
                else:
                    urgencia = 'programado'
                    estado_texto = f'En {dias_restantes} días'
                
                prestamos_data.append({
                    'id': prestamo.id,
                    'material': prestamo.material.nombre,
                    'codigo': prestamo.material.codigo,
                    'prestado_a': prestamo.prestado_a,
                    'fecha': prestamo.fecha_devolucion.isoformat(),
                    'fecha_prestamo': prestamo.fecha_prestamo.isoformat(),
                    'urgencia': urgencia,
                    'estado_texto': estado_texto,
                    'observaciones': prestamo.observaciones or '',
                    'descripcion': f"Devolución: {prestamo.material.codigo} - {prestamo.prestado_a}"
                })
        except Exception as e:
            print(f"⚠️  Error al cargar préstamos: {e}")
        
        # ============================================
        # 4. NOTAS - Notas personales del usuario
        # ============================================
        notas_data = []
        try:
            from .models import NotaCalendario
            notas = NotaCalendario.objects.filter(
                usuario=request.user,
                fecha__gte=fecha_inicio,
                fecha__lt=fecha_fin
            )
            
            for nota in notas:
                notas_data.append({
                    'id': nota.id,
                    'titulo': nota.titulo,
                    'descripcion': nota.descripcion or '',
                    'fecha': nota.fecha.isoformat(),
                    'prioridad': nota.prioridad,
                    'color': nota.color
                })
        except ImportError:
            pass
        except Exception as e:
            print(f"⚠️  Error al cargar notas: {e}")
        
        return JsonResponse({
            'trabajos': trabajos_data,
            'mantenciones': mantenciones_data,
            'prestamos': prestamos_data,
            'notas': notas_data
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': str(e),
            'trabajos': [],
            'mantenciones': [],
            'prestamos': [],
            'notas': []
        }, status=500)

@login_required
@require_POST
def crear_nota(request):
    """
    Crea una nueva nota en el calendario
    """
    try:
        from .models import NotaCalendario
        from datetime import datetime
        
        # Obtener la fecha como string y convertirla a date
        fecha_str = request.POST.get('fecha')
        fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        
        nota = NotaCalendario.objects.create(
            usuario=request.user,
            titulo=request.POST.get('titulo'),
            descripcion=request.POST.get('descripcion', ''),
            fecha=fecha_obj,  # ✅ Usar el objeto date
            prioridad=request.POST.get('prioridad', 'media'),
            color=request.POST.get('color', '#3b82f6')
        )
        
        return JsonResponse({
            'success': True,
            'nota': {
                'id': nota.id,
                'titulo': nota.titulo,
                'descripcion': nota.descripcion,
                'fecha': nota.fecha.isoformat(),  # ✅ Ahora sí es un objeto date
                'prioridad': nota.prioridad,
                'color': nota.color
            }
        })
    except ImportError:
        return JsonResponse({
            'success': False, 
            'error': 'Modelo NotaCalendario no disponible. Ejecuta las migraciones.'
        }, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False, 
            'error': str(e)
        }, status=400)

@login_required
@require_POST
def editar_nota(request, nota_id):
    """
    Edita una nota existente
    """
    try:
        from .models import NotaCalendario
        from datetime import datetime
        
        nota = get_object_or_404(NotaCalendario, id=nota_id, usuario=request.user)
        
        # Actualizar campos
        nota.titulo = request.POST.get('titulo', nota.titulo)
        nota.descripcion = request.POST.get('descripcion', nota.descripcion)
        
        # Convertir fecha string a date object
        fecha_str = request.POST.get('fecha')
        if fecha_str:
            nota.fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        
        nota.prioridad = request.POST.get('prioridad', nota.prioridad)
        nota.color = request.POST.get('color', nota.color)
        nota.save()
        
        return JsonResponse({
            'success': True,
            'nota': {
                'id': nota.id,
                'titulo': nota.titulo,
                'descripcion': nota.descripcion,
                'fecha': nota.fecha.isoformat(),
                'prioridad': nota.prioridad,
                'color': nota.color
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False, 
            'error': str(e)
        }, status=400)

@login_required
def obtener_nota(request, nota_id):
    """
    Obtiene los datos de una nota específica
    """
    if NotaCalendario is None:
        return JsonResponse({'error': 'Modelo NotaCalendario no disponible'}, status=400)
    
    nota = get_object_or_404(NotaCalendario, id=nota_id, usuario=request.user)
    
    return JsonResponse({
        'id': nota.id,
        'titulo': nota.titulo,
        'descripcion': nota.descripcion,
        'fecha': nota.fecha.isoformat(),
        'prioridad': nota.prioridad,
        'color': nota.color
    })

@login_required
@require_POST
def eliminar_nota(request, nota_id):
    """
    Elimina una nota del calendario
    """
    if NotaCalendario is None:
        return JsonResponse({'success': False, 'error': 'Modelo NotaCalendario no disponible'}, status=400)
    
    try:
        nota = get_object_or_404(NotaCalendario, id=nota_id, usuario=request.user)
        nota.delete()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
def obtener_notas_rango(request):
    """
    Obtiene todas las notas del usuario en un rango de fechas
    Útil para exportar o ver resumen
    """
    if NotaCalendario is None:
        return JsonResponse({'notas': []})
    
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    
    notas = NotaCalendario.objects.filter(usuario=request.user)
    
    if fecha_inicio:
        notas = notas.filter(fecha__gte=fecha_inicio)
    if fecha_fin:
        notas = notas.filter(fecha__lte=fecha_fin)
    
    prioridad = request.GET.get('prioridad')
    if prioridad:
        notas = notas.filter(prioridad=prioridad)
    
    notas_data = [{
        'id': n.id,
        'titulo': n.titulo,
        'descripcion': n.descripcion,
        'fecha': n.fecha.isoformat(),
        'prioridad': n.prioridad,
        'color': n.color,
        'es_pasado': n.es_pasado,
        'es_hoy': n.es_hoy,
        'es_urgente': n.es_urgente
    } for n in notas]
    
    return JsonResponse({'notas': notas_data})

@login_required
def estadisticas_calendario(request):
    """
    Devuelve estadísticas del calendario del usuario
    """
    hoy = timezone.now().date()
    
    # Notas
    notas_totales = 0
    notas_pendientes = 0
    notas_urgentes = 0
    
    if NotaCalendario is not None:
        notas_totales = NotaCalendario.objects.filter(usuario=request.user).count()
        notas_pendientes = NotaCalendario.objects.filter(usuario=request.user, fecha__gte=hoy).count()
        notas_urgentes = NotaCalendario.objects.filter(
            usuario=request.user,
            prioridad='alta',
            fecha__gte=hoy,
            fecha__lte=hoy + timedelta(days=3)
        ).count()
    
    # Trabajos (si el usuario tiene permisos)
    trabajos_mes = 0
    mantenciones_mes = 0
    
    if Cotizacion is not None and (request.user.is_staff or hasattr(request.user, 'grupos')):
        primer_dia_mes = hoy.replace(day=1)
        if hoy.month == 12:
            ultimo_dia_mes = datetime(hoy.year + 1, 1, 1).date()
        else:
            ultimo_dia_mes = datetime(hoy.year, hoy.month + 1, 1).date()
        
        trabajos_mes = Cotizacion.objects.filter(
            estado='aprobada',
            fecha_realizacion__gte=primer_dia_mes,
            fecha_realizacion__lt=ultimo_dia_mes
        ).count()
        
        if Material is not None:
            mantenciones_mes = Material.objects.filter(
                requiere_mantenimiento=True,
                fecha_proximo_mantenimiento__gte=primer_dia_mes,
                fecha_proximo_mantenimiento__lt=ultimo_dia_mes
            ).count()
    
    return JsonResponse({
        'notas': {
            'totales': notas_totales,
            'pendientes': notas_pendientes,
            'urgentes': notas_urgentes
        },
        'trabajos_mes': trabajos_mes,
        'mantenciones_mes': mantenciones_mes
    })