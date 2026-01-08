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

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
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
                            horas_estimadas=horas_por_empleado,
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
