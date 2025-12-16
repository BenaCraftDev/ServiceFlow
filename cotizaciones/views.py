import io
import json
import csv
from .forms_empleados import *
from .forms_prestamos import *
from .models import *
from .forms import *
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from home.decorators import requiere_admin, requiere_gerente_o_superior
from notificaciones.models import Notificacion
from notificaciones.utils import crear_notificacion
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from decimal import Decimal
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm, mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from home.models import PerfilEmpleado
from datetime import datetime, timedelta
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from .utils_mantenimiento import verificar_mantenimientos_materiales



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
def crear_cotizacion(request):
    """Crear nueva cotización"""
    if request.method == 'POST':
        form = CotizacionForm(request.POST)
        
        if form.is_valid():
            cotizacion = form.save(commit=False)
            cotizacion.creado_por = request.user
            
            # ⭐ GUARDAR FECHA_REALIZACION MANUALMENTE desde request.POST
            fecha_realizacion_str = request.POST.get('fecha_realizacion', '').strip()
            if fecha_realizacion_str:
                try:
                    from datetime import datetime
                    # Convertir string a fecha
                    cotizacion.fecha_realizacion = datetime.strptime(fecha_realizacion_str, '%Y-%m-%d').date()
                except ValueError as e:
                    cotizacion.fecha_realizacion = None
            else:
                cotizacion.fecha_realizacion = None
            
            cotizacion.save()
            cotizacion.generar_numero()
            cotizacion.save()
            
            messages.success(request, f'Cotización {cotizacion.numero} creada exitosamente.')
            return redirect('cotizaciones:editar', pk=cotizacion.pk)
        else:
            print("\n=== ERRORES DEL FORMULARIO ===")
            print(form.errors)
    else:
        form = CotizacionForm()
    
    return render(request, 'cotizaciones/cotizaciones/crear.html', {'form': form})

# Vistas para gestión de catálogos
@login_required
@requiere_gerente_o_superior
def gestionar_clientes(request):
    """Gestión de clientes"""
    clientes = Cliente.objects.all().order_by('nombre')
    
    busqueda = request.GET.get('busqueda', '')
    if busqueda:
        clientes = clientes.filter(
            Q(nombre__icontains=busqueda) |
            Q(rut__icontains=busqueda) |
            Q(email__icontains=busqueda)
        )
    
    paginator = Paginator(clientes, 20)
    page = request.GET.get('page')
    clientes = paginator.get_page(page)
    
    return render(request, 'cotizaciones/gestionar_clientes.html', {
        'clientes': clientes,
        'busqueda': busqueda
    })

@login_required
@requiere_gerente_o_superior
def gestionar_servicios(request):
    verificar_mantenimientos_materiales(request)
    """Gestión de servicios base"""
    servicios = ServicioBase.objects.select_related('categoria').order_by('categoria__nombre', 'nombre')
    categorias = CategoriaServicio.objects.filter(activo=True)
    
    categoria_filtro = request.GET.get('categoria', '')
    if categoria_filtro:
        servicios = servicios.filter(categoria_id=categoria_filtro)
    
    # Estadísticas adicionales
    servicios_parametrizables = servicios.filter(es_parametrizable=True).count()
    servicios_activos = servicios.filter(activo=True).count()
    
    return render(request, 'cotizaciones/gestionar_servicios.html', {
        'servicios': servicios,
        'categorias': categorias,
        'categoria_filtro': categoria_filtro,
        'servicios_parametrizables': servicios_parametrizables,
        'servicios_activos': servicios_activos,
    })

@login_required
@requiere_gerente_o_superior
def gestionar_materiales(request):
    verificar_mantenimientos_materiales(request)
    print(verificar_mantenimientos_materiales(request))
    """Gestión de materiales"""
    
    # Código original de la vista
    materiales = Material.objects.all().order_by('categoria', 'nombre')
    
    busqueda = request.GET.get('busqueda', '')
    categoria_filtro = request.GET.get('categoria', '')
    
    if busqueda:
        materiales = materiales.filter(
            Q(nombre__icontains=busqueda) |
            Q(codigo__icontains=busqueda) |
            Q(descripcion__icontains=busqueda)
        )
    
    if categoria_filtro:
        materiales = materiales.filter(categoria=categoria_filtro)
    
    categorias = Material.objects.values_list('categoria', flat=True).distinct().order_by('categoria')
    categorias = [cat for cat in categorias if cat]  # Filtrar valores vacíos
    
    # Estadísticas
    materiales_activos = materiales.filter(activo=True).count()
    precio_promedio = materiales.aggregate(promedio=models.Avg('precio_unitario'))['promedio'] or 0
    
    paginator = Paginator(materiales, 20)
    page = request.GET.get('page')
    materiales = paginator.get_page(page)
    
    return render(request, 'cotizaciones/gestionar_materiales.html', {
        'materiales': materiales,
        'categorias': categorias,
        'busqueda': busqueda,
        'categoria_filtro': categoria_filtro,
        'materiales_activos': materiales_activos,
        'precio_promedio': precio_promedio,
    })

@login_required
@requiere_gerente_o_superior
def aplicar_plantilla(request, cotizacion_pk, plantilla_pk):
    """Aplicar plantilla a cotización"""
    cotizacion = get_object_or_404(Cotizacion, pk=cotizacion_pk)
    plantilla = get_object_or_404(PlantillaCotizacion, pk=plantilla_pk)
    
    try:
        with transaction.atomic():
            # Agregar servicios de la plantilla
            for item_plantilla in plantilla.servicios.all():
                ItemServicio.objects.create(
                    cotizacion=cotizacion,
                    servicio=item_plantilla.servicio,
                    cantidad=item_plantilla.cantidad_default,
                    precio_unitario=item_plantilla.servicio.precio_base,
                    orden=item_plantilla.orden
                )
            
            # Recalcular totales
            cotizacion.calcular_totales()
            
        messages.success(request, f'Plantilla "{plantilla.nombre}" aplicada exitosamente.')
        
    except Exception as e:
        messages.error(request, f'Error al aplicar plantilla: {str(e)}')
    
    return redirect('cotizaciones:editar_cotizacion', pk=cotizacion_pk)

@login_required
@requiere_gerente_o_superior
def editar_cotizacion(request, pk):
    cotizacion = get_object_or_404(Cotizacion, pk=pk)
    
    if request.method == 'POST':
        form = CotizacionForm(request.POST, instance=cotizacion)
        
        if form.is_valid():
            cotizacion = form.save()
            messages.success(request, '✅ Cotización actualizada exitosamente')
            
            # Verificar si debe redirigir a enviar email
            if request.POST.get('guardar_y_enviar') == 'true':
                return redirect('cotizaciones:enviar_email', pk=cotizacion.pk)
            
            return redirect('cotizaciones:editar', pk=cotizacion.pk)
        else:
            messages.error(request, 'Error al actualizar la cotización')
    else:
        form = CotizacionForm(instance=cotizacion)
    
    # Obtener items relacionados
    items_servicio = cotizacion.items_servicio.all().order_by('orden')
    items_material = cotizacion.items_material.all()
    items_mano_obra = cotizacion.items_mano_obra.all()
    
    # Obtener catálogos
    servicios = ServicioBase.objects.filter(activo=True).select_related('categoria')
    materiales = Material.objects.filter(activo=True)
    categorias_empleados = CategoriaEmpleado.objects.filter(activo=True)
    
    context = {
        'cotizacion': cotizacion,
        'form': form,
        'items_servicio': items_servicio,
        'items_material': items_material,
        'items_mano_obra': items_mano_obra,
        'servicios': servicios,
        'materiales': materiales,
        'categorias_empleados': categorias_empleados,
    }
    return render(request, 'cotizaciones/cotizaciones/editar.html', context)

@login_required
@requiere_gerente_o_superior
def detalle_cotizacion(request, pk):
    verificar_mantenimientos_materiales(request)
    """Ver detalle de cotización"""
    cotizacion = get_object_or_404(Cotizacion, pk=pk)
    
    items_servicio = cotizacion.items_servicio.all().order_by('orden')
    items_material = cotizacion.items_material.all()
    items_mano_obra = cotizacion.items_mano_obra.all()
    
    context = {
        'cotizacion': cotizacion,
        'items_servicio': items_servicio,
        'items_material': items_material,
        'items_mano_obra': items_mano_obra,
        'config_empresa': ConfiguracionEmpresa.get_config(),
    }
    
    return render(request, 'cotizaciones/cotizaciones/detalle.html', context)

