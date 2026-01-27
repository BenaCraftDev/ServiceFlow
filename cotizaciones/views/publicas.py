import json
import csv
import logging # <--- FALTABA ESTO
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
from django.contrib.auth.models import User # <--- FALTABA ESTO
from ..models import *
from ..forms import *
from ..forms_empleados import *
from ..forms_prestamos import *
from home.decorators import requiere_admin, requiere_gerente_o_superior
from notificaciones.models import Notificacion
from notificaciones.utils import crear_notificacion
from home.models import PerfilEmpleado
from ..utils_mantenimiento import verificar_mantenimientos_materiales
from .comunicaciones import enviar_email_con_reintentos 

# Configurar Logger
logger = logging.getLogger(__name__) # <--- FALTABA ESTO

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
    
    cotizacion = get_object_or_404(Cotizacion, token_validacion=token)
    
    # Verificar que puede responder
    if not cotizacion.puede_responder():
        return render(request, 'cotizaciones/emails/respuesta_error.html', {
            'mensaje': 'Esta cotización ya fue respondida o no está disponible para respuestas.',
            'cotizacion': cotizacion,
            'config_empresa': ConfiguracionEmpresa.get_config(),
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
            # mensaje_admin = f'✅ Cliente aprobó cotización {cotizacion.numero}' # No se usa variable localmente
            
            # Configurar notificación de aprobación
            tipo_notificacion = 'success'
            titulo_notificacion = '🎉 ¡Cotización Aprobada!'
            mensaje_notificacion = f'El cliente aprobó la cotización #{cotizacion.numero} por ${cotizacion.valor_total:,.0f}'
            
        elif accion == 'rechazar':
            cotizacion.estado = 'rechazada'
            cotizacion.motivo_rechazo = comentarios
            mensaje_cliente = '❌ Su rechazo ha sido registrado'
            # mensaje_admin = f'❌ Cliente rechazó cotización {cotizacion.numero}'
            
            # Configurar notificación de rechazo
            tipo_notificacion = 'error'
            titulo_notificacion = '❌ Cotización Rechazada'
            mensaje_notificacion = f'El cliente rechazó la cotización #{cotizacion.numero}. Motivo: {comentarios[:100] if comentarios else "Sin motivo especificado"}'
            
        elif accion == 'modificar':
            cotizacion.estado = 'requiere_cambios'
            mensaje_cliente = '📝 Su solicitud de cambios ha sido registrada'
            # mensaje_admin = f'📝 Cliente solicita cambios en cotización {cotizacion.numero}'
            
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
            logger.error(f"Error creando notificación: {str(e)}")
        
        # Notificar al admin por email usando Resend
        try:
            config_empresa = ConfiguracionEmpresa.get_config()
            subject = f'[COTIZACIÓN {cotizacion.numero}] Respuesta del Cliente'
            
            # HTML para el email de notificación
            html_message = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
            </head>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <div style="background: linear-gradient(135deg, #1f5fa5, #2575c0); color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                        <h2 style="margin: 0;">Respuesta del Cliente</h2>
                    </div>
                    
                    <div style="background: white; padding: 20px; border: 1px solid #ddd; border-top: none;">
                        <h3 style="color: #1f5fa5;">Cotización N° {cotizacion.numero}</h3>
                        
                        <table style="width: 100%; margin: 20px 0;">
                            <tr>
                                <td style="padding: 8px; font-weight: bold;">Cliente:</td>
                                <td style="padding: 8px;">{cotizacion.get_nombre_cliente()}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px; font-weight: bold;">Acción:</td>
                                <td style="padding: 8px; text-transform: uppercase;">{accion}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px; font-weight: bold;">Estado Actual:</td>
                                <td style="padding: 8px;">{cotizacion.get_estado_display()}</td>
                            </tr>
                        </table>
                        
                        {f'<div style="background: #f0f8ff; padding: 15px; border-left: 4px solid #2575c0; margin: 20px 0;"><strong>Comentarios del cliente:</strong><br>{comentarios}</div>' if comentarios else ''}
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{request.build_absolute_uri(f'/cotizaciones/{cotizacion.pk}/')}" 
                               style="display: inline-block; padding: 12px 24px; background: #2575c0; color: white; text-decoration: none; border-radius: 5px; font-weight: bold;">
                                Ver Cotización Completa
                            </a>
                        </div>
                    </div>
                    
                    <div style="text-align: center; padding: 20px; color: #666; font-size: 12px;">
                        <p>Este correo fue enviado automáticamente por {config_empresa.nombre}</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Obtener emails de admins y gerentes
            admins_emails = list(User.objects.filter(
                perfilempleado__cargo__in=['admin', 'gerente'],
                perfilempleado__activo=True,
                email__isnull=False
            ).exclude(email='').values_list('email', flat=True))
            
            if admins_emails:
                exito, mensaje = enviar_email_con_reintentos(
                    subject=subject,
                    html_content=html_message,
                    recipient_list=admins_emails,
                    max_intentos=2,
                    timeout_segundos=15,
                    fail_silently=True
                )
                
                if not exito:
                    logger.warning(f"No se pudo enviar email a admins: {mensaje}")
        
        except Exception as e:
            logger.error(f"Error enviando notificación por email a admin: {str(e)}")
        
        return render(request, 'cotizaciones/emails/respuesta_exitosa.html', {
            'mensaje': mensaje_cliente,
            'cotizacion': cotizacion,
            'accion': accion,
            'config_empresa': ConfiguracionEmpresa.get_config(),
        })
    
    # GET: Mostrar formulario de confirmación
    context = {
        'cotizacion': cotizacion,
        'accion': accion,
        'config_empresa': ConfiguracionEmpresa.get_config(),
    }
    return render(request, 'cotizaciones/emails/confirmar_respuesta.html', context)