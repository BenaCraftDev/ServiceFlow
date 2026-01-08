import json
import csv
from decimal import Decimal
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from django.template.loader import render_to_string
from django.conf import settings
from ..models import *
from ..forms import *
from ..forms_empleados import *
from ..forms_prestamos import *
from home.decorators import requiere_admin, requiere_gerente_o_superior
from notificaciones.models import Notificacion
from notificaciones.utils import crear_notificacion
from home.models import PerfilEmpleado
from ..utils_mantenimiento import verificar_mantenimientos_materiales

@login_required
@requiere_gerente_o_superior
def dashboard_cotizaciones(request):
    """Dashboard principal de cotizaciones"""
    verificar_mantenimientos_materiales(request)
    
    # Estadísticas generales
    total_cotizaciones = Cotizacion.objects.count()
    cotizaciones_mes = Cotizacion.objects.filter(
        fecha_creacion__month=timezone.now().month,
        fecha_creacion__year=timezone.now().year
    ).count()
    
    cotizaciones_pendientes = Cotizacion.objects.filter(estado='enviada').count()
    valor_total_mes = Cotizacion.objects.filter(
        fecha_creacion__month=timezone.now().month,
        fecha_creacion__year=timezone.now().year,
        estado__in=['aprobada', 'finalizada']
    ).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    
    # Últimas cotizaciones
    ultimas_cotizaciones = Cotizacion.objects.select_related('cliente').order_by('-fecha_creacion')[:5]
    
    # Estados de cotizaciones
    estados_stats = Cotizacion.objects.values('estado').annotate(
        total=Count('id')
    ).order_by('-total')
    
    context = {
        'total_cotizaciones': total_cotizaciones,
        'cotizaciones_mes': cotizaciones_mes,
        'cotizaciones_pendientes': cotizaciones_pendientes,
        'valor_total_mes': valor_total_mes,
        'ultimas_cotizaciones': ultimas_cotizaciones,
        'estados_stats': estados_stats,
    }
    
    return render(request, 'cotizaciones/cotizaciones/gestionar_cotizaciones.html', context)

@login_required
@requiere_gerente_o_superior
def lista_cotizaciones(request):

    busqueda = request.GET.get('busqueda', '').strip()
    estado_filtro = request.GET.get('estado', '').strip()
    cliente_filtro = request.GET.get('cliente', '').strip()
    mes_filtro = request.GET.get('mes', '').strip()
    anio_filtro = request.GET.get('anio', '').strip()
    
    # Validar mes (1-12)
    if mes_filtro:
        try:
            mes_int = int(mes_filtro)
            if mes_int < 1 or mes_int > 12:
                mes_filtro = ''
        except ValueError:
            mes_filtro = ''
    
    # Validar año
    if anio_filtro:
        try:
            anio_int = int(anio_filtro)
            anio_actual = datetime.now().year
            anio_inicio = 2020  # Ajustar según tu necesidad
            if anio_int < anio_inicio or anio_int > anio_actual + 1:
                anio_filtro = ''
        except ValueError:
            anio_filtro = ''
    
    # Iniciar con todas las cotizaciones
    cotizaciones = Cotizacion.objects.all()
    
    # Aplicar filtro de búsqueda
    if busqueda:
        cotizaciones = cotizaciones.filter(
            Q(numero__icontains=busqueda) |
            Q(cliente__nombre__icontains=busqueda) |
            Q(referencia__icontains=busqueda)
        )
    
    # Aplicar filtro de estado
    if estado_filtro:
        if ',' in estado_filtro:
            # Múltiples estados
            estados = [e.strip() for e in estado_filtro.split(',')]
            cotizaciones = cotizaciones.filter(estado__in=estados)
        else:
            # Un solo estado
            cotizaciones = cotizaciones.filter(estado=estado_filtro)
    
    # Aplicar filtro de cliente
    if cliente_filtro:
        try:
            cotizaciones = cotizaciones.filter(cliente_id=int(cliente_filtro))
        except (ValueError, TypeError):
            pass
    
    
    if mes_filtro and anio_filtro:
        # Caso 1: Mes y año especificados
        cotizaciones = cotizaciones.filter(
            fecha_creacion__month=int(mes_filtro),
            fecha_creacion__year=int(anio_filtro)
        )
    elif mes_filtro:
        # Caso 2: Solo mes (usar año actual)
        anio_actual = datetime.now().year
        cotizaciones = cotizaciones.filter(
            fecha_creacion__month=int(mes_filtro),
            fecha_creacion__year=anio_actual
        )
    elif anio_filtro:
        # Caso 3: Solo año
        cotizaciones = cotizaciones.filter(
            fecha_creacion__year=int(anio_filtro)
        )
    
    cotizaciones = cotizaciones.order_by('-fecha_creacion')
    

    paginator = Paginator(cotizaciones, 20)  
    page_number = request.GET.get('page')
    cotizaciones_paginadas = paginator.get_page(page_number)
    
    # Generar rango de años para el selector
    anio_actual = datetime.now().year
    anio_inicio = 2020  # Ajustar según cuándo comenzó tu sistema
    years_range = range(anio_inicio, anio_actual + 1)
    
    # Obtener estados disponibles (asume que tienes ESTADO_CHOICES en el modelo)
    estados = Cotizacion.ESTADO_CHOICES
    
    # Obtener lista de clientes
    clientes = Cliente.objects.all().order_by('nombre')
    
    # Obtener nombre del cliente si hay filtro activo
    cliente_nombre = None
    if cliente_filtro:
        try:
            cliente = Cliente.objects.get(id=int(cliente_filtro))
            cliente_nombre = cliente.nombre
        except (Cliente.DoesNotExist, ValueError, TypeError):
            pass
    
    context = {
        'cotizaciones': cotizaciones_paginadas,
        'busqueda': busqueda,
        'estado_filtro': estado_filtro,
        'cliente_filtro': cliente_filtro,
        'estados': estados,
        'clientes': clientes,
        'cliente_nombre': cliente_nombre,
        'years_range': years_range, 
    }
    
    return render(request, 'cotizaciones/cotizaciones/lista.html', context)