@login_required
@requiere_gerente_o_superior
@require_http_methods(["DELETE"])
def eliminar_cotizacion(request, pk):
    """Eliminar cotización (solo si está en borrador)"""
    try:
        cotizacion = get_object_or_404(Cotizacion, pk=pk)
        
        # Solo permitir eliminar cotizaciones en borrador
        if cotizacion.estado != 'borrador':
            return JsonResponse({
                'success': False,
                'error': 'Solo se pueden eliminar cotizaciones en estado borrador'
            })
        
        numero_cotizacion = cotizacion.numero
        cotizacion.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Cotización {numero_cotizacion} eliminada exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def completar_cotizacion(request, pk):
    """Marcar cotización como completada/enviada"""
    try:
        cotizacion = get_object_or_404(Cotizacion, pk=pk)
        
        # Validar que la cotización tenga al menos un item
        tiene_items = (
            cotizacion.items_servicio.exists() or 
            cotizacion.items_material.exists() or 
            cotizacion.items_mano_obra.exists()
        )
        
        if not tiene_items:
            return JsonResponse({
                'success': False,
                'error': 'La cotización debe tener al menos un servicio, material o trabajo para ser completada'
            })
        
        # Cambiar estado a 'enviada'
        cotizacion.estado = 'enviada'
        cotizacion.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Cotización {cotizacion.numero} marcada como enviada',
            'nuevo_estado': 'enviada',
            'estado_display': cotizacion.get_estado_display()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def agregar_item_servicio(request, cotizacion_pk):
    """Agregar item de servicio vía AJAX"""
    cotizacion = get_object_or_404(Cotizacion, pk=cotizacion_pk)
    
    try:
        data = json.loads(request.body)
        servicio_id = data.get('servicio_id')
        cantidad = Decimal(str(data.get('cantidad', 1)))
        precio_unitario = Decimal(str(data.get('precio_unitario', 0)))
        descripcion_personalizada = data.get('descripcion_personalizada', '')
        parametros = data.get('parametros', {})
        
        servicio = get_object_or_404(ServicioBase, pk=servicio_id)
        
        with transaction.atomic():
            # Crear item de servicio
            item = ItemServicio.objects.create(
                cotizacion=cotizacion,
                servicio=servicio,
                cantidad=cantidad,
                precio_unitario=precio_unitario,
                descripcion_personalizada=descripcion_personalizada,
                orden=cotizacion.items_servicio.count()
            )
            
            # Agregar parámetros si existen
            for param_id, valor in parametros.items():
                if valor:
                    ParametroItemServicio.objects.create(
                        item_servicio=item,
                        parametro_id=param_id,
                        valor=valor
                    )
            
            # Recalcular totales
            cotizacion.calcular_totales()
        
        return JsonResponse({
            'success': True,
            'item_id': item.id,
            'subtotal': float(item.subtotal),
            'valor_total': float(cotizacion.valor_total)
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def agregar_item_material(request, cotizacion_pk):
    """Agregar item de material vía AJAX"""
    cotizacion = get_object_or_404(Cotizacion, pk=cotizacion_pk)
    
    try:
        data = json.loads(request.body)
        material_id = data.get('material_id')
        cantidad = Decimal(str(data.get('cantidad', 1)))
        precio_unitario = Decimal(str(data.get('precio_unitario', 0)))
        descripcion_personalizada = data.get('descripcion_personalizada', '')
        
        material = get_object_or_404(Material, pk=material_id)
        
        # ⏱️ NUEVO: Obtener y validar horas_uso
        horas_uso = data.get('horas_uso')
        
        # Validar si el material requiere mantenimiento por horas
        if material.requiere_mantenimiento and material.tipo_mantenimiento == 'horas':
            if not horas_uso or float(horas_uso) <= 0:
                return JsonResponse({
                    'success': False,
                    'error': 'Este material requiere especificar las horas de uso'
                }, status=400)
            
            # Convertir a Decimal
            horas_uso = Decimal(str(horas_uso))
        else:
            # Si no requiere horas, asegurar que sea None
            horas_uso = None
        
        with transaction.atomic():
            item = ItemMaterial.objects.create(
                cotizacion=cotizacion,
                material=material,
                cantidad=cantidad,
                precio_unitario=precio_unitario,
                descripcion_personalizada=descripcion_personalizada,
                horas_uso=horas_uso  # ⏱️ NUEVO campo
            )
            
            # Recalcular totales
            cotizacion.calcular_totales()
        
        return JsonResponse({
            'success': True,
            'item_id': item.id,
            'subtotal': float(item.subtotal),
            'valor_total': float(cotizacion.valor_total)
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def agregar_item_mano_obra(request, cotizacion_pk):
    """Agregar item de mano de obra vía AJAX con empleados"""
    cotizacion = get_object_or_404(Cotizacion, pk=cotizacion_pk)
    
    try:
        data = json.loads(request.body)
        descripcion = data.get('descripcion')
        horas = Decimal(str(data.get('horas', 0)))
        precio_hora = Decimal(str(data.get('precio_hora', 0)))
        empleados_seleccionados = data.get('empleados_seleccionados', [])
        
        print(f"DEBUG: Datos recibidos - empleados: {empleados_seleccionados}")  # DEBUG
        
        with transaction.atomic():
            # Crear item de mano de obra
            item = ItemManoObra.objects.create(
                cotizacion=cotizacion,
                descripcion=descripcion,
                horas=horas,
                precio_hora=precio_hora
            )
            
            print(f"DEBUG: ItemManoObra creado con ID: {item.id}")  # DEBUG
            
            # Asignar empleados si fueron seleccionados
            empleados_asignados = []
            if empleados_seleccionados and len(empleados_seleccionados) > 0:
                # Distribuir horas entre empleados (equitativamente por defecto)
                horas_por_empleado = horas / len(empleados_seleccionados)
                
                for empleado_id in empleados_seleccionados:
                    try:
                        empleado = PerfilEmpleado.objects.get(pk=empleado_id, activo=True, cargo='empleado')
                        
                        # Crear asignación de empleado
                        asignacion = ItemManoObraEmpleado.objects.create(
                            item_mano_obra=item,
                            empleado=empleado,
                            horas_asignadas=horas_por_empleado
                        )
                        
                        print(f"DEBUG: ItemManoObraEmpleado creado - empleado: {empleado.nombre_completo}")  # DEBUG
                        
                        # Crear registro en TrabajoEmpleado para la vista del empleado
                        trabajo_empleado, created = TrabajoEmpleado.objects.get_or_create(
                            empleado=empleado,
                            item_mano_obra=item,
                            defaults={
                                'cotizacion': cotizacion,
                                'estado': 'pendiente'
                            }
                        )
                        
                        if created:
                            print(f"DEBUG: TrabajoEmpleado creado para {empleado.nombre_completo}")  # DEBUG
                        else:
                            print(f"DEBUG: TrabajoEmpleado ya existía para {empleado.nombre_completo}")  # DEBUG
                        
                        empleados_asignados.append(empleado.nombre_completo)
                        
                    except PerfilEmpleado.DoesNotExist:
                        print(f"DEBUG: Empleado con ID {empleado_id} no encontrado")  # DEBUG
                        continue  # Saltar empleados que no existen o no están activos
            
            # Recalcular totales
            cotizacion.calcular_totales()
        
        response_data = {
            'success': True,
            'item_id': item.id,
            'subtotal': float(item.subtotal),
            'valor_total': float(cotizacion.valor_total)
        }
        
        if empleados_asignados:
            response_data['empleados_asignados'] = empleados_asignados
            response_data['message'] = f'Mano de obra agregada con {len(empleados_asignados)} empleados asignados'
        else:
            response_data['message'] = 'Mano de obra agregada sin empleados asignados'
        
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"ERROR en agregar_item_mano_obra: {str(e)}")  # DEBUG
        import traceback
        traceback.print_exc()  # Para ver el stack trace completo
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@requiere_gerente_o_superior
@require_http_methods(["DELETE"])
def eliminar_item_servicio(request, cotizacion_pk, item_pk):
    """Eliminar item de servicio"""
    cotizacion = get_object_or_404(Cotizacion, pk=cotizacion_pk)
    item = get_object_or_404(ItemServicio, pk=item_pk, cotizacion=cotizacion)
    
    item.delete()
    cotizacion.calcular_totales()
    
    return JsonResponse({
        'success': True,
        'valor_total': float(cotizacion.valor_total)
    })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["DELETE"])
def eliminar_item_material(request, cotizacion_pk, item_pk):
    """Eliminar item de material"""
    cotizacion = get_object_or_404(Cotizacion, pk=cotizacion_pk)
    item = get_object_or_404(ItemMaterial, pk=item_pk, cotizacion=cotizacion)
    
    item.delete()
    cotizacion.calcular_totales()
    
    return JsonResponse({
        'success': True,
        'valor_total': float(cotizacion.valor_total)
    })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["DELETE"])
def eliminar_item_mano_obra(request, cotizacion_pk, item_pk):
    """Eliminar item de mano de obra"""
    cotizacion = get_object_or_404(Cotizacion, pk=cotizacion_pk)
    item = get_object_or_404(ItemManoObra, pk=item_pk, cotizacion=cotizacion)
    
    item.delete()
    cotizacion.calcular_totales()
    
    return JsonResponse({
        'success': True,
        'valor_total': float(cotizacion.valor_total)
    })

@login_required
@requiere_gerente_o_superior
def obtener_servicios_categoria(request, categoria_id):
    """Obtener servicios de una categoría vía AJAX"""
    servicios = ServicioBase.objects.filter(
        categoria_id=categoria_id, 
        activo=True
    ).values('id', 'nombre', 'precio_base', 'unidad', 'es_parametrizable')
    
    return JsonResponse(list(servicios), safe=False)

@login_required
@requiere_gerente_o_superior
def obtener_parametros_servicio(request, servicio_id):
    """Obtener parámetros de un servicio vía AJAX"""
    try:
        parametros = ParametroServicio.objects.filter(
            servicio_id=servicio_id
        ).order_by('orden')
        
        parametros_data = []
        for param in parametros:
            param_dict = {
                'id': param.id,
                'nombre': param.nombre,
                'tipo': param.tipo,
                'requerido': param.requerido,
                'valor_por_defecto': param.valor_por_defecto or '',
                'orden': param.orden
            }
            
            if param.tipo == 'select' and param.opciones:
                param_dict['opciones_list'] = [opt.strip() for opt in param.opciones.split(',')]
            
            parametros_data.append(param_dict)
        
        return JsonResponse({
            'success': True,
            'parametros': parametros_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def actualizar_gastos_traslado(request, cotizacion_pk):
    """Actualizar gastos de traslado"""
    cotizacion = get_object_or_404(Cotizacion, pk=cotizacion_pk)
    
    try:
        data = json.loads(request.body)
        # Obtener y validar gastos_traslado
        gastos_value = data.get('gastos_traslado', '0')
        # Si es vacío o None, usar 0
        if gastos_value == '' or gastos_value is None:
            gastos_value = '0'
        gastos_traslado = Decimal(str(gastos_value))
        
        cotizacion.gastos_traslado = gastos_traslado
        cotizacion.calcular_totales()
        
        return JsonResponse({
            'success': True,
            'valor_total': float(cotizacion.valor_total),
            'valor_neto': float(cotizacion.valor_neto),
            'valor_iva': float(cotizacion.valor_iva)
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@requiere_gerente_o_superior
def generar_pdf_cotizacion(request, pk):
    cotizacion = get_object_or_404(Cotizacion, pk=pk)
    
    # Crear el objeto HttpResponse con el content-type de PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Cotizacion_{cotizacion.numero}.pdf"'
    
    # Crear el buffer en memoria
    buffer = io.BytesIO()
    
    # Crear el documento PDF
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm
    )
    
    # Contenedor para los elementos del PDF
    elements = []
    
    # Estilos personalizados
    styles = getSampleStyleSheet()
    
    # Estilo para encabezado empresa (centrado)
    empresa_style = ParagraphStyle(
        'EmpresaStyle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.black,
        alignment=TA_CENTER,
        spaceBefore=0,
        spaceAfter=3,
        fontName='Helvetica-Bold'
    )
    
    info_empresa_style = ParagraphStyle(
        'InfoEmpresaStyle', 
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.black,
        alignment=TA_CENTER,
        spaceBefore=1,
        spaceAfter=1
    )
    
    # Estilo para título cotización (centrado)
    titulo_cot_style = ParagraphStyle(
        'TituloCotStyle',
        parent=styles['Normal'],
        fontSize=16,
        textColor=colors.black,
        alignment=TA_CENTER,
        spaceBefore=15,
        spaceAfter=15,
        fontName='Helvetica-Bold'
    )
    
    # Estilo para información del cliente (alineado a la izquierda)
    cliente_style = ParagraphStyle(
        'ClienteStyle',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.black,
        alignment=TA_LEFT,
        spaceBefore=3,
        spaceAfter=3,
        fontName='Helvetica-Bold'
    )
    
    # Estilo para subtítulos de secciones
    seccion_style = ParagraphStyle(
        'SeccionStyle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.black,
        spaceBefore=15,
        spaceAfter=10,
        fontName='Helvetica-Bold',
        alignment=TA_LEFT
    )
    
    # Estilo para totales (alineado a la derecha)
    total_style = ParagraphStyle(
        'TotalStyle',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.black,
        alignment=TA_RIGHT,
        spaceBefore=3,
        spaceAfter=3,
        fontName='Helvetica-Bold'
    )
    
    # ENCABEZADO EMPRESA (CENTRADO)
    elements.append(Paragraph("JOSE E. ALVARADO N.", empresa_style))
    elements.append(Paragraph("SERVICIOS ELECTROMECANICOS", info_empresa_style))
    elements.append(Paragraph("INSTALACIÓN, MANTENCIÓN Y REPARACIÓN DE BOMBAS DE AGUA.", info_empresa_style))
    elements.append(Paragraph("SUPERFICIE Y SUMERGIBLES", info_empresa_style))
    elements.append(Paragraph("Pje. Santa Elisa 2437 Osorno", info_empresa_style))
    elements.append(Paragraph("TELEFONOS: 9-76193683/ EMAIL: seelmec@gmail.com", info_empresa_style))
    
    # LÍNEA DE SEPARACIÓN
    elements.append(Spacer(1, 10))
    line_table = Table([['_' * 80]], colWidths=[17*cm])
    line_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('FONTSIZE', (0, 0), (0, 0), 12),
        ('TEXTCOLOR', (0, 0), (0, 0), colors.black),
    ]))
    elements.append(line_table)
    elements.append(Spacer(1, 10))
    
    # TÍTULO COTIZACIÓN (CENTRADO)
    elements.append(Paragraph(f"COTIZACIÓN   N°  {cotizacion.numero}", titulo_cot_style))
    
    # INFORMACIÓN DEL CLIENTE (ALINEADO A LA IZQUIERDA)
    elements.append(Paragraph(f"SEÑOR(ES): {cotizacion.get_nombre_cliente().upper()}", cliente_style))
    
    if cotizacion.representante or cotizacion.representante_nombre_respaldo:
        rep_nombre = cotizacion.get_nombre_representante()
        if rep_nombre:
            elements.append(Paragraph(f"ATENCIÓN: {rep_nombre.upper()}", cliente_style))

    elements.append(Paragraph(f"REFERENCIA: {cotizacion.referencia.upper()}", cliente_style))
    elements.append(Paragraph(f"LUGAR: {cotizacion.lugar.upper()}", cliente_style))
    
    # SUBTÍTULO DESCRIPCIÓN
    elements.append(Paragraph("A.- DESCRIPCIÓN DE TRABAJOS, DETALLE Y VALORIZACIÓN.", seccion_style))
    elements.append(Spacer(1, 10))
    
    # OBTENER ITEMS
    try:
        from .models import ItemServicio, ItemMaterial, ItemManoObra
        
        items_servicio = list(ItemServicio.objects.filter(cotizacion=cotizacion).select_related('servicio'))
        items_material = list(ItemMaterial.objects.filter(cotizacion=cotizacion).select_related('material'))
        items_mano_obra = list(ItemManoObra.objects.filter(cotizacion=cotizacion))
        
    except Exception as e:
        items_servicio = []
        items_material = []
        items_mano_obra = []
    
    # TABLA DE SERVICIOS
    if items_servicio:
        servicios_data = [['DESCRIPCIÓN DEL TRABAJO', 'CANTIDAD', 'PRECIO UNIT.', 'SUBTOTAL']]
        
        for item in items_servicio:
            if item.descripcion_personalizada:
                descripcion = item.descripcion_personalizada
            else:
                descripcion = str(item.servicio)
            
            cantidad = f"{item.cantidad} {item.servicio.unidad if item.servicio else 'UND'}"
            precio = f"${int(item.precio_unitario):,}".replace(',', '.')
            subtotal = f"${int(item.subtotal):,}".replace(',', '.')
            
            servicios_data.append([descripcion, cantidad, precio, subtotal])
        
        servicios_table = Table(servicios_data, colWidths=[9*cm, 2.5*cm, 2.5*cm, 3*cm])
        servicios_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(servicios_table)
        elements.append(Spacer(1, 10))
    
    # TABLA DE MATERIALES
    if items_material:
        materiales_data = [['MATERIAL', 'CANTIDAD', 'PRECIO UNIT.', 'SUBTOTAL']]
        
        for item in items_material:
            if item.descripcion_personalizada:
                descripcion = item.descripcion_personalizada
            elif item.material:
                descripcion = f"{item.material.codigo} - {item.material.nombre}"
            else:
                descripcion = "Material sin especificar"
            
            unidad = item.material.unidad if item.material else "UND"
            cantidad = f"{item.cantidad} {unidad}"
            precio = f"${int(item.precio_unitario):,}".replace(',', '.')
            subtotal = f"${int(item.subtotal):,}".replace(',', '.')
            
            materiales_data.append([descripcion, cantidad, precio, subtotal])
        
        materiales_table = Table(materiales_data, colWidths=[9*cm, 2.5*cm, 2.5*cm, 3*cm])
        materiales_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(materiales_table)
        elements.append(Spacer(1, 10))
    
    # TABLA DE MANO DE OBRA
    if items_mano_obra:
        mano_obra_data = [['MANO DE OBRA', 'HORAS', 'PRECIO/HORA', 'SUBTOTAL']]
        
        for item in items_mano_obra:
            descripcion = item.descripcion
            horas = f"{item.horas}"
            precio_hora = f"${int(item.precio_hora):,}".replace(',', '.')
            subtotal = f"${int(item.subtotal):,}".replace(',', '.')
            
            mano_obra_data.append([descripcion, horas, precio_hora, subtotal])
        
        mano_obra_table = Table(mano_obra_data, colWidths=[9*cm, 2.5*cm, 2.5*cm, 3*cm])
        mano_obra_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(mano_obra_table)
        elements.append(Spacer(1, 15))
    
    # SECCIÓN DE TOTALES
    elements.append(Spacer(1, 20))
    
    # Crear tabla con conceptos a la izquierda y valores a la derecha
    totales_data = [
        ['VALOR TOTAL TRABAJOS', f"${int(cotizacion.subtotal_servicios):,}".replace(',', '.')],
        ['MATERIALES', f"${int(cotizacion.subtotal_materiales):,}".replace(',', '.')],
        ['MANO DE OBRA', f"${int(cotizacion.subtotal_mano_obra):,}".replace(',', '.')],
        ['GASTOS DE TRASLADO', f"${int(cotizacion.gastos_traslado):,}".replace(',', '.')],
        ['', ''],  # Espacio
        ['VALOR NETO', f"${int(cotizacion.valor_neto):,}".replace(',', '.')],
        ['VALOR IVA (19%)', f"${int(cotizacion.valor_iva):,}".replace(',', '.')],
        ['VALOR TOTAL', f"${int(cotizacion.valor_total):,}".replace(',', '.')]
    ]
    
    totales_table = Table(totales_data, colWidths=[10*cm, 7*cm])
    totales_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),   # Conceptos a la izquierda
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),  # Valores a la derecha
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, -3), 'Helvetica'),
        ('FONTNAME', (0, -2), (-1, -1), 'Helvetica-Bold'),  # Últimas dos filas en negrita
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('LINEABOVE', (0, -2), (-1, -2), 1, colors.black),  # Línea antes del valor neto
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),  # Línea más gruesa antes del total
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    
    elements.append(totales_table)
    
    
    # OBSERVACIONES
    elements.append(Spacer(1, 25))
    if cotizacion.observaciones:
        elements.append(Paragraph(f"NOTA: {cotizacion.observaciones}", styles['Normal']))
    else:
        elements.append(Paragraph("NOTA: Sin observaciones adicionales.", styles['Normal']))
    
    # SECCIÓN DE FIRMAS
    elements.append(Spacer(1, 20))
    
    # Crear tabla para firmas con espaciado adecuado
    firmas_data = [
        ['SALUDA ATTE.       JOSE E. ALVARADO N.', '', ''],
        ['', '', ''],
        ['FIRMA:_________________', '', 'NOMBRE Y RUT:_________________'],
        ['', '', 'ACEPTADO CLIENTE']
    ]
    
    firmas_table = Table(firmas_data, colWidths=[7*cm, 3*cm, 7*cm])
    firmas_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),     # SALUDA ATTE a la izquierda
        ('ALIGN', (0, 2), (0, 2), 'LEFT'),     # FIRMA a la izquierda
        ('ALIGN', (2, 2), (2, 2), 'CENTER'),   # NOMBRE Y RUT centrado
        ('ALIGN', (2, 3), (2, 3), 'CENTER'),   # ACEPTADO CLIENTE centrado
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    
    elements.append(firmas_table)
    
    # FECHA (alineada a la izquierda)
    elements.append(Spacer(1, 30))
    
    # Formatear fecha como en la imagen: "OSORNO 20 DE SEPTIEMBRE DE 2022"
    meses = {
        1: 'ENERO', 2: 'FEBRERO', 3: 'MARZO', 4: 'ABRIL', 5: 'MAYO', 6: 'JUNIO',
        7: 'JULIO', 8: 'AGOSTO', 9: 'SEPTIEMBRE', 10: 'OCTUBRE', 11: 'NOVIEMBRE', 12: 'DICIEMBRE'
    }
    
    dia = cotizacion.fecha_creacion.day
    mes = meses[cotizacion.fecha_creacion.month]
    año = cotizacion.fecha_creacion.year
    
    fecha_formateada = f"OSORNO {dia} DE {mes} DE {año}"
    
    elements.append(Paragraph(fecha_formateada, 
                            ParagraphStyle('FechaStyle', parent=styles['Normal'], 
                                         fontSize=10, alignment=TA_LEFT, 
                                         fontName='Helvetica')))
    
    # Construir el PDF
    doc.build(elements)
    
    # Obtener el valor del buffer y escribirlo a la respuesta
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    
    return response

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def cambiar_estado_cotizacion(request, pk):
    """Cambiar estado de la cotización"""
    import logging
    logger = logging.getLogger(__name__)
    
    cotizacion = get_object_or_404(Cotizacion, pk=pk)
    
    try:
        data = json.loads(request.body)
        nuevo_estado = data.get('estado')
        estado_anterior = cotizacion.estado
        
        logger.info(f"🔄 Cambio de estado - Cotización {cotizacion.numero}")
        logger.info(f"   Estado anterior: {estado_anterior}")
        logger.info(f"   Estado nuevo: {nuevo_estado}")
        
        if nuevo_estado in dict(Cotizacion.ESTADO_CHOICES):
            cotizacion.estado = nuevo_estado
            cotizacion.save()
            
            # ⏱️ NUEVA LÓGICA: Solo acumular cuando pasa a 'finalizada'
            deberia_acumular = (
                nuevo_estado == 'finalizada' and 
                estado_anterior != 'finalizada'
            )
            
            logger.info(f"   ¿Debería acumular horas? {deberia_acumular}")
            
            if deberia_acumular:
                logger.info(f"   ✅ Llamando a acumular_horas_materiales()")
                cotizacion.acumular_horas_materiales()
                logger.info(f"   ✓ Horas acumuladas exitosamente")
            
            messages.success(request, f'Estado actualizado a {cotizacion.get_estado_display()}')
            
            return JsonResponse({
                'success': True,
                'nuevo_estado': nuevo_estado,
                'estado_display': cotizacion.get_estado_display()
            })
        else:
            return JsonResponse({'success': False, 'error': 'Estado inválido'})
            
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@requiere_gerente_o_superior
@require_http_methods(["GET", "POST"])
def actualizar_fecha_realizacion(request, pk):
    """
    Vista para actualizar la fecha de realización de una cotización aprobada.
    Notifica automáticamente al cliente si hay cambio.
    """
    cotizacion = get_object_or_404(Cotizacion, pk=pk)
    
    # Verificar que está aprobada
    if cotizacion.estado != 'aprobada':
        messages.error(request, 'Solo se puede actualizar la fecha de cotizaciones aprobadas')
        return redirect('cotizaciones:detalle', pk=pk)
    
    if request.method == 'POST':
        form = ActualizarFechaRealizacionForm(request.POST, cotizacion=cotizacion)
        if form.is_valid():
            nueva_fecha = form.cleaned_data['fecha_realizacion']
            
            # Actualizar fecha y enviar notificaciones
            resultado = cotizacion.actualizar_fecha_realizacion(
                nueva_fecha=nueva_fecha,
                usuario=request.user
            )
            
            if resultado['fecha_actualizada']:
                messages.success(request, f'Fecha de realización actualizada a {nueva_fecha.strftime("%d/%m/%Y")}')
                
                if resultado['email_enviado']:
                    messages.success(request, 'Cliente notificado por email')
                
                if resultado['notificacion_enviada']:
                    messages.info(request, 'Notificación interna creada')
                
                if resultado['error']:
                    messages.warning(request, f'Advertencia: {resultado["error"]}')
            else:
                messages.info(request, 'No hubo cambios en la fecha')
            
            return redirect('cotizaciones:detalle', pk=pk)
    else:
        form = ActualizarFechaRealizacionForm(cotizacion=cotizacion)
    
    return render(request, 'cotizaciones/cotizaciones/actualizar_fecha_realizacion.html', {
        'form': form,
        'cotizacion': cotizacion
    })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["GET", "POST"])
