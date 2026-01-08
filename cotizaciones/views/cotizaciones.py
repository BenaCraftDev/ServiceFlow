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