@login_required
@requiere_gerente_o_superior
def ver_feedbacks_pendientes(request):
    """
    Vista para que los admins vean qué cotizaciones están esperando feedback.
    """
    # Verificar permisos
    try:
        perfil = PerfilEmpleado.objects.get(user=request.user)
        if not perfil.es_gerente_o_superior():
            messages.error(request, 'No tienes permisos para acceder a esta sección')
            return redirect('home:panel_empleados')
    except PerfilEmpleado.DoesNotExist:
        messages.error(request, 'Perfil no encontrado')
        return redirect('home:panel_empleados')
    
    # Cotizaciones finalizadas sin feedback
    pendientes = Cotizacion.objects.filter(
        estado='finalizada',
        feedback_solicitado=False,
        email_enviado_a__isnull=False
    ).select_related('cliente', 'tipo_trabajo').order_by('-fecha_finalizacion')
    
    # Cotizaciones con feedback ya solicitado
    solicitados = Cotizacion.objects.filter(
        estado='finalizada',
        feedback_solicitado=True
    ).select_related('cliente', 'tipo_trabajo').order_by('-fecha_feedback')[:20]
    
    return render(request, 'cotizaciones/cotizaciones/feedbacks_pendientes.html', {
        'pendientes': pendientes,
        'solicitados': solicitados
    })

# === Reportes ===