def finalizar_cotizacion(request, pk):
    """
    Marca una cotización como finalizada.
    Inicia el contador de 7 días para solicitar feedback.
    """
    cotizacion = get_object_or_404(Cotizacion, pk=pk)
    
    # Verificar que está aprobada
    if cotizacion.estado != 'aprobada':
        messages.error(request, 'Solo se pueden finalizar cotizaciones aprobadas')
        return redirect('cotizaciones:detalle', pk=pk)
    
    if request.method == 'POST':
        form = FinalizarCotizacionForm(request.POST)
        if form.is_valid():
            resultado = cotizacion.marcar_como_finalizada(usuario=request.user)
            
            if resultado['success']:
                # Guardar comentarios si existen
                comentarios = form.cleaned_data.get('comentarios_finalizacion')
                if comentarios:
                    if cotizacion.observaciones:
                        cotizacion.observaciones += f"\n\n[FINALIZACIÓN - {timezone.now().strftime('%d/%m/%Y')}]\n{comentarios}"
                    else:
                        cotizacion.observaciones = f"[FINALIZACIÓN - {timezone.now().strftime('%d/%m/%Y')}]\n{comentarios}"
                    cotizacion.save()
                
                messages.success(request, resultado['mensaje'])
                messages.info(request, 'El sistema solicitará feedback al cliente en 7 días')
            else:
                messages.error(request, resultado['error'])
            
            return redirect('cotizaciones:detalle', pk=pk)
    else:
        form = FinalizarCotizacionForm()
    
    return render(request, 'cotizaciones/cotizaciones/finalizar_cotizacion.html', {
        'form': form,
        'cotizacion': cotizacion
    })

@login_required
@requiere_gerente_o_superior
def editar_cotizacion_aprobada(request, pk):
    """
    Permite editar una cotización aprobada, pero la marca como 'requiere_cambios'.
    Esto resetea el proceso de aprobación.
    """
    cotizacion = get_object_or_404(Cotizacion, pk=pk)
    
    # Verificar que está aprobada
    if cotizacion.estado != 'aprobada':
        messages.error(request, 'Esta cotización no está aprobada')
        return redirect('cotizaciones:detalle', pk=pk)
    
    # Confirmar la acción
    if request.method == 'POST' and 'confirmar' in request.POST:
        # Cambiar estado
        cotizacion.estado = 'requiere_cambios'
        cotizacion.save()
        
        # Crear notificación
        Notificacion.objects.create(
            usuario=cotizacion.creado_por,
            titulo=f"Cotización {cotizacion.numero} requiere cambios",
            mensaje=f"La cotización aprobada fue modificada y ahora requiere nueva aprobación",
            tipo='warning',
            url=f'/cotizaciones/{cotizacion.pk}/editar/'
        )
        
        messages.warning(request, 'La cotización ahora requiere cambios. Deberá ser enviada nuevamente al cliente.')
        return redirect('cotizaciones:editar', pk=pk)
    
    return render(request, 'cotizaciones/cotizaciones/confirmar_edicion_aprobada.html', {
        'cotizacion': cotizacion
    })