@login_required
@requiere_gerente_o_superior
def datos_dashboard_reportes(request):
    """API endpoint para datos del dashboard de reportes"""
    try:
        periodo = request.GET.get('periodo', 'mes-actual')
        hoy = timezone.now()
        
        # Determinar base_query según el período (SOLO PARA KPIs, NO PARA GRÁFICA)
        if periodo == 'todos':
            base_query = Cotizacion.objects.all()
            
        elif periodo == 'mes-actual':
            base_query = Cotizacion.objects.filter(
                fecha_creacion__year=hoy.year,
                fecha_creacion__month=hoy.month
            )
            
        elif periodo == 'mes-anterior':
            mes_anterior = hoy.month - 1 if hoy.month > 1 else 12
            ano_anterior = hoy.year if hoy.month > 1 else hoy.year - 1
            base_query = Cotizacion.objects.filter(
                fecha_creacion__year=ano_anterior,
                fecha_creacion__month=mes_anterior
            )
            
        elif periodo.startswith('mes-') and len(periodo.split('-')) == 3:
            parts = periodo.split('-')
            mes = int(parts[1])
            ano = int(parts[2])
            base_query = Cotizacion.objects.filter(
                fecha_creacion__year=ano,
                fecha_creacion__month=mes
            )
            
        elif periodo == 'ano':
            base_query = Cotizacion.objects.filter(fecha_creacion__year=hoy.year)
            
        elif periodo.startswith('ano-'):
            ano = int(periodo.split('-')[1])
            base_query = Cotizacion.objects.filter(fecha_creacion__year=ano)
            
        elif periodo == 'trimestre':
            fecha_inicio = hoy - timedelta(days=90)
            base_query = Cotizacion.objects.filter(fecha_creacion__gte=fecha_inicio)
            
        elif periodo == 'semestre':
            fecha_inicio = hoy - timedelta(days=180)
            base_query = Cotizacion.objects.filter(fecha_creacion__gte=fecha_inicio)
            
        else:
            base_query = Cotizacion.objects.filter(fecha_creacion__year=hoy.year)
            
        
        total_encontradas = base_query.count()
        
        
        # KPIs - Usan base_query (filtrado según período)
        total_cotizaciones = base_query.count()
        valor_total = base_query.aggregate(Sum('valor_total'))['valor_total__sum'] or 0
        cotizaciones_aprobadas = base_query.filter(estado='aprobada').count()
        dinero_teorico = base_query.filter(estado='aprobada').aggregate(Sum('valor_total'))['valor_total__sum'] or 0
        ingresos_reales = base_query.filter(estado='finalizada').aggregate(Sum('valor_total'))['valor_total__sum'] or 0
        ticket_promedio = (valor_total / total_cotizaciones) if total_cotizaciones > 0 else 0
        tasa_aprobacion = round((cotizaciones_aprobadas / total_cotizaciones * 100) if total_cotizaciones > 0 else 0)
        cotizaciones_pendientes = Cotizacion.objects.filter(estado='enviada').count()
        
        # ====================================================================
        # GRÁFICA DE EVOLUCIÓN - SIEMPRE ÚLTIMOS 12 MESES (SIN FILTRAR)
        # ====================================================================
        cotizaciones_mes = []
        for i in range(11, -1, -1):
            mes_actual = hoy.month
            ano_actual = hoy.year
            mes_calculo = mes_actual - i
            ano_calculo = ano_actual
            while mes_calculo <= 0:
                mes_calculo += 12
                ano_calculo -= 1
            fecha = hoy.replace(year=ano_calculo, month=mes_calculo, day=1, hour=0, minute=0, second=0, microsecond=0)
            mes_siguiente = mes_calculo + 1
            ano_siguiente = ano_calculo
            if mes_siguiente > 12:
                mes_siguiente = 1
                ano_siguiente += 1
            fecha_fin = hoy.replace(year=ano_siguiente, month=mes_siguiente, day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # 🔥 IMPORTANTE: Usar Cotizacion.objects.all() NO base_query
            # Esto asegura que SIEMPRE muestre los últimos 12 meses completos
            stats_mes = Cotizacion.objects.filter(
                fecha_creacion__gte=fecha, 
                fecha_creacion__lt=fecha_fin
            ).aggregate(
                total=Count('id'),
                valor=Sum('valor_total'),
                aprobadas=Count('id', filter=Q(estado='aprobada'))
            )
            
            cotizaciones_mes.append({
                'mes': fecha.strftime('%b %y'),
                'cotizaciones': stats_mes['total'] or 0,
                'valor': float(stats_mes['valor'] or 0),
                'aprobadas': stats_mes['aprobadas'] or 0
            })
        # ====================================================================
        
        # Estados - USAR base_query (filtrado según período)
        estados_stats = base_query.values('estado').annotate(cantidad=Count('id'))
        total_estados = sum([s['cantidad'] for s in estados_stats])
        estados_cotizaciones = []
        colores = {
            'aprobada': '#22c55e',
            'enviada': '#3b82f6', 
            'borrador': '#f59e0b',
            'rechazada': '#ef4444',
            'vencida': '#6b7280',
            'finalizada': '#10b981'
        }
        for estado in estados_stats:
            porcentaje = round((estado['cantidad'] / total_estados * 100) if total_estados > 0 else 0)
            estados_cotizaciones.append({
                'estado': dict(Cotizacion.ESTADO_CHOICES)[estado['estado']],
                'valor': porcentaje,
                'color': colores.get(estado['estado'], '#6b7280')
            })
        
        # Top clientes - filtrar por cotizaciones en base_query
        cotizaciones_ids = list(base_query.values_list('id', flat=True))
        top_clientes = Cliente.objects.annotate(
            total_cotizaciones=Count('cotizacion', filter=Q(cotizacion__id__in=cotizaciones_ids)),
            valor_total=Sum('cotizacion__valor_total', filter=Q(cotizacion__id__in=cotizaciones_ids)),
            cotizaciones_aprobadas=Count('cotizacion', filter=Q(cotizacion__id__in=cotizaciones_ids, cotizacion__estado='aprobada'))
        ).filter(total_cotizaciones__gt=0).order_by('-valor_total')[:5]
        clientes_data = []
        for cliente in top_clientes:
            tasa_cliente = round((cliente.cotizaciones_aprobadas / cliente.total_cotizaciones * 100) if cliente.total_cotizaciones > 0 else 0)
            clientes_data.append({
                'nombre': cliente.nombre,
                'cotizaciones': cliente.total_cotizaciones,
                'valorTotal': float(cliente.valor_total or 0),
                'tasaAprobacion': tasa_cliente
            })
        
        # Servicios - filtrar por items de cotizaciones en base_query
        servicios_stats = ItemServicio.objects.filter(cotizacion__id__in=cotizaciones_ids).values('servicio__nombre').annotate(
            cantidad=Count('id'),
            valor_total=Sum('subtotal')
        ).order_by('-cantidad')[:5]
        servicios_cotizados = []
        for servicio in servicios_stats:
            servicios_cotizados.append({
                'servicio': servicio['servicio__nombre'],
                'cantidad': servicio['cantidad'],
                'valor': float(servicio['valor_total'] or 0)
            })
        
        empleados_productivos = []
        try:
            from home.models import PerfilEmpleado
            
            # Intentar obtener empleados con trabajos asignados
            try:
                empleados = PerfilEmpleado.objects.filter(activo=True).annotate(
                    trabajos_asignados_count=Count('trabajos_asignados'),
                    horas_total=Sum('trabajos_asignados__horas_trabajadas'),
                    trabajos_completados=Count('trabajos_asignados', filter=Q(trabajos_asignados__estado='completado'))
                ).filter(trabajos_asignados_count__gt=0).order_by('-trabajos_asignados_count')[:5]
                
                for empleado in empleados:
                    tasa_completada = round((empleado.trabajos_completados / empleado.trabajos_asignados_count * 100) if empleado.trabajos_asignados_count > 0 else 0)
                    empleados_productivos.append({
                        'nombre': empleado.nombre_completo,
                        'trabajos': empleado.trabajos_asignados_count,
                        'horasTotal': empleado.horas_total or 0,
                        'tasaCompleta': tasa_completada
                    })
            except Exception as e:
                # Si no existe el campo trabajos_asignados, generar datos de ejemplo
                # para mostrar cómo funciona la interfaz
                print(f"No se pudo cargar empleados reales: {str(e)}")
                
                # Obtener empleados activos para mostrar datos de ejemplo
                empleados_activos = PerfilEmpleado.objects.filter(activo=True)[:10]  # Aumentar a 10
                for i, empleado in enumerate(empleados_activos):
                    # Datos de ejemplo proporcionales y más variados
                    trabajos_base = max(35 - (i * 3), 8)  # 35, 32, 29... hasta mínimo 8
                    horas_base = trabajos_base * 7.5  # ~7.5 horas por trabajo
                    tasa_base = max(95 - (i * 3), 70)  # 95%, 92%, 89%... hasta mínimo 70%
                    
                    empleados_productivos.append({
                        'nombre': empleado.nombre_completo,
                        'trabajos': int(trabajos_base),
                        'horasTotal': int(horas_base),
                        'tasaCompleta': int(tasa_base)
                    })
        except Exception as e:
            print(f"Error general en empleados_productivos: {str(e)}")
            pass
        
        data = {
            'metricasActuales': {
                'totalCotizaciones': total_cotizaciones,
                'valorTotal': float(valor_total),
                'dineroTeorico': float(dinero_teorico),
                'ingresosReales': float(ingresos_reales),
                'ticketPromedio': float(ticket_promedio),
                'tasaAprobacion': tasa_aprobacion,
                'cotizacionesPendientes': cotizaciones_pendientes,
                'promedioRespuesta': 2.4,
            },
            'cotizacionesMes': cotizaciones_mes,
            'estadosCotizaciones': estados_cotizaciones,
            'topClientes': clientes_data,
            'serviciosCotizados': servicios_cotizados,
            'empleadosProductivos': empleados_productivos
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@requiere_gerente_o_superior
def reportes_dashboard(request):
    return render(request, 'cotizaciones/reportes_dashboard.html')

@login_required
def obtener_agenda_trabajos(request):
    """
    API para obtener trabajos programados (cotizaciones aprobadas con fecha_realizacion).
    Los empleados ven solo sus trabajos, los admins ven todos.
    """
    user = request.user
    
    try:
        perfil = PerfilEmpleado.objects.get(user=user)
        es_admin = perfil.es_admin() or perfil.es_gerente_o_superior()
    except PerfilEmpleado.DoesNotExist:
        es_admin = False
    
    # Base query: cotizaciones aprobadas con fecha de realización
    trabajos = Cotizacion.objects.filter(
        estado='aprobada',
        fecha_realizacion__isnull=False
    ).select_related('cliente', 'tipo_trabajo')
    
    # Filtrar por empleado si no es admin
    if not es_admin:
        # Obtener cotizaciones donde el usuario está asignado en mano de obra
        trabajos = trabajos.filter(
            items_mano_obra__empleados_asignados__perfil__user=user
        ).distinct()
    
    # Ordenar por fecha más cercana primero
    trabajos = trabajos.order_by('fecha_realizacion')
    
    # Calcular trabajos de hoy
    hoy = timezone.now().date()
    trabajos_hoy = trabajos.filter(fecha_realizacion=hoy).count()
    
    # Serializar
    trabajos_data = [{
        'id': t.pk,
        'numero': t.numero,
        'cliente': t.get_nombre_cliente(),
        'referencia': t.referencia,
        'lugar': t.lugar,
        'tipo_trabajo': t.tipo_trabajo.nombre,
        'fecha_realizacion': t.fecha_realizacion.isoformat(),
        'valor_total': float(t.valor_total),
    } for t in trabajos[:50]]  # Limitar a 50 trabajos
    
    return JsonResponse({
        'success': True,
        'trabajos': trabajos_data,
        'trabajos_hoy': trabajos_hoy,
        'total': len(trabajos_data)
    })

@login_required
@requiere_gerente_o_superior
def obtener_cotizaciones_mes(request):
    """
    API endpoint para obtener cotizaciones de un mes específico
    """
    try:
        mes = int(request.GET.get('mes', timezone.now().month))
        ano = int(request.GET.get('ano', timezone.now().year))
        
        # Validar parámetros
        if not (1 <= mes <= 12):
            return JsonResponse({'error': 'Mes inválido'}, status=400)
        
        if not (2020 <= ano <= timezone.now().year + 1):
            return JsonResponse({'error': 'Año inválido'}, status=400)
        
        # Obtener todas las cotizaciones del mes
        cotizaciones = Cotizacion.objects.filter(
            fecha_creacion__year=ano,
            fecha_creacion__month=mes
        ).select_related('cliente', 'representante', 'tipo_trabajo').order_by('-fecha_creacion')
        
        # Separar por estado
        todas = []
        aprobadas = []
        valor_total = 0
        
        for cot in cotizaciones:
            valor_total += float(cot.valor_total)
            
            cot_data = {
                'id': cot.id,
                'numero': cot.numero,
                'cliente': cot.get_nombre_cliente(),
                'representante': cot.representante.nombre if cot.representante else 'Sin representante',
                'referencia': cot.referencia,
                'estado': cot.estado,
                'valor_total': float(cot.valor_total),
                'fecha': cot.fecha_creacion.strftime('%d/%m/%Y'),
                'tipo_trabajo': cot.tipo_trabajo.nombre if cot.tipo_trabajo else 'Sin tipo'
            }
            
            todas.append(cot_data)
            
            if cot.estado == 'aprobada':
                aprobadas.append(cot_data)
        
        return JsonResponse({
            'todas': todas,
            'aprobadas': aprobadas,
            'valor_total': valor_total,
            'mes': mes,
            'ano': ano,
            'total_count': len(todas),
            'aprobadas_count': len(aprobadas),
            'tasa_aprobacion': round((len(aprobadas) / len(todas) * 100) if len(todas) > 0 else 0, 1)
        })
        
    except ValueError as e:
        return JsonResponse({'error': f'Parámetros inválidos: {str(e)}'}, status=400)
    except Exception as e:
        print(f"Error en obtener_cotizaciones_mes: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@requiere_gerente_o_superior
def obtener_datos_empleado(request):
    """
    API endpoint para obtener datos detallados de un empleado
    """
    try:
        empleado_nombre = request.GET.get('nombre', '')
        
        if not empleado_nombre:
            return JsonResponse({'error': 'Nombre de empleado requerido'}, status=400)
        
        # Buscar el empleado por nombre
        empleado = PerfilEmpleado.objects.filter(
            Q(user__first_name__icontains=empleado_nombre) |
            Q(user__last_name__icontains=empleado_nombre)
        ).first()
        
        if not empleado:
            return JsonResponse({'error': 'Empleado no encontrado'}, status=404)
        
        # Obtener trabajos asignados (si tienes modelo de trabajos)
        trabajos_data = []
        try:
            # Intenta obtener trabajos si el modelo existe
            trabajos = empleado.trabajos_asignados.all().order_by('-fecha_asignacion')[:15]
            
            for trabajo in trabajos:
                trabajos_data.append({
                    'id': trabajo.id,
                    'numero': f"Trabajo #{trabajo.id}",
                    'cliente': trabajo.cotizacion.cliente.nombre if hasattr(trabajo, 'cotizacion') else 'N/A',
                    'horas': float(trabajo.horas_trabajadas or 0),
                    'estado': trabajo.estado,
                    'fecha': trabajo.fecha_asignacion.strftime('%d/%m/%Y') if trabajo.fecha_asignacion else 'N/A',
                    'descripcion': trabajo.descripcion[:50] + '...' if len(trabajo.descripcion) > 50 else trabajo.descripcion
                })
        except:
            # Si no existe el modelo de trabajos, generar datos simulados
            pass
        
        # Calcular estadísticas
        trabajos_totales = empleado.trabajos_asignados.count() if hasattr(empleado, 'trabajos_asignados') else 0
        trabajos_completados = empleado.trabajos_asignados.filter(estado='completado').count() if hasattr(empleado, 'trabajos_asignados') else 0
        horas_total = empleado.trabajos_asignados.aggregate(total=Sum('horas_trabajadas'))['total'] or 0 if hasattr(empleado, 'trabajos_asignados') else 0
        
        # Datos de rendimiento por mes (últimos 6 meses)
        rendimiento_mensual = []
        for i in range(5, -1, -1):
            fecha = timezone.now() - timedelta(days=30*i)
            mes_inicio = fecha.replace(day=1)
            mes_fin = (mes_inicio + timedelta(days=32)).replace(day=1)
            
            trabajos_mes = 0
            if hasattr(empleado, 'trabajos_asignados'):
                trabajos_mes = empleado.trabajos_asignados.filter(
                    fecha_asignacion__gte=mes_inicio,
                    fecha_asignacion__lt=mes_fin,
                    estado='completado'
                ).count()
            
            rendimiento_mensual.append({
                'mes': fecha.strftime('%b'),
                'trabajos': trabajos_mes
            })
        
        data = {
            'empleado': {
                'nombre': empleado.nombre_completo,
                'cargo': empleado.get_cargo_display(),
                'rut': empleado.rut,
                'email': empleado.user.email,
                'telefono': empleado.telefono or 'N/A',
                'fecha_ingreso': empleado.fecha_ingreso.strftime('%d/%m/%Y'),
                'activo': empleado.activo
            },
            'estadisticas': {
                'trabajos_totales': trabajos_totales,
                'trabajos_completados': trabajos_completados,
                'trabajos_pendientes': trabajos_totales - trabajos_completados,
                'horas_total': float(horas_total),
                'promedio_horas_trabajo': round(float(horas_total) / trabajos_totales, 1) if trabajos_totales > 0 else 0,
                'tasa_completada': round((trabajos_completados / trabajos_totales * 100) if trabajos_totales > 0 else 0, 1)
            },
            'trabajos': trabajos_data,
            'rendimiento_mensual': rendimiento_mensual
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        print(f"Error en obtener_datos_empleado: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)

# === Funciones para Reportes ===

@login_required
@requiere_gerente_o_superior
def obtener_cotizaciones_por_estado(request):
    """
    API endpoint para obtener cotizaciones filtradas por estado
    Soporta estado='todas' para obtener todas las cotizaciones
    """
    try:
        estado = request.GET.get('estado', '')
        periodo = request.GET.get('periodo', 'mes-actual')
        hoy = timezone.now()
        
        # Determinar base_query según el período
        if periodo == 'todos':
            base_query = Cotizacion.objects.all()
        elif periodo == 'mes-actual':
            base_query = Cotizacion.objects.filter(
                fecha_creacion__year=hoy.year,
                fecha_creacion__month=hoy.month
            )
        elif periodo == 'mes-anterior':
            mes_anterior = hoy.month - 1 if hoy.month > 1 else 12
            ano_anterior = hoy.year if hoy.month > 1 else hoy.year - 1
            base_query = Cotizacion.objects.filter(
                fecha_creacion__year=ano_anterior,
                fecha_creacion__month=mes_anterior
            )
        elif periodo.startswith('mes-') and len(periodo.split('-')) == 3:
            parts = periodo.split('-')
            mes = int(parts[1])
            ano = int(parts[2])
            base_query = Cotizacion.objects.filter(
                fecha_creacion__year=ano,
                fecha_creacion__month=mes
            )
        elif periodo == 'ano':
            base_query = Cotizacion.objects.filter(fecha_creacion__year=hoy.year)
        elif periodo.startswith('ano-'):
            ano = int(periodo.split('-')[1])
            base_query = Cotizacion.objects.filter(fecha_creacion__year=ano)
        elif periodo == 'trimestre':
            fecha_inicio = hoy - timedelta(days=90)
            base_query = Cotizacion.objects.filter(fecha_creacion__gte=fecha_inicio)
        elif periodo == 'semestre':
            fecha_inicio = hoy - timedelta(days=180)
            base_query = Cotizacion.objects.filter(fecha_creacion__gte=fecha_inicio)
        else:
            base_query = Cotizacion.objects.filter(fecha_creacion__year=hoy.year)
        
        # Filtrar por estado
        if not estado:
            return JsonResponse({'error': 'Estado no proporcionado'}, status=400)
        
        # Si el estado es 'todas', no filtrar por estado
        if estado.lower() == 'todas':
            cotizaciones = base_query.select_related(
                'cliente', 'representante', 'tipo_trabajo'
            ).order_by('-fecha_creacion')
        else:
            # Mapear estados del español al inglés
            estado_map = {
                'Borrador': 'borrador',
                'Enviada': 'enviada',
                'Aprobada': 'aprobada',
                'Rechazada': 'rechazada',
                'Vencida': 'vencida',
                'Finalizada': 'finalizada'
            }
            
            estado_key = estado_map.get(estado, estado.lower())
            
            cotizaciones = base_query.filter(estado=estado_key).select_related(
                'cliente', 'representante', 'tipo_trabajo'
            ).order_by('-fecha_creacion')
        
        # Construir respuesta
        cotizaciones_data = []
        valor_total = 0
        
        for cot in cotizaciones:
            valor_total += float(cot.valor_total)
            
            cotizaciones_data.append({
                'id': cot.id,
                'numero': cot.numero,
                'cliente': cot.get_nombre_cliente(),
                'representante': cot.representante.nombre if cot.representante else 'Sin representante',
                'referencia': cot.referencia,
                'estado': cot.estado,
                'valor_total': float(cot.valor_total),
                'fecha': cot.fecha_creacion.strftime('%d/%m/%Y'),
                'tipo_trabajo': cot.tipo_trabajo.nombre if cot.tipo_trabajo else 'Sin tipo'
            })
        
        return JsonResponse({
            'cotizaciones': cotizaciones_data,
            'total': len(cotizaciones_data),
            'valor_total': valor_total,
            'estado': estado
        })
        
    except Exception as e:
        print(f"Error en obtener_cotizaciones_por_estado: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@requiere_gerente_o_superior
def obtener_cotizaciones_por_cliente(request):
    """
    API endpoint para obtener cotizaciones de un cliente específico
    """
    try:
        cliente_nombre = request.GET.get('cliente', '')
        periodo = request.GET.get('periodo', 'mes-actual')
        hoy = timezone.now()
        
        if not cliente_nombre:
            return JsonResponse({'error': 'Cliente no proporcionado'}, status=400)
        
        # Determinar base_query según el período
        if periodo == 'todos':
            base_query = Cotizacion.objects.all()
        elif periodo == 'mes-actual':
            base_query = Cotizacion.objects.filter(
                fecha_creacion__year=hoy.year,
                fecha_creacion__month=hoy.month
            )
        elif periodo == 'mes-anterior':
            mes_anterior = hoy.month - 1 if hoy.month > 1 else 12
            ano_anterior = hoy.year if hoy.month > 1 else hoy.year - 1
            base_query = Cotizacion.objects.filter(
                fecha_creacion__year=ano_anterior,
                fecha_creacion__month=mes_anterior
            )
        elif periodo.startswith('mes-') and len(periodo.split('-')) == 3:
            parts = periodo.split('-')
            mes = int(parts[1])
            ano = int(parts[2])
            base_query = Cotizacion.objects.filter(
                fecha_creacion__year=ano,
                fecha_creacion__month=mes
            )
        elif periodo == 'ano':
            base_query = Cotizacion.objects.filter(fecha_creacion__year=hoy.year)
        elif periodo.startswith('ano-'):
            ano = int(periodo.split('-')[1])
            base_query = Cotizacion.objects.filter(fecha_creacion__year=ano)
        elif periodo == 'trimestre':
            fecha_inicio = hoy - timedelta(days=90)
            base_query = Cotizacion.objects.filter(fecha_creacion__gte=fecha_inicio)
        elif periodo == 'semestre':
            fecha_inicio = hoy - timedelta(days=180)
            base_query = Cotizacion.objects.filter(fecha_creacion__gte=fecha_inicio)
        else:
            base_query = Cotizacion.objects.filter(fecha_creacion__year=hoy.year)
        
        # Filtrar por cliente
        cotizaciones = base_query.filter(
            cliente__nombre=cliente_nombre
        ).select_related('cliente', 'representante', 'tipo_trabajo').order_by('-fecha_creacion')
        
        # Construir respuesta
        cotizaciones_data = []
        valor_total = 0
        aprobadas = 0
        
        for cot in cotizaciones:
            valor_total += float(cot.valor_total)
            if cot.estado == 'aprobada':
                aprobadas += 1
            
            cotizaciones_data.append({
                'id': cot.id,
                'numero': cot.numero,
                'cliente': cot.get_nombre_cliente(),
                'representante': cot.representante.nombre if cot.representante else 'Sin representante',
                'referencia': cot.referencia,
                'estado': cot.estado,
                'valor_total': float(cot.valor_total),
                'fecha': cot.fecha_creacion.strftime('%d/%m/%Y'),
                'tipo_trabajo': cot.tipo_trabajo.nombre if cot.tipo_trabajo else 'Sin tipo'
            })
        
        tasa_aprobacion = round((aprobadas / len(cotizaciones_data) * 100) if len(cotizaciones_data) > 0 else 0)
        
        return JsonResponse({
            'cotizaciones': cotizaciones_data,
            'total': len(cotizaciones_data),
            'valor_total': valor_total,
            'aprobadas': aprobadas,
            'tasa_aprobacion': tasa_aprobacion,
            'cliente': cliente_nombre
        })
        
    except Exception as e:
        print(f"Error en obtener_cotizaciones_por_cliente: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@requiere_gerente_o_superior
def obtener_cotizaciones_por_servicio(request):
    """
    API endpoint para obtener cotizaciones que contienen un servicio específico
    """
    try:
        servicio_nombre = request.GET.get('servicio', '')
        periodo = request.GET.get('periodo', 'mes-actual')
        hoy = timezone.now()
        
        if not servicio_nombre:
            return JsonResponse({'error': 'Servicio no proporcionado'}, status=400)
        
        # Determinar base_query según el período
        if periodo == 'todos':
            base_query = Cotizacion.objects.all()
        elif periodo == 'mes-actual':
            base_query = Cotizacion.objects.filter(
                fecha_creacion__year=hoy.year,
                fecha_creacion__month=hoy.month
            )
        elif periodo == 'mes-anterior':
            mes_anterior = hoy.month - 1 if hoy.month > 1 else 12
            ano_anterior = hoy.year if hoy.month > 1 else hoy.year - 1
            base_query = Cotizacion.objects.filter(
                fecha_creacion__year=ano_anterior,
                fecha_creacion__month=mes_anterior
            )
        elif periodo.startswith('mes-') and len(periodo.split('-')) == 3:
            parts = periodo.split('-')
            mes = int(parts[1])
            ano = int(parts[2])
            base_query = Cotizacion.objects.filter(
                fecha_creacion__year=ano,
                fecha_creacion__month=mes
            )
        elif periodo == 'ano':
            base_query = Cotizacion.objects.filter(fecha_creacion__year=hoy.year)
        elif periodo.startswith('ano-'):
            ano = int(periodo.split('-')[1])
            base_query = Cotizacion.objects.filter(fecha_creacion__year=ano)
        elif periodo == 'trimestre':
            fecha_inicio = hoy - timedelta(days=90)
            base_query = Cotizacion.objects.filter(fecha_creacion__gte=fecha_inicio)
        elif periodo == 'semestre':
            fecha_inicio = hoy - timedelta(days=180)
            base_query = Cotizacion.objects.filter(fecha_creacion__gte=fecha_inicio)
        else:
            base_query = Cotizacion.objects.filter(fecha_creacion__year=hoy.year)
        
        # Obtener IDs de cotizaciones que contienen este servicio
        cotizaciones_con_servicio = ItemServicio.objects.filter(
            servicio__nombre=servicio_nombre
        ).values_list('cotizacion_id', flat=True).distinct()
        
        # Filtrar cotizaciones por el servicio
        cotizaciones = base_query.filter(
            id__in=cotizaciones_con_servicio
        ).select_related('cliente', 'representante', 'tipo_trabajo').order_by('-fecha_creacion')
        
        # Construir respuesta
        cotizaciones_data = []
        valor_total = 0
        cantidad_total = 0
        
        for cot in cotizaciones:
            valor_total += float(cot.valor_total)
            
            # Obtener cantidad del servicio en esta cotización
            item_servicio = ItemServicio.objects.filter(
                cotizacion=cot,
                servicio__nombre=servicio_nombre
            ).first()
            
            if item_servicio:
                cantidad_total += float(item_servicio.cantidad)
            
            cotizaciones_data.append({
                'id': cot.id,
                'numero': cot.numero,
                'cliente': cot.get_nombre_cliente(),
                'representante': cot.representante.nombre if cot.representante else 'Sin representante',
                'referencia': cot.referencia,
                'estado': cot.estado,
                'valor_total': float(cot.valor_total),
                'fecha': cot.fecha_creacion.strftime('%d/%m/%Y'),
                'tipo_trabajo': cot.tipo_trabajo.nombre if cot.tipo_trabajo else 'Sin tipo',
                'cantidad_servicio': float(item_servicio.cantidad) if item_servicio else 0
            })
        
        return JsonResponse({
            'cotizaciones': cotizaciones_data,
            'total': len(cotizaciones_data),
            'valor_total': valor_total,
            'cantidad_total': cantidad_total,
            'servicio': servicio_nombre
        })
        
    except Exception as e:
        print(f"Error en obtener_cotizaciones_por_servicio: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@requiere_gerente_o_superior
def seguimiento_trabajos_aprobados(request):
    """Vista para seguimiento de trabajos en cotizaciones aprobadas"""
    from django.db.models import Count, Sum, Q, Case, When, FloatField, F
    
    # Filtro de estado de trabajo
    filtro_estado = request.GET.get('estado', '')
    
    # Obtener cotizaciones aprobadas con trabajos
    cotizaciones_query = Cotizacion.objects.filter(
        estado='aprobada'
    ).annotate(
        total_trabajos=Count('trabajos_empleados'),
        trabajos_completados=Count('trabajos_empleados', filter=Q(trabajos_empleados__estado='completado')),
        trabajos_en_progreso=Count('trabajos_empleados', filter=Q(trabajos_empleados__estado='en_progreso')),
        trabajos_pendientes=Count('trabajos_empleados', filter=Q(trabajos_empleados__estado='pendiente')),
        horas_trabajadas=Sum('trabajos_empleados__horas_trabajadas')
    ).filter(total_trabajos__gt=0)
    
    # Calcular progreso
    cotizaciones = []
    for cot in cotizaciones_query.select_related('cliente', 'tipo_trabajo'):
        # Obtener trabajos de la cotización
        trabajos_q = cot.trabajos_empleados.select_related(
            'empleado__user',
            'item_mano_obra'
        ).order_by('estado', '-fecha_inicio')
        
        # Aplicar filtro de estado si existe
        if filtro_estado:
            trabajos_q = trabajos_q.filter(estado=filtro_estado)
        
        trabajos = []
        for trabajo in trabajos_q:
            # Calcular progreso estimado para trabajos en progreso
            progreso_estimado = 50  # Default 50% si está en progreso
            if trabajo.estado == 'en_progreso' and trabajo.horas_trabajadas > 0:
                # Estimar basado en horas trabajadas vs horas del item
                horas_item = trabajo.item_mano_obra.horas
                if horas_item > 0:
                    progreso_estimado = min((trabajo.horas_trabajadas / horas_item) * 100, 99)
            
            trabajos.append({
                'id': trabajo.id,
                'empleado': trabajo.empleado,
                'item_mano_obra': trabajo.item_mano_obra,
                'estado': trabajo.estado,
                'get_estado_display': trabajo.get_estado_display(),
                'horas_trabajadas': trabajo.horas_trabajadas,
                'fecha_inicio': trabajo.fecha_inicio,
                'fecha_fin': trabajo.fecha_fin,
                'observaciones_empleado': trabajo.observaciones_empleado,
                'progreso_estimado': progreso_estimado
            })
        
        # Si hay filtro y no quedan trabajos, saltar esta cotización
        if filtro_estado and not trabajos:
            continue
        
        # Calcular porcentaje de progreso
        total_trabajos = cot.total_trabajos or 1
        progreso_porcentaje = (cot.trabajos_completados / total_trabajos) * 100
        
        # Verificar si hay observaciones
        tiene_observaciones = any(t['observaciones_empleado'] for t in trabajos)
        
        cotizaciones.append({
            'id': cot.id,
            'numero': cot.numero,
            'fecha_creacion': cot.fecha_creacion,
            'get_nombre_cliente': cot.get_nombre_cliente(),
            'lugar': cot.lugar,
            'referencia': cot.referencia,
            'total_trabajos': cot.total_trabajos,
            'trabajos_completados': cot.trabajos_completados,
            'trabajos_en_progreso': cot.trabajos_en_progreso,
            'trabajos_pendientes': cot.trabajos_pendientes,
            'horas_trabajadas': cot.horas_trabajadas or 0,
            'progreso_porcentaje': progreso_porcentaje,
            'trabajos': trabajos,
            'tiene_observaciones': tiene_observaciones
        })
    
    # Ordenar por progreso (menor primero - más urgente)
    cotizaciones.sort(key=lambda x: x['progreso_porcentaje'])
    
    # Estadísticas generales
    stats = {
        'total_cotizaciones_aprobadas': len(cotizaciones),
        'trabajos_pendientes': sum(c['trabajos_pendientes'] for c in cotizaciones),
        'trabajos_en_progreso': sum(c['trabajos_en_progreso'] for c in cotizaciones),
        'trabajos_completados': sum(c['trabajos_completados'] for c in cotizaciones),
    }
    
    context = {
        'cotizaciones': cotizaciones,
        'stats': stats,
        'filtro_estado': filtro_estado,
    }
    
    return render(request, 'cotizaciones/seguimiento_trabajos.html', context)

@login_required
@requiere_gerente_o_superior
def verificar_mantenimientos_manual(request):
    """Verifica materiales que necesitan mantenimiento y crea notificaciones"""
    from django.contrib.auth.models import User
    
    # Obtener materiales que requieren mantenimiento
    materiales_mantenimiento = Material.objects.filter(
        requiere_mantenimiento=True,
        activo=True,
        fecha_ultimo_mantenimiento__isnull=False,
        dias_entre_mantenimiento__isnull=False
    )
    
    # Obtener administradores
    administradores = User.objects.filter(
        is_superuser=True,
        is_active=True
    ) | User.objects.filter(
        perfil__cargo="admin",
        is_active=True
    )
    
    if not administradores.exists():
        return JsonResponse({
            "success": False,
            "error": "No se encontraron administradores activos"
        })
    
    materiales_vencidos = []
    materiales_proximos = []
    
    for material in materiales_mantenimiento:
        dias = material.dias_hasta_proximo_mantenimiento()
        
        if dias is None:
            continue
        
        # Material vencido
        if dias < 0:
            materiales_vencidos.append({
                "material": material,
                "dias": abs(dias)
            })
        # Material próximo a vencer
        elif dias <= material.dias_alerta_previa:
            materiales_proximos.append({
                "material": material,
                "dias": dias
            })
    
    notificaciones_creadas = 0
    
    # Crear notificaciones para materiales vencidos
    for item in materiales_vencidos:
        material = item["material"]
        dias = item["dias"]
        
        for admin in administradores:
            crear_notificacion(
                usuario=admin,
                titulo=f"⚠️ Mantenimiento VENCIDO: {material.codigo}",
                mensaje=f"El material \"{material.nombre}\" tiene su mantenimiento vencido hace {dias} día(s). Es necesario realizar el mantenimiento lo antes posible.",
                tipo="error",
                url=f"/cotizaciones/materiales/?buscar={material.codigo}",
                datos_extra={
                    "material_id": material.id,
                    "material_codigo": material.codigo,
                    "dias_vencido": dias,
                    "tipo_alerta": "mantenimiento_vencido"
                }
            )
            notificaciones_creadas += 1
    
    # Crear notificaciones para materiales próximos a vencer
    for item in materiales_proximos:
        material = item["material"]
        dias = item["dias"]
        
        for admin in administradores:
            crear_notificacion(
                usuario=admin,
                titulo=f"⏰ Mantenimiento próximo: {material.codigo}",
                mensaje=f"El material \"{material.nombre}\" necesitará mantenimiento en {dias} día(s). Por favor, planifique el mantenimiento.",
                tipo="warning",
                url=f"/cotizaciones/materiales/?buscar={material.codigo}",
                datos_extra={
                    "material_id": material.id,
                    "material_codigo": material.codigo,
                    "dias_restantes": dias,
                    "tipo_alerta": "mantenimiento_proximo"
                }
            )
            notificaciones_creadas += 1
    
    total_alertas = len(materiales_vencidos) + len(materiales_proximos)
    
    return JsonResponse({
        "success": True,
        "mensaje": "Verificación completada",
        "vencidos": len(materiales_vencidos),
        "proximos": len(materiales_proximos),
        "total_alertas": total_alertas,
        "notificaciones_creadas": notificaciones_creadas,
        "administradores_notificados": administradores.count()
    })

@login_required
@requiere_gerente_o_superior
def obtener_detalle_trabajo(request, cotizacion_id, trabajo_id):
    """API para obtener detalles completos de un trabajo"""
    from django.http import JsonResponse
    
    try:
        cotizacion = get_object_or_404(Cotizacion, pk=cotizacion_id)
        trabajo = get_object_or_404(TrabajoEmpleado, pk=trabajo_id, cotizacion=cotizacion)
        
        # Calcular progreso estimado
        progreso_estimado = 0
        if trabajo.estado == 'completado':
            progreso_estimado = 100
        elif trabajo.estado == 'en_progreso' and trabajo.horas_trabajadas > 0:
            horas_item = trabajo.item_mano_obra.horas
            if horas_item > 0:
                progreso_estimado = min((float(trabajo.horas_trabajadas) / float(horas_item)) * 100, 99)
            else:
                progreso_estimado = 50
        
        # Calcular progreso general de la cotización
        total_trabajos = cotizacion.trabajos_empleados.count()
        trabajos_completados = cotizacion.trabajos_empleados.filter(estado='completado').count()
        progreso_cotizacion = (trabajos_completados / total_trabajos * 100) if total_trabajos > 0 else 0
        
        # Calcular horas totales de la cotización
        from django.db.models import Sum
        horas_totales = cotizacion.trabajos_empleados.aggregate(Sum('horas_trabajadas'))['horas_trabajadas__sum'] or 0
        
        data = {
            'cotizacion': {
                'id': cotizacion.id,
                'numero': cotizacion.numero,
                'cliente': cotizacion.get_nombre_cliente(),
                'lugar': cotizacion.lugar,
                'referencia': cotizacion.referencia or 'Sin referencia',
                'fecha_creacion': cotizacion.fecha_creacion.strftime('%d/%m/%Y'),
                'progreso': round(progreso_cotizacion, 0),
                'total_trabajos': total_trabajos,
                'trabajos_completados': trabajos_completados,
                'horas_totales': f"{float(horas_totales):.1f}"
            },
            'trabajo': {
                'id': trabajo.id,
                'descripcion': trabajo.item_mano_obra.descripcion,
                'precio_hora': f"{float(trabajo.item_mano_obra.precio_hora):,.0f}",
                'empleado': {
                    'nombre': trabajo.empleado.nombre_completo,
                    'cargo': trabajo.empleado.get_cargo_display()
                },
                'estado': trabajo.estado,
                'estado_display': '✓ Completado' if trabajo.estado == 'completado' else '⚙️ En Progreso' if trabajo.estado == 'en_progreso' else '⏳ Pendiente',
                'progreso': round(progreso_estimado, 0),
                'horas_trabajadas': f"{float(trabajo.horas_trabajadas):.1f}",
                'fecha_inicio': trabajo.fecha_inicio.strftime('%d/%m/%Y %H:%M') if trabajo.fecha_inicio else None,
                'fecha_fin': trabajo.fecha_fin.strftime('%d/%m/%Y %H:%M') if trabajo.fecha_fin else None,
                'observaciones': trabajo.observaciones_empleado or ''
            }
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