# === Crud Clientes === 

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def crear_cliente(request):
    """Crear nuevo cliente vía AJAX"""
    try:
        data = json.loads(request.body)
        
        with transaction.atomic():
            # Crear cliente SIN los campos 'atencion' y 'activo'
            cliente = Cliente.objects.create(
                nombre=data.get('nombre'),
                rut=data.get('rut', ''),
                telefono=data.get('telefono', ''),
                email=data.get('email', ''),
                direccion=data.get('direccion', '')
            )
            
            # Crear representantes si existen
            representantes = data.get('representantes', [])
            for idx, nombre_rep in enumerate(representantes):
                if nombre_rep.strip():  # Solo si no está vacío
                    RepresentanteCliente.objects.create(
                        cliente=cliente,
                        nombre=nombre_rep.strip(),
                        orden=idx
                    )
        
        return JsonResponse({
            'success': True,
            'cliente_id': cliente.id,
            'message': 'Cliente creado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["PUT"])
def editar_cliente(request, cliente_id):
    """Editar cliente existente vía AJAX"""
    try:
        cliente = get_object_or_404(Cliente, pk=cliente_id)
        data = json.loads(request.body)
        
        with transaction.atomic():
            # Actualizar datos básicos del cliente
            cliente.nombre = data.get('nombre', cliente.nombre)
            cliente.rut = data.get('rut', cliente.rut)
            cliente.telefono = data.get('telefono', cliente.telefono)
            cliente.email = data.get('email', cliente.email)
            cliente.direccion = data.get('direccion', cliente.direccion)
            cliente.save()
            
            # Actualizar representantes
            # Eliminar los existentes
            cliente.representantes.all().delete()
            
            # Crear los nuevos
            representantes = data.get('representantes', [])
            for idx, nombre_rep in enumerate(representantes):
                if nombre_rep.strip():
                    RepresentanteCliente.objects.create(
                        cliente=cliente,
                        nombre=nombre_rep.strip(),
                        orden=idx
                    )
        
        return JsonResponse({
            'success': True,
            'message': 'Cliente actualizado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
    
@login_required
@requiere_gerente_o_superior
@require_http_methods(["DELETE"])
def eliminar_cliente(request, cliente_id):
    """Eliminar cliente vía AJAX"""
    try:
        cliente = get_object_or_404(Cliente, pk=cliente_id)
        nombre_cliente = cliente.nombre
        
        # Los representantes se eliminarán automáticamente por CASCADE
        cliente.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Cliente {nombre_cliente} eliminado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
    
@login_required
@requiere_gerente_o_superior
@require_http_methods(["GET"])
def obtener_cliente(request, cliente_id):
    """Obtener datos de un cliente vía AJAX"""
    try:
        cliente = get_object_or_404(Cliente, pk=cliente_id)
        
        # Obtener lista de representantes
        representantes = list(cliente.representantes.values_list('nombre', flat=True))
        
        return JsonResponse({
            'success': True,
            'cliente': {
                'id': cliente.id,
                'nombre': cliente.nombre,
                'rut': cliente.rut or '',
                'telefono': cliente.telefono or '',
                'email': cliente.email or '',
                'direccion': cliente.direccion or '',
                'representantes': representantes
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
def obtener_representantes_cliente(request, cliente_id):
    """Obtener representantes de un cliente vía AJAX"""
    try:
        representantes = RepresentanteCliente.objects.filter(
            cliente_id=cliente_id
        ).values('id', 'nombre').order_by('orden', 'nombre')
        
        return JsonResponse({
            'success': True,
            'representantes': list(representantes)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

# === Crud Tipos de Trabajo =====

@login_required
@requiere_gerente_o_superior
def gestionar_tipos_trabajo(request):
    """Vista principal para gestionar tipos de trabajo"""
    
    busqueda = request.GET.get('busqueda', '').strip()
    estado_filtro = request.GET.get('estado', '').strip()
    
    # Query base
    tipos = TipoTrabajo.objects.all()
    
    # Aplicar filtros
    if busqueda:
        tipos = tipos.filter(
            Q(nombre__icontains=busqueda) |
            Q(descripcion__icontains=busqueda)
        )
    
    if estado_filtro == 'activo':
        tipos = tipos.filter(activo=True)
    elif estado_filtro == 'inactivo':
        tipos = tipos.filter(activo=False)
    
    # Estadísticas
    tipos_activos = TipoTrabajo.objects.filter(activo=True).count()
    tipos_inactivos = TipoTrabajo.objects.filter(activo=False).count()
    cotizaciones_count = Cotizacion.objects.count()
    
    # Prefetch para optimizar consultas
    tipos = tipos.prefetch_related('cotizacion_set').order_by('nombre')
    
    context = {
        'tipos': tipos,
        'tipos_activos': tipos_activos,
        'tipos_inactivos': tipos_inactivos,
        'cotizaciones_count': cotizaciones_count,
        'busqueda': busqueda,
        'estado_filtro': estado_filtro,
    }
    
    return render(request, 'cotizaciones/tipos_trabajo/gestionar_tipos_trabajo.html', context)

@login_required
@requiere_gerente_o_superior
def crear_tipo_trabajo(request):
    """Crear nuevo tipo de trabajo"""
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        activo = request.POST.get('activo') == 'on'
        
        if not nombre:
            messages.error(request, 'El nombre del tipo de trabajo es obligatorio')
            return redirect('cotizaciones:gestionar_tipos_trabajo')
        
        # Verificar si ya existe
        if TipoTrabajo.objects.filter(nombre__iexact=nombre).exists():
            messages.error(request, f'Ya existe un tipo de trabajo con el nombre "{nombre}"')
            return redirect('cotizaciones:gestionar_tipos_trabajo')
        
        try:
            tipo = TipoTrabajo.objects.create(
                nombre=nombre,
                descripcion=descripcion if descripcion else None,
                activo=activo
            )
            
            messages.success(request, f'Tipo de trabajo "{tipo.nombre}" creado exitosamente')
            
            # Crear notificación
            crear_notificacion(
                request.user,
                tipo='success',
                titulo='Tipo de Trabajo Creado',
                mensaje=f'Se ha creado el tipo de trabajo "{tipo.nombre}"',
                url=f'/cotizaciones/tipos-trabajo/'
            )
            
        except Exception as e:
            messages.error(request, f'Error al crear el tipo de trabajo: {str(e)}')
        
        return redirect('cotizaciones:gestionar_tipos_trabajo')
    
    return redirect('cotizaciones:gestionar_tipos_trabajo')

@login_required
@requiere_gerente_o_superior
def editar_tipo_trabajo(request, tipo_id):
    """Editar tipo de trabajo existente"""
    tipo = get_object_or_404(TipoTrabajo, id=tipo_id)
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        activo = request.POST.get('activo') == 'on'
        
        if not nombre:
            messages.error(request, 'El nombre del tipo de trabajo es obligatorio')
            return redirect('cotizaciones:gestionar_tipos_trabajo')
        
        # Verificar si el nuevo nombre ya existe (excepto el actual)
        if TipoTrabajo.objects.filter(nombre__iexact=nombre).exclude(id=tipo_id).exists():
            messages.error(request, f'Ya existe otro tipo de trabajo con el nombre "{nombre}"')
            return redirect('cotizaciones:gestionar_tipos_trabajo')
        
        try:
            tipo.nombre = nombre
            tipo.descripcion = descripcion if descripcion else None
            tipo.activo = activo
            tipo.save()
            
            messages.success(request, f'Tipo de trabajo "{tipo.nombre}" actualizado exitosamente')
            
            # Crear notificación
            crear_notificacion(
                request.user,
                tipo='info',
                titulo='Tipo de Trabajo Actualizado',
                mensaje=f'Se ha actualizado el tipo de trabajo "{tipo.nombre}"',
                url=f'/cotizaciones/tipos-trabajo/'
            )
            
        except Exception as e:
            messages.error(request, f'Error al actualizar el tipo de trabajo: {str(e)}')
        
        return redirect('cotizaciones:gestionar_tipos_trabajo')
    
    return redirect('cotizaciones:gestionar_tipos_trabajo')

@login_required
@requiere_gerente_o_superior
def obtener_datos_tipo_trabajo(request, tipo_id):
    """Obtener datos de un tipo de trabajo para edición (JSON)"""
    try:
        tipo = TipoTrabajo.objects.get(id=tipo_id)
        
        data = {
            'success': True,
            'tipo': {
                'id': tipo.id,
                'nombre': tipo.nombre,
                'descripcion': tipo.descripcion or '',
                'activo': tipo.activo,
            }
        }
        return JsonResponse(data)
        
    except TipoTrabajo.DoesNotExist:
        return JsonResponse({
            'success': False,
            'mensaje': 'Tipo de trabajo no encontrado'
        }, status=404)

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def eliminar_tipo_trabajo(request, tipo_id):
    """Eliminar tipo de trabajo"""
    try:
        tipo = TipoTrabajo.objects.get(id=tipo_id)
        
        # Verificar si tiene cotizaciones asociadas
        if tipo.cotizacion_set.exists():
            return JsonResponse({
                'success': False,
                'mensaje': f'No se puede eliminar: el tipo de trabajo "{tipo.nombre}" tiene {tipo.cotizacion_set.count()} cotizaciones asociadas'
            })
        
        nombre = tipo.nombre
        tipo.delete()
        
        messages.success(request, f'Tipo de trabajo "{nombre}" eliminado exitosamente')
        
        # Crear notificación
        crear_notificacion(
            request.user,
            tipo='warning',
            titulo='Tipo de Trabajo Eliminado',
            mensaje=f'Se ha eliminado el tipo de trabajo "{nombre}"',
            url=f'/cotizaciones/tipos-trabajo/'
        )
        
        return JsonResponse({
            'success': True,
            'mensaje': 'Tipo de trabajo eliminado exitosamente'
        })
        
    except TipoTrabajo.DoesNotExist:
        return JsonResponse({
            'success': False,
            'mensaje': 'Tipo de trabajo no encontrado'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'mensaje': f'Error al eliminar: {str(e)}'
        }, status=500)

@login_required
@requiere_gerente_o_superior
def exportar_tipos_trabajo(request):
    """Exportar tipos de trabajo a Excel o CSV"""
    
    formato = request.GET.get('formato', 'excel')
    estado_filtro = request.GET.get('estado', '').strip()
    
    # Query
    tipos = TipoTrabajo.objects.all()
    
    if estado_filtro == 'activo':
        tipos = tipos.filter(activo=True)
    elif estado_filtro == 'inactivo':
        tipos = tipos.filter(activo=False)
    
    tipos = tipos.order_by('nombre')
    
    if formato == 'csv':
        # Exportar CSV
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="tipos_trabajo_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        # BOM para UTF-8
        response.write('\ufeff')
        
        writer = csv.writer(response)
        writer.writerow(['Nombre', 'Descripción', 'Estado', 'Cotizaciones Asociadas'])
        
        for tipo in tipos:
            writer.writerow([
                tipo.nombre,
                tipo.descripcion or '',
                'Activo' if tipo.activo else 'Inactivo',
                tipo.cotizacion_set.count()
            ])
        
        return response
    
    else:
        # Exportar Excel
        wb = Workbook()
        ws = wb.active
        ws.title = "Tipos de Trabajo"
        
        # Estilos
        header_fill = PatternFill(start_color='2575C0', end_color='2575C0', fill_type='solid')
        header_font = Font(bold=True, color='FFFFFF', size=12)
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # Headers
        headers = ['Nombre', 'Descripción', 'Estado', 'Cotizaciones Asociadas']
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num)
            cell.value = header
            cell.fill = header_fill
            cell.font = header_font
            cell.border = border
            cell.alignment = Alignment(horizontal='center', vertical='center')
        
        # Datos
        for row_num, tipo in enumerate(tipos, 2):
            ws.cell(row=row_num, column=1, value=tipo.nombre).border = border
            ws.cell(row=row_num, column=2, value=tipo.descripcion or '').border = border
            ws.cell(row=row_num, column=3, value='Activo' if tipo.activo else 'Inactivo').border = border
            ws.cell(row=row_num, column=4, value=tipo.cotizacion_set.count()).border = border
        
        # Ajustar anchos
        ws.column_dimensions['A'].width = 30
        ws.column_dimensions['B'].width = 50
        ws.column_dimensions['C'].width = 15
        ws.column_dimensions['D'].width = 20
        
        # Guardar
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="tipos_trabajo_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
        
        return response

# === Crud Servicios === 

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def crear_servicio(request):
    """Crear nuevo servicio vía AJAX"""
    try:
        data = json.loads(request.body)
        
        # Obtener la categoría
        categoria = get_object_or_404(CategoriaServicio, pk=data.get('categoria_id'))
        
        servicio = ServicioBase.objects.create(
            categoria=categoria,
            nombre=data.get('nombre'),
            descripcion=data.get('descripcion'),
            precio_base=data.get('precio_base'),
            unidad=data.get('unidad', 'UND'),
            es_parametrizable=data.get('es_parametrizable', False),
            activo=data.get('activo', True)
        )
        
        return JsonResponse({
            'success': True,
            'servicio_id': servicio.id,
            'message': 'Servicio creado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["GET"])
def obtener_servicio(request, servicio_id):
    """Obtener datos de un servicio vía AJAX"""
    try:
        servicio = get_object_or_404(ServicioBase, pk=servicio_id)
        
        return JsonResponse({
            'success': True,
            'servicio': {
                'id': servicio.id,
                'categoria_id': servicio.categoria.id,
                'nombre': servicio.nombre,
                'descripcion': servicio.descripcion,
                'precio_base': float(servicio.precio_base),
                'unidad': servicio.unidad,
                'es_parametrizable': servicio.es_parametrizable,
                'activo': servicio.activo
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["PUT"])
def editar_servicio(request, servicio_id):
    """Editar servicio existente vía AJAX"""
    try:
        servicio = get_object_or_404(ServicioBase, pk=servicio_id)
        data = json.loads(request.body)
        
        # Actualizar categoría si se proporciona
        if data.get('categoria_id'):
            categoria = get_object_or_404(CategoriaServicio, pk=data.get('categoria_id'))
            servicio.categoria = categoria
        
        servicio.nombre = data.get('nombre', servicio.nombre)
        servicio.descripcion = data.get('descripcion', servicio.descripcion)
        servicio.precio_base = data.get('precio_base', servicio.precio_base)
        servicio.unidad = data.get('unidad', servicio.unidad)
        servicio.es_parametrizable = data.get('es_parametrizable', servicio.es_parametrizable)
        servicio.activo = data.get('activo', servicio.activo)
        servicio.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Servicio actualizado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["DELETE"])
def eliminar_servicio(request, servicio_id):
    """Eliminar servicio vía AJAX"""
    try:
        servicio = get_object_or_404(ServicioBase, pk=servicio_id)
        nombre_servicio = servicio.nombre
        servicio.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Servicio {nombre_servicio} eliminado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def crear_categoria_servicio(request):
    """Crear nueva categoría de servicio vía AJAX"""
    try:
        data = json.loads(request.body)
        
        categoria = CategoriaServicio.objects.create(
            nombre=data.get('nombre'),
            descripcion=data.get('descripcion', ''),
            orden=data.get('orden', 0),
            activo=True
        )
        
        return JsonResponse({
            'success': True,
            'categoria_id': categoria.id,
            'message': 'Categoría creada exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
    
@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def crear_parametro_servicio(request, servicio_id):
    """Crear nuevo parámetro para un servicio"""
    try:
        servicio = get_object_or_404(ServicioBase, pk=servicio_id)
        data = json.loads(request.body)
        
        parametro = ParametroServicio.objects.create(
            servicio=servicio,
            nombre=data.get('nombre'),
            tipo=data.get('tipo'),
            requerido=data.get('requerido', True),
            opciones=data.get('opciones', ''),
            valor_por_defecto=data.get('valor_por_defecto', ''),
            orden=data.get('orden', 0)
        )
        
        return JsonResponse({
            'success': True,
            'parametro_id': parametro.id,
            'message': 'Parámetro creado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["PUT"])
def editar_parametro_servicio(request, parametro_id):
    """Editar parámetro existente"""
    try:
        parametro = get_object_or_404(ParametroServicio, pk=parametro_id)
        data = json.loads(request.body)
        
        parametro.nombre = data.get('nombre', parametro.nombre)
        parametro.tipo = data.get('tipo', parametro.tipo)
        parametro.requerido = data.get('requerido', parametro.requerido)
        parametro.opciones = data.get('opciones', parametro.opciones)
        parametro.valor_por_defecto = data.get('valor_por_defecto', parametro.valor_por_defecto)
        parametro.orden = data.get('orden', parametro.orden)
        parametro.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Parámetro actualizado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["DELETE"])
def eliminar_parametro_servicio(request, parametro_id):
    """Eliminar parámetro"""
    try:
        parametro = get_object_or_404(ParametroServicio, pk=parametro_id)
        nombre_parametro = parametro.nombre
        parametro.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Parámetro {nombre_parametro} eliminado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
def gestionar_parametros_servicio(request, servicio_id):
    """Vista para gestionar parámetros de un servicio"""
    servicio = get_object_or_404(ServicioBase, pk=servicio_id)
    parametros = servicio.parametros.all().order_by('orden')
    
    context = {
        'servicio': servicio,
        'parametros': parametros,
        'tipos_parametro': ParametroServicio.TIPO_CHOICES
    }
    
    return render(request, 'cotizaciones/gestionar_parametros.html', context)

# === Crud Materiales === 

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def crear_material(request):
    """Crear nuevo material vía AJAX"""
    try:
        data = json.loads(request.body)
        
        # Procesar fecha de último mantenimiento si viene
        fecha_ultimo_mantenimiento = None
        if data.get('fecha_ultimo_mantenimiento'):
            try:
                from datetime import datetime
                fecha_ultimo_mantenimiento = datetime.strptime(
                    data.get('fecha_ultimo_mantenimiento'), 
                    '%Y-%m-%d'
                ).date()
            except:
                pass
        
        material = Material.objects.create(
            codigo=data.get('codigo'),
            nombre=data.get('nombre'),
            descripcion=data.get('descripcion', ''),
            precio_unitario=data.get('precio_unitario'),
            unidad=data.get('unidad', 'UND'),
            categoria=data.get('categoria', ''),
            activo=data.get('activo', True),
            
            # Campos de mantenimiento
            requiere_mantenimiento=data.get('requiere_mantenimiento', False),
            
            # ⏱️ NUEVO: Tipo de mantenimiento
            tipo_mantenimiento=data.get('tipo_mantenimiento', 'dias'),
            
            # Campos para mantenimiento por DÍAS
            dias_entre_mantenimiento=data.get('dias_entre_mantenimiento') or None,
            dias_alerta_previa=data.get('dias_alerta_previa', 7),
            fecha_ultimo_mantenimiento=fecha_ultimo_mantenimiento,
            
            # ⏱️ NUEVO: Campos para mantenimiento por HORAS
            horas_entre_mantenimiento=data.get('horas_entre_mantenimiento') or None,
            horas_alerta_previa=data.get('horas_alerta_previa', 10),
            horas_uso_acumuladas=data.get('horas_uso_acumuladas', 0),
        )
        
        return JsonResponse({
            'success': True,
            'material_id': material.id,
            'message': 'Material creado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["GET"])
def obtener_material(request, material_id):
    """Obtener datos de un material vía AJAX"""
    try:
        material = get_object_or_404(Material, pk=material_id)
        
        return JsonResponse({
            'success': True,
            'material': {
                'id': material.id,
                'codigo': material.codigo,
                'nombre': material.nombre,
                'descripcion': material.descripcion or '',
                'precio_unitario': float(material.precio_unitario),
                'unidad': material.unidad,
                'categoria': material.categoria or '',
                'activo': material.activo,
                'requiere_mantenimiento': material.requiere_mantenimiento,
                
                # ⏱️ NUEVO: Tipo de mantenimiento
                'tipo_mantenimiento': material.tipo_mantenimiento,
                
                # Campos DÍAS
                'dias_entre_mantenimiento': material.dias_entre_mantenimiento,
                'dias_alerta_previa': material.dias_alerta_previa,
                'fecha_ultimo_mantenimiento': material.fecha_ultimo_mantenimiento.isoformat() if material.fecha_ultimo_mantenimiento else None,
                
                # ⏱️ NUEVO: Campos HORAS
                'horas_entre_mantenimiento': material.horas_entre_mantenimiento,
                'horas_alerta_previa': material.horas_alerta_previa,
                'horas_uso_acumuladas': float(material.horas_uso_acumuladas),
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["PUT"])
def editar_material(request, material_id):
    """Editar material existente vía AJAX"""
    try:
        material = get_object_or_404(Material, pk=material_id)
        data = json.loads(request.body)
        
        material.codigo = data.get('codigo', material.codigo)
        material.nombre = data.get('nombre', material.nombre)
        material.descripcion = data.get('descripcion', material.descripcion)
        material.precio_unitario = data.get('precio_unitario', material.precio_unitario)
        material.unidad = data.get('unidad', material.unidad)
        material.categoria = data.get('categoria', material.categoria)
        material.activo = data.get('activo', material.activo)
        
        # Campos de mantenimiento
        material.requiere_mantenimiento = data.get('requiere_mantenimiento', False)
        
        # ⏱️ NUEVO: Tipo de mantenimiento
        material.tipo_mantenimiento = data.get('tipo_mantenimiento', 'dias')
        
        if material.requiere_mantenimiento:
            # Campos para DÍAS
            material.dias_entre_mantenimiento = data.get('dias_entre_mantenimiento') or None
            material.dias_alerta_previa = data.get('dias_alerta_previa', 7)
            
            # Procesar fecha de último mantenimiento
            fecha_str = data.get('fecha_ultimo_mantenimiento')
            if fecha_str:
                try:
                    from datetime import datetime
                    material.fecha_ultimo_mantenimiento = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                except:
                    pass
            else:
                if not material.fecha_ultimo_mantenimiento:
                    material.fecha_ultimo_mantenimiento = None
            
            # ⏱️ NUEVO: Campos para HORAS
            material.horas_entre_mantenimiento = data.get('horas_entre_mantenimiento') or None
            material.horas_alerta_previa = data.get('horas_alerta_previa', 10)
            material.horas_uso_acumuladas = data.get('horas_uso_acumuladas', 0)
        else:
            # Si se desmarca, limpiar todos los campos
            material.dias_entre_mantenimiento = None
            material.dias_alerta_previa = 7
            material.fecha_ultimo_mantenimiento = None
            material.horas_entre_mantenimiento = None
            material.horas_alerta_previa = 10
            material.horas_uso_acumuladas = 0
        
        material.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Material actualizado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["DELETE"])
def eliminar_material(request, material_id):
    try:
        material = get_object_or_404(Material, pk=material_id)
        nombre_material = material.nombre
        material.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Material {nombre_material} eliminado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
    
@login_required
@requiere_gerente_o_superior
def validar_codigo_material(request):
    """Validar si un código de material está disponible"""
    codigo = request.GET.get('codigo', '')
    existe = Material.objects.filter(codigo=codigo).exists()
    
    return JsonResponse({
        'disponible': not existe,
        'codigo': codigo
    })

@login_required
@requiere_admin
@require_http_methods(["POST"])
def registrar_mantenimiento_material(request, material_id):
    """Registra que se realizó el mantenimiento de un material"""
    try:
        material = get_object_or_404(Material, pk=material_id)
        
        if not material.requiere_mantenimiento:
            return JsonResponse({
                'success': False,
                'error': 'Este material no requiere mantenimiento'
            })
        
        # ⏱️ MANEJO SEGÚN TIPO DE MANTENIMIENTO
        if material.tipo_mantenimiento == 'horas':
            # Para mantenimiento por HORAS: Reiniciar contador
            material.horas_uso_acumuladas = 0
            mensaje_notificacion = f'Se ha registrado exitosamente el mantenimiento del material "{material.nombre}". El contador de horas se ha reiniciado a 0. Próximo mantenimiento en {material.horas_entre_mantenimiento} horas de uso.'
            nueva_fecha_texto = f'Contador reiniciado a 0 horas'
            
        else:
            # Para mantenimiento por DÍAS: Actualizar fecha
            material.fecha_ultimo_mantenimiento = timezone.now().date()
            mensaje_notificacion = f'Se ha registrado exitosamente el mantenimiento del material "{material.nombre}". Próximo mantenimiento en {material.dias_entre_mantenimiento} días.'
            nueva_fecha_texto = material.fecha_ultimo_mantenimiento.strftime('%d/%m/%Y')
        
        material.save()
        
        # Crear notificación de confirmación para el usuario
        crear_notificacion(
            usuario=request.user,
            titulo=f'✓ Mantenimiento registrado: {material.codigo}',
            mensaje=mensaje_notificacion,
            tipo='success',
            url=f'/cotizaciones/materiales/?buscar={material.codigo}',
            datos_extra={
                'material_id': material.id,
                'material_codigo': material.codigo,
                'tipo_mantenimiento': material.tipo_mantenimiento,
                'fecha_mantenimiento': material.fecha_ultimo_mantenimiento.isoformat() if material.fecha_ultimo_mantenimiento else None,
                'horas_acumuladas': float(material.horas_uso_acumuladas) if material.tipo_mantenimiento == 'horas' else None,
            }
        )
        
        estado = material.get_estado_mantenimiento()
        
        return JsonResponse({
            'success': True,
            'message': f'Mantenimiento registrado para {material.nombre}',
            'nueva_fecha': nueva_fecha_texto,
            'estado_mantenimiento': estado
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
def obtener_alertas_mantenimiento(request):
    """Obtiene lista de materiales que necesitan mantenimiento"""
    try:
        materiales_mantenimiento = Material.objects.filter(
            requiere_mantenimiento=True,
            activo=True,
            fecha_ultimo_mantenimiento__isnull=False,
            dias_entre_mantenimiento__isnull=False
        )
        
        alertas = []
        for material in materiales_mantenimiento:
            dias = material.dias_hasta_proximo_mantenimiento()
            if dias is not None and dias <= material.dias_alerta_previa:
                estado = material.get_estado_mantenimiento()
                alertas.append({
                    'id': material.id,
                    'codigo': material.codigo,
                    'nombre': material.nombre,
                    'categoria': material.categoria,
                    'dias_restantes': dias,
                    'estado': estado,
                    'fecha_ultimo': material.fecha_ultimo_mantenimiento.strftime('%d/%m/%Y') if material.fecha_ultimo_mantenimiento else None,
                })
        
        # Ordenar: vencidos primero, luego por días restantes
        alertas.sort(key=lambda x: (x['dias_restantes'] >= 0, x['dias_restantes']))
        
        return JsonResponse({
            'success': True,
            'alertas': alertas,
            'total': len(alertas)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def importar_materiales_csv(request):
    """Importar materiales desde archivo CSV"""
    try:
        if 'archivo' not in request.FILES:
            return JsonResponse({'success': False, 'error': 'No se encontró archivo'})
        
        archivo = request.FILES['archivo']
        actualizar_existentes = request.POST.get('actualizar_existentes') == 'true'
        
        # Leer archivo CSV
        contenido = archivo.read().decode('utf-8')
        lineas = contenido.strip().split('\n')
        
        if len(lineas) < 2:
            return JsonResponse({'success': False, 'error': 'Archivo CSV vacío o sin datos'})
        
        # Procesar header
        headers = [h.strip().lower() for h in lineas[0].split(',')]
        required_fields = ['codigo', 'nombre', 'precio_unitario']
        
        for field in required_fields:
            if field not in headers:
                return JsonResponse({'success': False, 'error': f'Campo requerido faltante: {field}'})
        
        materiales_creados = 0
        materiales_actualizados = 0
        
        # Procesar datos
        for i, linea in enumerate(lineas[1:], 2):
            try:
                valores = [v.strip().strip('"') for v in linea.split(',')]
                if len(valores) != len(headers):
                    continue
                
                data = dict(zip(headers, valores))
                
                # Validar datos requeridos
                if not data.get('codigo') or not data.get('nombre'):
                    continue
                
                material_data = {
                    'codigo': data['codigo'],
                    'nombre': data['nombre'],
                    'categoria': data.get('categoria', ''),
                    'precio_unitario': float(data['precio_unitario']),
                    'unidad': data.get('unidad', 'UND'),
                    'descripcion': data.get('descripcion', ''),
                    'activo': True
                }
                
                # Verificar si existe
                material_existente = Material.objects.filter(codigo=data['codigo']).first()
                
                if material_existente:
                    if actualizar_existentes:
                        for key, value in material_data.items():
                            setattr(material_existente, key, value)
                        material_existente.save()
                        materiales_actualizados += 1
                else:
                    Material.objects.create(**material_data)
                    materiales_creados += 1
                    
            except (ValueError, IndexError) as e:
                continue  # Saltar líneas con errores
        
        mensaje = f'Importación completada: {materiales_creados} creados'
        if materiales_actualizados:
            mensaje += f', {materiales_actualizados} actualizados'
        
        return JsonResponse({
            'success': True,
            'materiales_creados': materiales_creados,
            'materiales_actualizados': materiales_actualizados,
            'message': mensaje
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
def gestionar_categorias_empleados(request):
    """Gestión de categorías de empleados"""
    try:
        # Importar modelos
        from .models import CategoriaEmpleado, EmpleadoCategoria
        
        # Obtener categorías con prefetch para optimizar consultas
        categorias = CategoriaEmpleado.objects.prefetch_related('empleados').all().order_by('orden', 'nombre')
        
        # Obtener empleados disponibles para asignación
        empleados_disponibles = PerfilEmpleado.objects.filter(
            activo=True
        ).exclude(
            cargo='admin'  
        ).select_related('user').order_by('user__first_name')
        
        # Obtener asignaciones actuales para mostrar en la tabla
        asignaciones_actuales = EmpleadoCategoria.objects.filter(
            activo=True
        ).select_related('empleado__user', 'categoria').order_by('categoria__orden', 'empleado__user__first_name')
        
        context = {
            'categorias': categorias,
            'empleados_disponibles': empleados_disponibles,
            'asignaciones_actuales': asignaciones_actuales,
            'total_empleados': empleados_disponibles.count()
        }
        
        return render(request, 'cotizaciones/gestionar_categorias_empleados.html', context)
        
    except ImportError:
        messages.error(request, 'Los modelos de categorías de empleados no están configurados. Ejecuta las migraciones.')
        return redirect('home:panel_empleados')
    except Exception as e:
        messages.error(request, f'Error al cargar categorías: {str(e)}')
        return redirect('home:panel_empleados')

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def crear_categoria_empleado(request):
    """Crear nueva categoría de empleado"""
    try:
        data = json.loads(request.body)
        
        categoria = CategoriaEmpleado.objects.create(
            nombre=data.get('nombre'),
            descripcion=data.get('descripcion', ''),
            orden=data.get('orden', 0),
            activo=data.get('activo', True)
        )
        
        return JsonResponse({
            'success': True,
            'categoria_id': categoria.id,
            'message': 'Categoría creada exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["PUT"])
def editar_categoria_empleado(request, categoria_id):
    """Editar categoría de empleado"""
    try:
        categoria = get_object_or_404(CategoriaEmpleado, pk=categoria_id)
        data = json.loads(request.body)
        
        categoria.nombre = data.get('nombre', categoria.nombre)
        categoria.descripcion = data.get('descripcion', categoria.descripcion)
        categoria.orden = data.get('orden', categoria.orden)
        categoria.activo = data.get('activo', categoria.activo)
        categoria.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Categoría actualizada exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["DELETE"])
def eliminar_categoria_empleado(request, categoria_id):
    """Eliminar categoría de empleado"""
    try:
        categoria = get_object_or_404(CategoriaEmpleado, pk=categoria_id)
        nombre_categoria = categoria.nombre
        categoria.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Categoría {nombre_categoria} eliminada exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

# === ASIGNACIÓN DE EMPLEADOS A CATEGORÍAS ===

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def asignar_empleado_categoria(request):
    """Asignar empleado a categoría"""
    try:
        data = json.loads(request.body)
        
        empleado = get_object_or_404(PerfilEmpleado, pk=data.get('empleado_id'))
        categoria = get_object_or_404(CategoriaEmpleado, pk=data.get('categoria_id'))
        
        # Verificar si ya existe la asignación
        asignacion_existente = EmpleadoCategoria.objects.filter(
            empleado=empleado,
            categoria=categoria
        ).first()
        
        if asignacion_existente:
            return JsonResponse({
                'success': False,
                'error': 'El empleado ya está asignado a esta categoría'
            })
        
        asignacion = EmpleadoCategoria.objects.create(
            empleado=empleado,
            categoria=categoria,
            activo=True
        )
        
        return JsonResponse({
            'success': True,
            'asignacion_id': asignacion.id,
            'message': f'{empleado.nombre_completo} asignado a {categoria.nombre}'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["DELETE"])
def eliminar_empleado_categoria(request, asignacion_id):
    """Eliminar asignación de empleado a categoría"""
    try:
        asignacion = get_object_or_404(EmpleadoCategoria, pk=asignacion_id)
        empleado_nombre = asignacion.empleado.nombre_completo
        categoria_nombre = asignacion.categoria.nombre
        asignacion.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'{empleado_nombre} removido de {categoria_nombre}'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
def obtener_empleados_categoria(request, categoria_id):
    """Obtener empleados de una categoría específica"""
    empleados = PerfilEmpleado.objects.filter(
        activo=True,
        cargo='empleado',
        categorias_trabajo__categoria_id=categoria_id,
        categorias_trabajo__activo=True
    ).select_related('user').distinct()
    
    empleados_data = []
    for empleado in empleados:
        empleados_data.append({
            'id': empleado.id,
            'nombre': empleado.nombre_completo,
            'telefono': empleado.telefono or '',
        })
    
    return JsonResponse(empleados_data, safe=False)

# === GESTIÓN DE EMPLEADOS EN MANO DE OBRA ===

@login_required
@requiere_gerente_o_superior
def gestionar_empleados_mano_obra(request, cotizacion_pk, item_pk):
    """Gestionar empleados asignados a un item de mano de obra"""
    cotizacion = get_object_or_404(Cotizacion, pk=cotizacion_pk)
    item_mano_obra = get_object_or_404(ItemManoObra, pk=item_pk, cotizacion=cotizacion)
    
    # Obtener empleados ya asignados
    empleados_asignados = ItemManoObraEmpleado.objects.filter(
        item_mano_obra=item_mano_obra
    ).select_related('empleado__user')
    
    # Calcular estadísticas
    total_horas_asignadas = sum(asignacion.horas_asignadas for asignacion in empleados_asignados)
    empleados_completados = empleados_asignados.filter(completado=True).count()
    
    # Obtener categorías disponibles para filtrar empleados
    try:
        categorias_empleados = CategoriaEmpleado.objects.filter(activo=True)
    except:
        categorias_empleados = []
    
    context = {
        'cotizacion': cotizacion,
        'item_mano_obra': item_mano_obra,
        'empleados_asignados': empleados_asignados,
        'categorias_empleados': categorias_empleados,
        'total_horas_asignadas': total_horas_asignadas,
        'empleados_completados': empleados_completados,
    }
    
    return render(request, 'cotizaciones/gestionar_empleados_mano_obra.html', context)

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def agregar_empleado_mano_obra(request, cotizacion_pk, item_pk):
    """Agregar empleado a item de mano de obra"""
    try:
        cotizacion = get_object_or_404(Cotizacion, pk=cotizacion_pk)
        item_mano_obra = get_object_or_404(ItemManoObra, pk=item_pk, cotizacion=cotizacion)
        
        data = json.loads(request.body)
        empleado_id = data.get('empleado_id')
        horas_asignadas = data.get('horas_asignadas', 0)
        observaciones = data.get('observaciones', '')
        
        empleado = get_object_or_404(PerfilEmpleado, pk=empleado_id)
        
        # Verificar si ya está asignado
        asignacion_existente = ItemManoObraEmpleado.objects.filter(
            item_mano_obra=item_mano_obra,
            empleado=empleado
        ).first()
        
        if asignacion_existente:
            return JsonResponse({
                'success': False,
                'error': 'El empleado ya está asignado a este trabajo'
            })
        
        with transaction.atomic():
            # Crear asignación
            asignacion = ItemManoObraEmpleado.objects.create(
                item_mano_obra=item_mano_obra,
                empleado=empleado,
                horas_asignadas=horas_asignadas,
                observaciones=observaciones
            )
            
            # Crear registro en TrabajoEmpleado para la vista del empleado
            TrabajoEmpleado.objects.create(
                empleado=empleado,
                cotizacion=cotizacion,
                item_mano_obra=item_mano_obra,
                estado='pendiente'
            )
        
        return JsonResponse({
            'success': True,
            'asignacion_id': asignacion.id,
            'message': f'{empleado.nombre_completo} asignado al trabajo'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["DELETE"])
def eliminar_empleado_mano_obra(request, cotizacion_pk, item_pk, empleado_id):
    """Eliminar empleado de item de mano de obra"""
    try:
        cotizacion = get_object_or_404(Cotizacion, pk=cotizacion_pk)
        item_mano_obra = get_object_or_404(ItemManoObra, pk=item_pk, cotizacion=cotizacion)
        empleado = get_object_or_404(PerfilEmpleado, pk=empleado_id)
        
        # Eliminar asignación
        asignacion = get_object_or_404(
            ItemManoObraEmpleado,
            item_mano_obra=item_mano_obra,
            empleado=empleado
        )
        
        # También eliminar de TrabajoEmpleado
        trabajo_empleado = TrabajoEmpleado.objects.filter(
            empleado=empleado,
            item_mano_obra=item_mano_obra
        ).first()
        
        with transaction.atomic():
            asignacion.delete()
            if trabajo_empleado:
                trabajo_empleado.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'{empleado.nombre_completo} removido del trabajo'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

# === VISTAS PARA EMPLEADOS ===

@login_required
def mis_trabajos_empleado(request):
    """Vista de trabajos para empleados"""
    try:
        perfil_empleado = request.user.perfilempleado
    except PerfilEmpleado.DoesNotExist:
        messages.error(request, 'No tienes un perfil de empleado asignado')
        return redirect('home:panel_empleados')
    
    # Obtener trabajos del empleado - SOLO DE COTIZACIONES APROBADAS
    trabajos = TrabajoEmpleado.objects.filter(
        empleado=perfil_empleado,
        cotizacion__estado='aprobada'  # FILTRO CRÍTICO: Solo trabajos aprobados
    ).select_related(
        'cotizacion__cliente',
        'item_mano_obra'
    ).order_by('-id', 'estado')
    
    # Filtros
    estado_filtro = request.GET.get('estado', '')
    if estado_filtro and trabajos.exists():
        trabajos = trabajos.filter(estado=estado_filtro)
    
    # Estadísticas
    from django.db.models import Sum
    stats = {
        'pendientes': trabajos.filter(estado='pendiente').count(),
        'en_progreso': trabajos.filter(estado='en_progreso').count(),
        'completados': trabajos.filter(estado='completado').count(),
        'total_horas': trabajos.aggregate(total=Sum('horas_trabajadas'))['total'] or 0
    }
    
    context = {
        'trabajos': trabajos,
        'stats': stats,
        'estado_filtro': estado_filtro,
        'estados_choices': [
            ('pendiente', 'Pendiente'),
            ('en_progreso', 'En Progreso'),
            ('completado', 'Completado'),
            ('suspendido', 'Suspendido'),
        ],
        'perfil_empleado': perfil_empleado,
        'model_exists': True,
    }

    # Detectar si la petición es desde la app móvil
    if request.headers.get('Accept') == 'application/json':
        trabajos_data = []
        
        for trabajo in trabajos:
            trabajos_data.append({
                'id': trabajo.id,
                'numero_cotizacion': trabajo.cotizacion.numero_cotizacion,
                'cliente': trabajo.cotizacion.cliente.nombre,
                'descripcion': trabajo.item_mano_obra.categoria_empleado.nombre if trabajo.item_mano_obra else 'Sin descripción',
                'estado': trabajo.estado,
                'fecha_asignacion': trabajo.fecha_asignacion.strftime('%Y-%m-%d') if trabajo.fecha_asignacion else None,
                'fecha_entrega': trabajo.cotizacion.fecha_estimada.strftime('%Y-%m-%d') if trabajo.cotizacion.fecha_estimada else None,
                'horas_trabajadas': float(trabajo.horas_trabajadas or 0),
                'observaciones': trabajo.observaciones_empleado or '',
            })
        
        return JsonResponse({
            'success': True,
            'trabajos': trabajos_data,
            'estadisticas': stats
        })
    
    return render(request, 'cotizaciones/mis_trabajos_empleado.html', context)

@login_required
@require_http_methods(["POST"])
def actualizar_trabajo_empleado(request, trabajo_id):
    """Actualizar estado y detalles de trabajo por empleado"""
    try:
        perfil_empleado = request.user.perfilempleado
        trabajo = get_object_or_404(
            TrabajoEmpleado,
            pk=trabajo_id,
            empleado=perfil_empleado
        )
        
        data = json.loads(request.body)
        
        # Actualizar campos permitidos
        trabajo.estado = data.get('estado', trabajo.estado)
        trabajo.horas_trabajadas = data.get('horas_trabajadas', trabajo.horas_trabajadas)
        trabajo.observaciones_empleado = data.get('observaciones_empleado', trabajo.observaciones_empleado)
        
        # Manejar fechas de inicio y fin
        if data.get('estado') == 'en_progreso' and not trabajo.fecha_inicio:
            trabajo.fecha_inicio = timezone.now()
        elif data.get('estado') == 'completado':
            if not trabajo.fecha_fin:
                trabajo.fecha_fin = timezone.now()
        
        trabajo.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Trabajo actualizado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@require_http_methods(["POST"])
def completar_trabajo_empleado(request, trabajo_id):
    """Marcar trabajo como completado"""
    try:
        perfil_empleado = request.user.perfilempleado
        trabajo = get_object_or_404(
            TrabajoEmpleado,
            pk=trabajo_id,
            empleado=perfil_empleado
        )
        
        trabajo.estado = 'completado'
        trabajo.fecha_fin = timezone.now()
        trabajo.save()
        
        # También actualizar la asignación en ItemManoObraEmpleado
        asignacion = ItemManoObraEmpleado.objects.filter(
            item_mano_obra=trabajo.item_mano_obra,
            empleado=perfil_empleado
        ).first()
        
        if asignacion:
            asignacion.marcar_completado()
        
        return JsonResponse({
            'success': True,
            'message': 'Trabajo marcado como completado'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

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

# === Reportes ===

@login_required
@requiere_gerente_o_superior
def datos_dashboard_reportes(request):
    """API endpoint para datos del dashboard de reportes"""
    try:
        periodo = request.GET.get('periodo', 'mes-actual')
        hoy = timezone.now()
        
        print(f"\n{'='*50}")
        print(f"DEBUG - Periodo: {periodo}")
        print(f"DEBUG - Fecha actual: {hoy} (Mes: {hoy.month}, Año: {hoy.year})")
        
        # Determinar base_query según el período (SOLO PARA KPIs, NO PARA GRÁFICA)
        if periodo == 'todos':
            base_query = Cotizacion.objects.all()
            print(f"DEBUG - TODOS (sin filtro)")
        elif periodo == 'mes-actual':
            base_query = Cotizacion.objects.filter(
                fecha_creacion__year=hoy.year,
                fecha_creacion__month=hoy.month
            )
            print(f"DEBUG - Mes actual: {hoy.month}/{hoy.year}")
        elif periodo == 'mes-anterior':
            mes_anterior = hoy.month - 1 if hoy.month > 1 else 12
            ano_anterior = hoy.year if hoy.month > 1 else hoy.year - 1
            base_query = Cotizacion.objects.filter(
                fecha_creacion__year=ano_anterior,
                fecha_creacion__month=mes_anterior
            )
            print(f"DEBUG - Mes anterior: {mes_anterior}/{ano_anterior}")
        elif periodo.startswith('mes-') and len(periodo.split('-')) == 3:
            parts = periodo.split('-')
            mes = int(parts[1])
            ano = int(parts[2])
            base_query = Cotizacion.objects.filter(
                fecha_creacion__year=ano,
                fecha_creacion__month=mes
            )
            print(f"DEBUG - Mes específico: {mes}/{ano}")
        elif periodo == 'ano':
            base_query = Cotizacion.objects.filter(fecha_creacion__year=hoy.year)
            print(f"DEBUG - Año actual: {hoy.year}")
        elif periodo.startswith('ano-'):
            ano = int(periodo.split('-')[1])
            base_query = Cotizacion.objects.filter(fecha_creacion__year=ano)
            print(f"DEBUG - Año específico: {ano}")
        elif periodo == 'trimestre':
            fecha_inicio = hoy - timedelta(days=90)
            base_query = Cotizacion.objects.filter(fecha_creacion__gte=fecha_inicio)
            print(f"DEBUG - Trimestre desde: {fecha_inicio}")
        elif periodo == 'semestre':
            fecha_inicio = hoy - timedelta(days=180)
            base_query = Cotizacion.objects.filter(fecha_creacion__gte=fecha_inicio)
            print(f"DEBUG - Semestre desde: {fecha_inicio}")
        else:
            base_query = Cotizacion.objects.filter(fecha_creacion__year=hoy.year)
            print(f"DEBUG - Default (año actual): {hoy.year}")
        
        total_encontradas = base_query.count()
        print(f"DEBUG - Cotizaciones encontradas: {total_encontradas}")
        print(f"{'='*50}\n")
        
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
            empleados = PerfilEmpleado.objects.filter(activo=True, cargo='empleado').annotate(
                trabajos_asignados=Count('trabajos_asignados'),
                horas_total=Sum('trabajos_asignados__horas_trabajadas'),
                trabajos_completados=Count('trabajos_asignados', filter=Q(trabajos_asignados__estado='completado'))
            ).order_by('-trabajos_asignados')[:5]
            for empleado in empleados:
                tasa_completada = round((empleado.trabajos_completados / empleado.trabajos_asignados * 100) if empleado.trabajos_asignados > 0 else 0)
                empleados_productivos.append({
                    'nombre': empleado.nombre_completo,
                    'trabajos': empleado.trabajos_asignados,
                    'horasTotal': empleado.horas_total or 0,
                    'tasaCompleta': tasa_completada
                })
        except:
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

# === FUNCIONES DE EXPORTACIÓN ===

@login_required
@requiere_gerente_o_superior
def exportar_clientes(request):
    """Exportar clientes a Excel o CSV"""
    formato = request.GET.get('formato', 'excel')
    
    # Aplicar los mismos filtros que en la vista principal
    clientes = Cliente.objects.all().order_by('nombre')
    busqueda = request.GET.get('busqueda', '')
    if busqueda:
        clientes = clientes.filter(
            Q(nombre__icontains=busqueda) |
            Q(rut__icontains=busqueda) |
            Q(email__icontains=busqueda)
        )
    
    if formato == 'csv':
        return exportar_clientes_csv(clientes)
    else:
        return exportar_clientes_excel(clientes)

def exportar_clientes_csv(clientes):
    """Exportar clientes a CSV"""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="clientes.csv"'
    response.write('\ufeff')
    
    writer = csv.writer(response)
    writer.writerow([
        'Nombre', 'RUT', 'Dirección', 'Teléfono', 'Email', 'Fecha Creación'
    ])
    
    for cliente in clientes:
        # Obtener representantes
        representantes = ', '.join([r.nombre for r in cliente.representantes.all()])
        
        writer.writerow([
            cliente.nombre,
            cliente.rut or '',
            cliente.direccion or '',
            cliente.telefono or '',
            cliente.email or '',
            cliente.fecha_creacion.strftime('%d/%m/%Y'),
        ])
    
    return response

def exportar_clientes_excel(clientes):
    """Exportar clientes a Excel"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Clientes"
    
    # Estilos
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Encabezados
    headers = ['Nombre', 'Representantes', 'RUT', 'Dirección', 'Teléfono', 'Email', 'Fecha Creación']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = border
    
    # Datos
    for row, cliente in enumerate(clientes, 2):
        # Obtener representantes
        representantes = ', '.join([r.nombre for r in cliente.representantes.all()])
        
        ws.cell(row=row, column=1, value=cliente.nombre).border = border
        ws.cell(row=row, column=2, value=representantes or '-').border = border
        ws.cell(row=row, column=3, value=cliente.rut or '').border = border
        ws.cell(row=row, column=4, value=cliente.direccion or '').border = border
        ws.cell(row=row, column=5, value=cliente.telefono or '').border = border
        ws.cell(row=row, column=6, value=cliente.email or '').border = border
        ws.cell(row=row, column=7, value=cliente.fecha_creacion.strftime('%d/%m/%Y')).border = border
    
    # Ajustar ancho de columnas
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 20
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="clientes.xlsx"'
    wb.save(response)
    
    return response

@login_required
@requiere_gerente_o_superior
def exportar_servicios(request):
    """Exportar servicios a Excel o CSV"""
    formato = request.GET.get('formato', 'excel')
    
    servicios = ServicioBase.objects.select_related('categoria').order_by('categoria__nombre', 'nombre')
    categoria_filtro = request.GET.get('categoria', '')
    if categoria_filtro:
        servicios = servicios.filter(categoria_id=categoria_filtro)
    
    if formato == 'csv':
        return exportar_servicios_csv(servicios)
    else:
        return exportar_servicios_excel(servicios)

def exportar_servicios_csv(servicios):
    """Exportar servicios a CSV"""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="servicios.csv"'
    response.write('\ufeff')
    
    writer = csv.writer(response)
    writer.writerow([
        'Categoría', 'Nombre', 'Descripción', 'Precio Base', 
        'Unidad', 'Parametrizable', 'Estado'
    ])
    
    for servicio in servicios:
        writer.writerow([
            servicio.categoria.nombre,
            servicio.nombre,
            servicio.descripcion,
            float(servicio.precio_base),
            servicio.unidad,
            'Sí' if servicio.es_parametrizable else 'No',
            'Activo' if servicio.activo else 'Inactivo'
        ])
    
    return response

def exportar_servicios_excel(servicios):
    """Exportar servicios a Excel"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Servicios"
    
    # Estilos
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Encabezados
    headers = ['Categoría', 'Nombre', 'Descripción', 'Precio Base', 'Unidad', 'Parametrizable', 'Estado']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = border
    
    # Datos
    for row, servicio in enumerate(servicios, 2):
        ws.cell(row=row, column=1, value=servicio.categoria.nombre).border = border
        ws.cell(row=row, column=2, value=servicio.nombre).border = border
        ws.cell(row=row, column=3, value=servicio.descripcion).border = border
        ws.cell(row=row, column=4, value=float(servicio.precio_base)).border = border
        ws.cell(row=row, column=5, value=servicio.unidad).border = border
        ws.cell(row=row, column=6, value='Sí' if servicio.es_parametrizable else 'No').border = border
        ws.cell(row=row, column=7, value='Activo' if servicio.activo else 'Inactivo').border = border
    
    # Ajustar ancho de columnas
    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 30
    ws.column_dimensions['C'].width = 40
    ws.column_dimensions['D'].width = 15
    ws.column_dimensions['E'].width = 12
    ws.column_dimensions['F'].width = 15
    ws.column_dimensions['G'].width = 12
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="servicios.xlsx"'
    wb.save(response)
    
    return response

@login_required
@requiere_gerente_o_superior
def exportar_materiales(request):
    """Exportar materiales a Excel o CSV"""
    formato = request.GET.get('formato', 'excel')
    
    materiales = Material.objects.all().order_by('categoria', 'nombre')
    busqueda = request.GET.get('busqueda', '')
    categoria_filtro = request.GET.get('categoria', '')
    
    if busqueda:
        materiales = materiales.filter(
            Q(nombre__icontains=busqueda) |
            Q(codigo__icontains=busqueda) |
            Q(descripcion__icontains=busqueda)
        )
    
    if categoria_filtro:
        materiales = materiales.filter(categoria=categoria_filtro)
    
    if formato == 'csv':
        return exportar_materiales_csv(materiales)
    else:
        return exportar_materiales_excel(materiales)

def exportar_materiales_csv(materiales):
    """Exportar materiales a CSV"""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="materiales.csv"'
    response.write('\ufeff')
    
    writer = csv.writer(response)
    writer.writerow([
        'Código', 'Nombre', 'Descripción', 'Categoría', 
        'Precio Unitario', 'Unidad', 'Estado'
    ])
    
    for material in materiales:
        writer.writerow([
            material.codigo,
            material.nombre,
            material.descripcion or '',
            material.categoria or '',
            float(material.precio_unitario),
            material.unidad,
            'Activo' if material.activo else 'Inactivo'
        ])
    
    return response

def exportar_materiales_excel(materiales):
    """Exportar materiales a Excel"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Materiales"
    
    # Estilos
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Encabezados
    headers = ['Código', 'Nombre', 'Descripción', 'Categoría', 'Precio Unitario', 'Unidad', 'Estado']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = border
    
    # Datos
    for row, material in enumerate(materiales, 2):
        ws.cell(row=row, column=1, value=material.codigo).border = border
        ws.cell(row=row, column=2, value=material.nombre).border = border
        ws.cell(row=row, column=3, value=material.descripcion or '').border = border
        ws.cell(row=row, column=4, value=material.categoria or '').border = border
        ws.cell(row=row, column=5, value=float(material.precio_unitario)).border = border
        ws.cell(row=row, column=6, value=material.unidad).border = border
        ws.cell(row=row, column=7, value='Activo' if material.activo else 'Inactivo').border = border
    
    # Ajustar ancho de columnas
    ws.column_dimensions['A'].width = 15
    ws.column_dimensions['B'].width = 30
    ws.column_dimensions['C'].width = 40
    ws.column_dimensions['D'].width = 20
    ws.column_dimensions['E'].width = 15
    ws.column_dimensions['F'].width = 12
    ws.column_dimensions['G'].width = 12
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="materiales.xlsx"'
    wb.save(response)
    
    return response

@login_required
@requiere_gerente_o_superior
def exportar_cotizaciones(request):
    """Exportar cotizaciones a Excel o CSV"""
    formato = request.GET.get('formato', 'excel')
    
    cotizaciones = Cotizacion.objects.select_related('cliente', 'tipo_trabajo').order_by('-fecha_creacion')
    
    # Aplicar filtros
    busqueda = request.GET.get('busqueda', '')
    estado = request.GET.get('estado', '')
    cliente_id = request.GET.get('cliente', '')
    
    if busqueda:
        cotizaciones = cotizaciones.filter(
            Q(numero__icontains=busqueda) |
            Q(cliente__nombre__icontains=busqueda) |
            Q(referencia__icontains=busqueda)
        )
    
    if estado:
        cotizaciones = cotizaciones.filter(estado=estado)
        
    if cliente_id:
        cotizaciones = cotizaciones.filter(cliente_id=cliente_id)
    
    if formato == 'csv':
        return exportar_cotizaciones_csv(cotizaciones)
    else:
        return exportar_cotizaciones_excel(cotizaciones)

def exportar_cotizaciones_csv(cotizaciones):
    """Exportar cotizaciones a CSV"""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="cotizaciones.csv"'
    response.write('\ufeff')
    
    writer = csv.writer(response)
    writer.writerow([
        'Número', 'Cliente', 'Referencia', 'Lugar', 'Tipo Trabajo',
        'Fecha Creación', 'Estado', 'Valor Neto', 'IVA', 'Valor Total'
    ])
    
    for cot in cotizaciones:
        writer.writerow([
            cot.numero,
            cot.cliente.nombre if cot.cliente else 'Sin cliente',
            cot.referencia,
            cot.lugar,
            cot.tipo_trabajo.nombre if cot.tipo_trabajo else 'Sin tipo',
            cot.fecha_creacion.strftime('%d/%m/%Y'),
            cot.get_estado_display(),
            float(cot.valor_neto),
            float(cot.valor_iva),
            float(cot.valor_total)
        ])
    
    return response

def exportar_cotizaciones_excel(cotizaciones):
    """Exportar cotizaciones a Excel"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Cotizaciones"
    
    # Estilos
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Encabezados
    headers = ['Número', 'Cliente', 'Referencia', 'Lugar', 'Tipo Trabajo', 
               'Fecha Creación', 'Estado', 'Valor Neto', 'IVA', 'Valor Total']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = border
    
    # Datos
    for row, cot in enumerate(cotizaciones, 2):
        ws.cell(row=row, column=1, value=cot.numero).border = border
        ws.cell(row=row, column=2, value=cot.cliente.nombre if cot.cliente else 'Sin cliente').border = border
        ws.cell(row=row, column=3, value=cot.referencia).border = border
        ws.cell(row=row, column=4, value=cot.lugar).border = border
        ws.cell(row=row, column=5, value=cot.tipo_trabajo.nombre if cot.tipo_trabajo else 'Sin tipo').border = border
        ws.cell(row=row, column=6, value=cot.fecha_creacion.strftime('%d/%m/%Y')).border = border
        ws.cell(row=row, column=7, value=cot.get_estado_display()).border = border
        ws.cell(row=row, column=8, value=float(cot.valor_neto)).border = border
        ws.cell(row=row, column=9, value=float(cot.valor_iva)).border = border
        ws.cell(row=row, column=10, value=float(cot.valor_total)).border = border
    
    # Ajustar ancho de columnas
    for col in range(1, 11):
        ws.column_dimensions[get_column_letter(col)].width = 18
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="cotizaciones.xlsx"'
    wb.save(response)
    
    return response
    """Exportar cotizaciones a Excel"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Cotizaciones"
    
    # Estilos
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Encabezados
    headers = ['Número', 'Cliente', 'Referencia', 'Lugar', 'Tipo Trabajo', 
               'Fecha Creación', 'Estado', 'Valor Neto', 'IVA', 'Valor Total']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = border
    
    # Datos
    for row, cot in enumerate(cotizaciones, 2):
        ws.cell(row=row, column=1, value=cot.numero).border = border
        ws.cell(row=row, column=2, value=cot.cliente.nombre).border = border
        ws.cell(row=row, column=3, value=cot.referencia).border = border
        ws.cell(row=row, column=4, value=cot.lugar).border = border
        ws.cell(row=row, column=5, value=cot.tipo_trabajo.nombre).border = border
        ws.cell(row=row, column=6, value=cot.fecha_creacion.strftime('%d/%m/%Y')).border = border
        ws.cell(row=row, column=7, value=cot.get_estado_display()).border = border
        ws.cell(row=row, column=8, value=float(cot.valor_neto)).border = border
        ws.cell(row=row, column=9, value=float(cot.valor_iva)).border = border
        ws.cell(row=row, column=10, value=float(cot.valor_total)).border = border
    
    # Ajustar ancho de columnas
    for col in range(1, 11):
        ws.column_dimensions[get_column_letter(col)].width = 18
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="cotizaciones.xlsx"'
    wb.save(response)
    
    return response

@login_required
@requiere_gerente_o_superior
def exportar_trabajos(request):
    """Exportar trabajos en progreso a Excel o CSV"""
    from django.db.models import Count, Sum, Q
    
    formato = request.GET.get('formato', 'excel')
    
    # Filtros
    filtro_estado = request.GET.get('estado', '')
    filtro_empleado = request.GET.get('empleado', '')
    busqueda = request.GET.get('busqueda', '')
    
    # Obtener cotizaciones aprobadas con trabajos
    cotizaciones_query = Cotizacion.objects.filter(
        estado='aprobada'
    ).annotate(
        total_trabajos=Count('trabajos_empleados')
    ).filter(total_trabajos__gt=0).select_related('cliente', 'tipo_trabajo')
    
    # Recopilar todos los trabajos
    trabajos_list = []
    
    for cot in cotizaciones_query:
        trabajos_q = cot.trabajos_empleados.select_related(
            'empleado__user',
            'item_mano_obra'
        ).all()
        
        # Aplicar filtros
        if filtro_estado:
            trabajos_q = trabajos_q.filter(estado=filtro_estado)
        
        if filtro_empleado:
            trabajos_q = trabajos_q.filter(empleado_id=filtro_empleado)
        
        for trabajo in trabajos_q:
            # Filtro de búsqueda
            if busqueda:
                busqueda_lower = busqueda.lower()
                if not (busqueda_lower in cot.numero.lower() or 
                       busqueda_lower in cot.get_nombre_cliente().lower() or 
                       busqueda_lower in trabajo.item_mano_obra.descripcion.lower()):
                    continue
            
            # Calcular progreso
            progreso = 0
            if trabajo.estado == 'completado':
                progreso = 100
            elif trabajo.estado == 'en_progreso' and trabajo.horas_trabajadas > 0:
                horas_item = trabajo.item_mano_obra.horas
                if horas_item > 0:
                    progreso = min((float(trabajo.horas_trabajadas) / float(horas_item)) * 100, 99)
                else:
                    progreso = 50
            
            trabajos_list.append({
                'cotizacion': cot,
                'trabajo': trabajo,
                'progreso': progreso
            })
    
    if formato == 'csv':
        return exportar_trabajos_csv(trabajos_list)
    else:
        return exportar_trabajos_excel(trabajos_list)

def exportar_trabajos_csv(trabajos_list):
    """Exportar trabajos a CSV"""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="seguimiento_trabajos.csv"'
    response.write('\ufeff')  # BOM para UTF-8
    
    writer = csv.writer(response)
    writer.writerow([
        'Cotización', 'Cliente', 'Lugar', 'Trabajo', 'Empleado', 'Cargo',
        'Estado', 'Progreso (%)', 'Horas Trabajadas', 'Precio/Hora',
        'Fecha Inicio', 'Fecha Fin', 'Observaciones'
    ])
    
    for item in trabajos_list:
        cot = item['cotizacion']
        trabajo = item['trabajo']
        progreso = item['progreso']
        
        writer.writerow([
            cot.numero,
            cot.get_nombre_cliente(),
            cot.lugar,
            trabajo.item_mano_obra.descripcion,
            trabajo.empleado.nombre_completo,
            trabajo.empleado.get_cargo_display(),
            trabajo.get_estado_display(),
            f"{progreso:.0f}",
            f"{float(trabajo.horas_trabajadas):.1f}",
            f"{float(trabajo.item_mano_obra.precio_hora):,.0f}",
            trabajo.fecha_inicio.strftime('%d/%m/%Y %H:%M') if trabajo.fecha_inicio else 'No iniciado',
            trabajo.fecha_fin.strftime('%d/%m/%Y %H:%M') if trabajo.fecha_fin else 'En curso' if trabajo.estado == 'en_progreso' else '-',
            trabajo.observaciones_empleado or '-'
        ])
    
    return response

def exportar_trabajos_excel(trabajos_list):
    """Exportar trabajos a Excel"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Seguimiento Trabajos"
    
    # Estilos
    header_fill = PatternFill(start_color="2575C0", end_color="2575C0", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Estado fills
    completado_fill = PatternFill(start_color="D4EDDA", end_color="D4EDDA", fill_type="solid")
    en_progreso_fill = PatternFill(start_color="FFF3CD", end_color="FFF3CD", fill_type="solid")
    pendiente_fill = PatternFill(start_color="F8D7DA", end_color="F8D7DA", fill_type="solid")
    
    # Encabezados
    headers = [
        'Cotización', 'Cliente', 'Lugar', 'Trabajo', 'Empleado', 'Cargo',
        'Estado', 'Progreso (%)', 'Horas Trabajadas', 'Precio/Hora',
        'Fecha Inicio', 'Fecha Fin', 'Observaciones'
    ]
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = border
    
    # Datos
    for row_idx, item in enumerate(trabajos_list, 2):
        cot = item['cotizacion']
        trabajo = item['trabajo']
        progreso = item['progreso']
        
        # Determinar fill según estado
        if trabajo.estado == 'completado':
            row_fill = completado_fill
        elif trabajo.estado == 'en_progreso':
            row_fill = en_progreso_fill
        else:
            row_fill = pendiente_fill
        
        # Datos de la fila
        datos = [
            cot.numero,
            cot.get_nombre_cliente(),
            cot.lugar,
            trabajo.item_mano_obra.descripcion,
            trabajo.empleado.nombre_completo,
            trabajo.empleado.get_cargo_display(),
            trabajo.get_estado_display(),
            f"{progreso:.0f}%",
            f"{float(trabajo.horas_trabajadas):.1f}",
            f"${float(trabajo.item_mano_obra.precio_hora):,.0f}",
            trabajo.fecha_inicio.strftime('%d/%m/%Y %H:%M') if trabajo.fecha_inicio else 'No iniciado',
            trabajo.fecha_fin.strftime('%d/%m/%Y %H:%M') if trabajo.fecha_fin else ('En curso' if trabajo.estado == 'en_progreso' else '-'),
            trabajo.observaciones_empleado or '-'
        ]
        
        for col_idx, valor in enumerate(datos, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=valor)
            cell.border = border
            cell.alignment = Alignment(vertical='center', wrap_text=True)
            if col_idx == 7:  # Columna de estado
                cell.fill = row_fill
                cell.font = Font(bold=True)
    
    # Ajustar ancho de columnas
    column_widths = [15, 25, 20, 30, 25, 15, 15, 12, 15, 12, 18, 18, 40]
    for col_idx, width in enumerate(column_widths, 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width
    
    # Establecer altura de fila del encabezado
    ws.row_dimensions[1].height = 30
    
    # Congelar primera fila
    ws.freeze_panes = 'A2'
    
    # Preparar respuesta
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="seguimiento_trabajos.xlsx"'
    wb.save(response)
    
    return response

# === Cotizaciones Ciclo de Vida ===

@login_required
@requiere_gerente_o_superior
def enviar_cotizacion_email(request, pk):
    """
    Vista mejorada para enviar cotización por email con manejo robusto de errores
    """
    cotizacion = get_object_or_404(Cotizacion, pk=pk)
    
    # Verificar que la cotización esté en estado válido para enviar
    if cotizacion.estado not in ['borrador', 'enviada']:
        messages.warning(
            request,
            f'Esta cotización está en estado "{cotizacion.get_estado_display()}" y no puede ser enviada por email.'
        )
        return redirect('cotizaciones:detalle', pk=pk)
    
    if request.method == 'POST':
        email_destinatario = request.POST.get('email', '').strip()
        mensaje_adicional = request.POST.get('mensaje_adicional', '').strip()
        enviar_copia = request.POST.get('enviar_copia') == 'on'
        
        # Validaciones
        if not email_destinatario:
            messages.error(request, '❌ Debe ingresar un email válido')
            return redirect('cotizaciones:enviar_email', pk=pk)
        
        # Verificar configuración de email antes de intentar enviar
        config_valida, errores_config = verificar_configuracion_email()
        if not config_valida:
            logger.error(f"Configuración de email inválida: {errores_config}")
            messages.error(
                request,
                '❌ La configuración de email del sistema no está completa. '
                'Contacte al administrador.'
            )
            return redirect('cotizaciones:enviar_email', pk=pk)
        
        try:
            # Construir URL base
            base_url = request.build_absolute_uri('/')[:-1]
            
            # Determinar email para copia
            email_copia = request.user.email if enviar_copia else None
            
            # Mostrar mensaje de "enviando..."
            logger.info(f"Iniciando envío de cotización {cotizacion.numero} a {email_destinatario}")
            
            # Enviar email con manejo robusto
            exito, mensaje, detalles = enviar_cotizacion_email_async(
                cotizacion=cotizacion,
                email_destinatario=email_destinatario,
                mensaje_adicional=mensaje_adicional,
                enviar_copia=enviar_copia,
                email_copia=email_copia,
                base_url=base_url
            )
            
            if exito:
                # Actualizar cotización
                cotizacion.estado = 'enviada'
                cotizacion.fecha_envio = timezone.now()
                cotizacion.email_enviado_a = email_destinatario
                cotizacion.save()
                
                # Mensaje de éxito
                mensaje_exito = f'✅ Cotización enviada exitosamente a {email_destinatario}'
                
                # Agregar info sobre copia si corresponde
                if enviar_copia and email_copia:
                    if detalles.get('email_copia', {}).get('exito', False):
                        mensaje_exito += f' (copia enviada a {email_copia})'
                    else:
                        mensaje_exito += f' (la copia a {email_copia} no pudo ser enviada)'
                
                messages.success(request, mensaje_exito)
                logger.info(f"✅ Cotización {cotizacion.numero} enviada exitosamente")
                
                return redirect('cotizaciones:detalle', pk=pk)
            else:
                # Error en el envío
                logger.error(f"❌ Error al enviar cotización {cotizacion.numero}: {mensaje}")
                
                # Mensajes de error más específicos según el problema
                if 'timeout' in mensaje.lower() or 'timed out' in mensaje.lower():
                    messages.error(
                        request,
                        '⏱️ El servidor de email no respondió a tiempo. '
                        'Por favor, intente nuevamente en unos momentos. '
                        'Si el problema persiste, contacte al administrador del sistema.'
                    )
                elif 'connection refused' in mensaje.lower():
                    messages.error(
                        request,
                        '🚫 No se pudo conectar con el servidor de email. '
                        'Verifique la configuración del sistema o contacte al administrador.'
                    )
                elif 'authentication' in mensaje.lower():
                    messages.error(
                        request,
                        '🔐 Error de autenticación con el servidor de email. '
                        'Contacte al administrador para verificar las credenciales.'
                    )
                else:
                    messages.error(
                        request,
                        f'❌ Error al enviar email: {mensaje}. '
                        'Por favor, intente nuevamente o contacte al administrador.'
                    )
                
                return redirect('cotizaciones:enviar_email', pk=pk)
                
        except EmailSendError as e:
            logger.error(f"EmailSendError al enviar cotización {cotizacion.numero}: {str(e)}")
            messages.error(
                request,
                f'❌ Error al enviar email: {str(e)}. '
                'Por favor, intente nuevamente en unos momentos.'
            )
            return redirect('cotizaciones:enviar_email', pk=pk)
            
        except Exception as e:
            logger.exception(f"Error inesperado al enviar cotización {cotizacion.numero}")
            messages.error(
                request,
                '❌ Ocurrió un error inesperado al enviar el email. '
                'Por favor, contacte al administrador del sistema.'
            )
            return redirect('cotizaciones:enviar_email', pk=pk)
    
    # GET: Mostrar formulario
    email_sugerido = ''
    if cotizacion.cliente and cotizacion.cliente.email:
        email_sugerido = cotizacion.cliente.email
    
    # Verificar configuración y mostrar advertencia si es necesaria
    config_valida, errores_config = verificar_configuracion_email()
    if not config_valida:
        for error in errores_config:
            messages.warning(request, f'⚠️ Problema de configuración: {error}')
    
    context = {
        'cotizacion': cotizacion,
        'email_sugerido': email_sugerido,
        'config_email_valida': config_valida,
    }
    return render(request, 'cotizaciones/emails/enviar_email.html', context)

def ver_cotizacion_publica(request, token):
    """Vista pública de cotización sin login"""
    cotizacion = get_object_or_404(Cotizacion, token_validacion=token)
    
    items_servicio = cotizacion.items_servicio.all().order_by('orden')
    items_material = cotizacion.items_material.all()
    items_mano_obra = cotizacion.items_mano_obra.all()
    
    context = {
        'cotizacion': cotizacion,
        'items_servicio': items_servicio,
        'items_material': items_material,
        'items_mano_obra': items_mano_obra,
        'config_empresa': ConfiguracionEmpresa.get_config(),
        'es_vista_publica': True,
    }
    
    return render(request, 'cotizaciones/emails/ver_publica.html', context)

def responder_cotizacion(request, token, accion):
    """Procesar respuesta del cliente (aprobar/rechazar/modificar)"""
    from django.core.mail import send_mail
    
    cotizacion = get_object_or_404(Cotizacion, token_validacion=token)
    
    # Verificar que puede responder
    if not cotizacion.puede_responder():
        return render(request, 'cotizaciones/respuesta_error.html', {
            'mensaje': 'Esta cotización ya fue respondida o no está disponible para respuestas.',
            'cotizacion': cotizacion
        })
    
    if request.method == 'POST':
        comentarios = request.POST.get('comentarios', '')
        
        # Actualizar cotización según la acción
        cotizacion.fecha_respuesta_cliente = timezone.now()
        cotizacion.comentarios_cliente = comentarios
        
        # Variables para notificaciones
        tipo_notificacion = 'info'
        titulo_notificacion = ''
        mensaje_notificacion = ''
        
        if accion == 'aprobar':
            cotizacion.estado = 'aprobada'
            mensaje_cliente = '✅ Su aprobación ha sido registrada exitosamente'
            mensaje_admin = f'✅ Cliente aprobó cotización {cotizacion.numero}'
            
            # Configurar notificación de aprobación
            tipo_notificacion = 'success'
            titulo_notificacion = '🎉 ¡Cotización Aprobada!'
            mensaje_notificacion = f'El cliente aprobó la cotización #{cotizacion.numero} por ${cotizacion.valor_total:,.0f}'
            
        elif accion == 'rechazar':
            cotizacion.estado = 'rechazada'
            cotizacion.motivo_rechazo = comentarios
            mensaje_cliente = '❌ Su rechazo ha sido registrado'
            mensaje_admin = f'❌ Cliente rechazó cotización {cotizacion.numero}'
            
            # Configurar notificación de rechazo
            tipo_notificacion = 'error'
            titulo_notificacion = '❌ Cotización Rechazada'
            mensaje_notificacion = f'El cliente rechazó la cotización #{cotizacion.numero}. Motivo: {comentarios[:100] if comentarios else "Sin motivo especificado"}'
            
        elif accion == 'modificar':
            cotizacion.estado = 'requiere_cambios'
            mensaje_cliente = '📝 Su solicitud de cambios ha sido registrada'
            mensaje_admin = f'📝 Cliente solicita cambios en cotización {cotizacion.numero}'
            
            # Configurar notificación de cambios
            tipo_notificacion = 'warning'
            titulo_notificacion = '📝 Cambios Solicitados'
            mensaje_notificacion = f'El cliente solicita cambios en la cotización #{cotizacion.numero}: {comentarios[:100] if comentarios else "Ver detalles"}'
        
        else:
            return redirect('cotizaciones:ver_publica', token=token)
        
        cotizacion.save()
        
        # ⭐ CREAR NOTIFICACIÓN AL CREADOR DE LA COTIZACIÓN
        try:
            crear_notificacion(
                usuario=cotizacion.creado_por,
                titulo=titulo_notificacion,
                mensaje=mensaje_notificacion,
                tipo=tipo_notificacion,
                url=f'/cotizaciones/{cotizacion.pk}/',
                datos_extra={
                    'cotizacion_id': cotizacion.id,
                    'cotizacion_numero': cotizacion.numero,
                    'cliente': cotizacion.get_nombre_cliente(),
                    'accion': accion,
                    'valor_total': float(cotizacion.valor_total),
                    'comentarios': comentarios[:500] if comentarios else '',
                }
            )
        except Exception as e:
            print(f"Error creando notificación: {str(e)}")
        
        # Notificar al admin por email
        try:
            subject = f'[COTIZACIÓN {cotizacion.numero}] Respuesta del Cliente'
            message = f"""
Respuesta recibida para la Cotización N° {cotizacion.numero}

Cliente: {cotizacion.get_nombre_cliente()}
Acción: {accion.upper()}
Estado actual: {cotizacion.get_estado_display()}

Comentarios del cliente:
{comentarios if comentarios else 'Sin comentarios'}

Ver cotización: {request.build_absolute_uri(f'/cotizaciones/{cotizacion.pk}/')}
            """
            
            # Enviar a todos los admins y gerentes
            admins_emails = User.objects.filter(
                perfilempleado__cargo__in=['admin', 'gerente'],
                perfilempleado__activo=True
            ).values_list('email', flat=True)
            
            if admins_emails:
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    list(admins_emails),
                    fail_silently=True,
                )
        except Exception as e:
            print(f"Error enviando notificación a admin: {str(e)}")
        
        return render(request, 'cotizaciones/emails/respuesta_exitosa.html', {
            'mensaje': mensaje_cliente,
            'cotizacion': cotizacion,
            'accion': accion
        })
    
    # GET: Mostrar formulario de confirmación
    context = {
        'cotizacion': cotizacion,
        'accion': accion,
        'config_empresa': ConfiguracionEmpresa.get_config(),
    }
    return render(request, 'cotizaciones/emails/confirmar_respuesta.html', context)

@login_required
@requiere_gerente_o_superior
def reenviar_cotizacion(request, pk):
    """Reenviar cotización después de hacer cambios"""
    cotizacion = get_object_or_404(Cotizacion, pk=pk)
    
    if cotizacion.estado == 'requiere_cambios':
        # Cambiar estado a borrador para permitir edición
        cotizacion.estado = 'borrador'
        cotizacion.save()
        messages.success(request, 'Cotización convertida a borrador para edición')
        return redirect('cotizaciones:editar', pk=pk)
    else:
        messages.error(request, 'Esta cotización no requiere cambios')
        return redirect('cotizaciones:detalle', pk=pk)

def solicitar_feedback_automatico():
    """
    Función para ejecutar periódicamente (cada día) que solicita feedback
    a los clientes 7 días después de finalizar una cotización.
    
    EJECUTAR CON:
    - Django management command
    - Celery task
    - Cron job
    """
    from django.core.mail import send_mail
    from django.conf import settings
    
    # Obtener cotizaciones finalizadas hace 7 días que no han recibido feedback
    hace_7_dias = timezone.now().date() - timedelta(days=7)
    
    cotizaciones = Cotizacion.objects.filter(
        estado='finalizada',
        feedback_solicitado=False,
        fecha_finalizacion__date=hace_7_dias,
        email_enviado_a__isnull=False
    )
    
    resultados = {
        'enviados': 0,
        'fallidos': 0,
        'errores': []
    }
    
    for cotizacion in cotizaciones:
        resultado = cotizacion.solicitar_feedback_cliente()
        
        if resultado['success']:
            resultados['enviados'] += 1
            print(f"✅ Feedback solicitado: {cotizacion.numero}")
        else:
            resultados['fallidos'] += 1
            resultados['errores'].append({
                'cotizacion': cotizacion.numero,
                'error': resultado['error']
            })
            print(f"❌ Error en {cotizacion.numero}: {resultado['error']}")
    
    return resultados

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

# === NUEVAS FUNCIONES PARA REPORTES INTERACTIVOS ===

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

# === PRESTAMOS ===

@login_required
@requiere_gerente_o_superior
def lista_prestamos(request):
    """Lista todos los préstamos activos"""
    
    buscar = request.GET.get('buscar', '').strip()
    
    prestamos = PrestamoMaterial.objects.select_related(
        'material', 'usuario_registro'
    ).all()
    
    if buscar:
        prestamos = prestamos.filter(
            Q(material__codigo__icontains=buscar) |
            Q(material__nombre__icontains=buscar) |
            Q(prestado_a__icontains=buscar)
        )
    
    # Contar estados
    total = prestamos.count()
    vencidos = sum(1 for p in prestamos if p.esta_vencido())
    proximos = sum(1 for p in prestamos if not p.esta_vencido() and p.dias_restantes() <= 3)
    
    # Materiales disponibles = materiales activos
    materiales_disponibles_count = Material.objects.filter(activo=True).count()
    
    # Materiales para el formulario = solo activos
    materiales_disponibles_form = Material.objects.filter(
        activo=True
    ).order_by('codigo')
    
    context = {
        'prestamos': prestamos,
        'total': total,
        'vencidos': vencidos,
        'proximos': proximos,
        'materiales_disponibles': materiales_disponibles_count,
        'materiales_disponibles_form': materiales_disponibles_form,
        'buscar': buscar,
    }
    
    return render(request, 'cotizaciones/prestamos/lista_prestamos.html', context)

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def crear_prestamo(request):
    """Crear préstamo vía AJAX"""
    
    try:
        data = json.loads(request.body)
        
        material = Material.objects.get(pk=data['material_id'])
        
        # Validar que esté activo (disponible)
        if not material.activo:
            return JsonResponse({
                'success': False,
                'error': f'El material {material.codigo} no está disponible (inactivo o prestado)'
            })
        
        # Crear préstamo (automáticamente marca material como inactivo)
        prestamo = PrestamoMaterial.objects.create(
            material=material,
            prestado_a=data['prestado_a'],
            fecha_devolucion=data['fecha_devolucion'],
            observaciones=data.get('observaciones', ''),
            usuario_registro=request.user
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Préstamo creado: {material.codigo} - {data["prestado_a"]}'
        })
        
    except Material.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Material no encontrado'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
def obtener_datos_prestamo(request, pk):
    """Obtener datos de un préstamo para edición"""
    
    prestamo = get_object_or_404(PrestamoMaterial, pk=pk)
    
    return JsonResponse({
        'success': True,
        'prestamo': {
            'id': prestamo.id,
            'material_id': prestamo.material.id,
            'material_codigo': prestamo.material.codigo,
            'material_nombre': prestamo.material.nombre,
            'prestado_a': prestamo.prestado_a,
            'fecha_devolucion': prestamo.fecha_devolucion.strftime('%Y-%m-%d'),
            'observaciones': prestamo.observaciones or ''
        }
    })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["PUT"])
def editar_prestamo(request, pk):
    """Editar préstamo vía AJAX"""
    
    try:
        prestamo = get_object_or_404(PrestamoMaterial, pk=pk)
        data = json.loads(request.body)
        
        # Actualizar datos (NO se puede cambiar el material)
        prestamo.prestado_a = data['prestado_a']
        prestamo.fecha_devolucion = data['fecha_devolucion']
        prestamo.observaciones = data.get('observaciones', '')
        prestamo.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Préstamo actualizado correctamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["DELETE"])
def eliminar_prestamo(request, pk):
    """Eliminar/Devolver préstamo vía AJAX"""
    
    try:
        from django.utils import timezone
        from .models import HistorialPrestamo
        
        prestamo = get_object_or_404(PrestamoMaterial, pk=pk)
        material_codigo = prestamo.material.codigo
        
        # Guardar en historial ANTES de eliminar
        HistorialPrestamo.objects.create(
            material_codigo=prestamo.material.codigo,
            material_nombre=prestamo.material.nombre,
            prestado_a=prestamo.prestado_a,
            fecha_prestamo=prestamo.fecha_prestamo,
            fecha_devolucion=prestamo.fecha_devolucion,
            fecha_devuelto=timezone.now().date(),
            observaciones=prestamo.observaciones,
            usuario_registro=prestamo.usuario_registro
        )
        
        # Marcar material como activo
        material = prestamo.material
        material.activo = True
        material.save()
        
        # Eliminar préstamo
        prestamo.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Material devuelto: {material_codigo}'
        })
        
    except PrestamoMaterial.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Préstamo no encontrado'
        }, status=404)
    except Exception as e:
        import traceback
        print(f"ERROR en eliminar_prestamo: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def verificar_material_disponible(request):
    """Verifica si un material está disponible (activo)"""
    
    material_id = request.GET.get('material_id')
    
    if not material_id:
        return JsonResponse({'disponible': True})
    
    try:
        material = Material.objects.get(pk=material_id)
        
        if not material.activo:
            # Si no está activo, verificar si es por préstamo
            if hasattr(material, 'prestamo_actual'):
                prestamo = material.prestamo_actual
                return JsonResponse({
                    'disponible': False,
                    'mensaje': f'Material en préstamo hasta el {prestamo.fecha_devolucion.strftime("%d/%m/%Y")}',
                    'prestado_a': prestamo.prestado_a
                })
            else:
                return JsonResponse({
                    'disponible': False,
                    'mensaje': 'Material no disponible (inactivo)'
                })
        
        return JsonResponse({
            'disponible': True,
            'mensaje': 'Material disponible'
        })
    
    except Material.DoesNotExist:
        return JsonResponse({'disponible': False, 'mensaje': 'Material no encontrado'})

@login_required
@requiere_gerente_o_superior
def obtener_historial(request):
    """Obtiene el historial de préstamos"""
    
    try:
        from .models import HistorialPrestamo
        
        historial = HistorialPrestamo.objects.all().order_by('-fecha_devuelto')
        
        data = []
        for item in historial:
            data.append({
                'id': item.id,
                'material_codigo': item.material_codigo,
                'material_nombre': item.material_nombre,
                'prestado_a': item.prestado_a,
                'fecha_prestamo': item.fecha_prestamo.isoformat(),
                'fecha_devolucion': item.fecha_devolucion.isoformat(),
                'fecha_devuelto': item.fecha_devuelto.isoformat() if item.fecha_devuelto else None,
                'duracion_dias': item.duracion_dias(),
                'observaciones': item.observaciones or ''
            })
        
        return JsonResponse({
            'success': True,
            'historial': data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })







    """Obtiene el historial de préstamos"""
    
    try:
        from .models import HistorialPrestamo
        
        historial = HistorialPrestamo.objects.all().order_by('-fecha_devuelto')
        
        data = []
        for item in historial:
            data.append({
                'id': item.id,
                'material_codigo': item.material_codigo,
                'material_nombre': item.material_nombre,
                'prestado_a': item.prestado_a,
                'fecha_prestamo': item.fecha_prestamo.isoformat(),
                'fecha_devolucion': item.fecha_devolucion.isoformat(),
                'fecha_devuelto': item.fecha_devuelto.isoformat() if item.fecha_devuelto else None,
                'duracion_dias': item.duracion_dias(),
                'observaciones': item.observaciones or ''
            })
        
        return JsonResponse({
            'success': True,
            'historial': data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


