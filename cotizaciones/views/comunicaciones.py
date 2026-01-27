import os
from ..forms_empleados import *
from ..forms_prestamos import *
from ..models import *
from ..forms import *
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
from ..utils_mantenimiento import verificar_mantenimientos_materiales
import socket
import logging
from time import sleep
from smtplib import SMTPException
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.urls import reverse
from django.template.loader import render_to_string  # Importamos la función que SÍ funciona
from django.contrib.auth.forms import SetPasswordForm
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode

logger = logging.getLogger(__name__)

class EmailSendError(Exception):
    """Excepción personalizada para errores de envío de email"""
    pass

def verificar_configuracion_email():
    """Verifica que la configuración de email esté correcta"""
    errores = []
    
    if not hasattr(settings, 'EMAIL_HOST') or not settings.EMAIL_HOST:
        errores.append("EMAIL_HOST no está configurado")
    
    if not hasattr(settings, 'EMAIL_PORT') or not settings.EMAIL_PORT:
        errores.append("EMAIL_PORT no está configurado")
    
    if not hasattr(settings, 'DEFAULT_FROM_EMAIL') or not settings.DEFAULT_FROM_EMAIL:
        errores.append("DEFAULT_FROM_EMAIL no está configurado")
    
    if hasattr(settings, 'EMAIL_BACKEND'):
        if 'console' in settings.EMAIL_BACKEND.lower():
            errores.append("EMAIL_BACKEND está en modo console (solo para desarrollo)")
    
    return len(errores) == 0, errores

def enviar_email_con_reintentos(
    subject,
    html_content,
    recipient_list,
    from_email=None,
    max_intentos=3,
    timeout_segundos=30,
    fail_silently=False
):
    """Envía email usando Resend API"""
    import resend
    from django.conf import settings
    
    # Obtener API key
    api_key = os.environ.get('RESEND_API_KEY')
    if not api_key:
        error_msg = "RESEND_API_KEY no está configurada"
        logger.error(error_msg)
        if not fail_silently:
            raise EmailSendError(error_msg)
        return False, error_msg
    
    resend.api_key = api_key
    
    # Email de origen
    if from_email is None:
        from_email = os.environ.get('RESEND_FROM_EMAIL', 'onboarding@resend.dev')
    
    # Reintentos
    for intento in range(1, max_intentos + 1):
        try:
            logger.info(f"📧 Intento {intento}/{max_intentos} de enviar email vía Resend API")
            
            params = {
                "from": from_email,
                "to": recipient_list,
                "subject": subject,
                "html": html_content,
            }
            
            email = resend.Emails.send(params)
            
            logger.info(f"✅ Email enviado exitosamente - ID: {email['id']}")
            return True, "Email enviado exitosamente"
            
        except Exception as e:
            error_msg = f"Error Resend: {str(e)}"
            logger.error(f"❌ {error_msg} (intento {intento}/{max_intentos})")
            
            if intento < max_intentos:
                sleep(2 ** intento)
                continue
            else:
                if not fail_silently:
                    raise EmailSendError(str(e))
                return False, str(e)
    
    return False, "No se pudo enviar el email después de múltiples intentos"

@login_required
@requiere_gerente_o_superior
def enviar_cotizacion_email(request, pk):
    """Vista mejorada para enviar cotización por email con manejo robusto de errores"""
    cotizacion = get_object_or_404(Cotizacion, pk=pk)
    
    # Validar que tenga items
    tiene_items = (
        cotizacion.items_servicio.exists() or 
        cotizacion.items_material.exists() or 
        cotizacion.items_mano_obra.exists()
    )
    
    if not tiene_items:
        messages.error(request, 'La cotización debe tener al menos un item antes de enviarla')
        return redirect('cotizaciones:editar', pk=pk)
    
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
            # Generar token único para esta cotización
            if not cotizacion.token_validacion:
                cotizacion.generar_token()
            
            # Construir URL base
            base_url = request.build_absolute_uri('/')[:-1]
            
            # Generar URLs de respuesta
            url_aprobar = f"{base_url}/cotizaciones/responder/{cotizacion.token_validacion}/aprobar/"
            url_rechazar = f"{base_url}/cotizaciones/responder/{cotizacion.token_validacion}/rechazar/"
            url_modificar = f"{base_url}/cotizaciones/responder/{cotizacion.token_validacion}/modificar/"
            url_ver = f"{base_url}/cotizaciones/ver-publica/{cotizacion.token_validacion}/"
            
            # Contexto para el template del cliente
            context_cliente = {
                'cotizacion': cotizacion,
                'mensaje_adicional': mensaje_adicional,
                'url_aprobar': url_aprobar,
                'url_rechazar': url_rechazar,
                'url_modificar': url_modificar,
                'url_ver': url_ver,
                'config_empresa': ConfiguracionEmpresa.get_config(),
                'es_copia_remitente': False,
            }
            
            # Renderizar HTML
            html_content = render_to_string(
                'cotizaciones/emails/cotizacion_cliente.html',
                context_cliente
            )
            
            subject = f'Cotización N° {cotizacion.numero} - {ConfiguracionEmpresa.get_config().nombre}'
            
            logger.info(f"Iniciando envío de cotización {cotizacion.numero} a {email_destinatario}")
            
            # Enviar email principal con reintentos
            exito_principal, mensaje_principal = enviar_email_con_reintentos(
                subject=subject,
                html_content=html_content,
                recipient_list=[email_destinatario],
                max_intentos=3,
                timeout_segundos=20,
                fail_silently=False
            )
            
            if exito_principal:
                # Enviar copia si está activado
                if enviar_copia and request.user.email:
                    context_copia = context_cliente.copy()
                    context_copia['es_copia_remitente'] = True
                    context_copia['email_destinatario'] = email_destinatario
                    
                    html_content_copia = render_to_string(
                        'cotizaciones/emails/cotizacion_cliente.html',
                        context_copia
                    )
                    
                    exito_copia, mensaje_copia = enviar_email_con_reintentos(
                        subject=f'[COPIA] {subject}',
                        html_content=html_content_copia,
                        recipient_list=[request.user.email],
                        max_intentos=2,
                        timeout_segundos=15,
                        fail_silently=True  # No fallar si falla la copia
                    )
                
                # Actualizar cotización
                cotizacion.estado = 'enviada'
                cotizacion.fecha_envio = timezone.now()
                cotizacion.email_enviado_a = email_destinatario
                cotizacion.save()
                
                # Mensaje de éxito
                mensaje_exito = f'✅ Cotización enviada exitosamente a {email_destinatario}'
                
                if enviar_copia and request.user.email:
                    if exito_copia:
                        mensaje_exito += f' (copia enviada a {request.user.email})'
                    else:
                        mensaje_exito += f' (la copia a {request.user.email} no pudo ser enviada)'
                
                messages.success(request, mensaje_exito)
                logger.info(f"✅ Cotización {cotizacion.numero} enviada exitosamente")
                
                return redirect('cotizaciones:detalle', pk=pk)
            else:
                # Error en el envío
                logger.error(f"❌ Error al enviar cotización {cotizacion.numero}: {mensaje_principal}")
                
                # Mensajes de error más específicos
                if 'timeout' in mensaje_principal.lower() or 'timed out' in mensaje_principal.lower():
                    messages.error(
                        request,
                        '⏱️ El servidor de email no respondió a tiempo. '
                        'Por favor, intente nuevamente en unos momentos. '
                        'Si el problema persiste, contacte al administrador del sistema.'
                    )
                elif 'connection refused' in mensaje_principal.lower():
                    messages.error(
                        request,
                        '🚫 No se pudo conectar con el servidor de email. '
                        'Verifique la configuración del sistema o contacte al administrador.'
                    )
                elif 'authentication' in mensaje_principal.lower():
                    messages.error(
                        request,
                        '🔐 Error de autenticación con el servidor de email. '
                        'Contacte al administrador para verificar las credenciales.'
                    )
                else:
                    messages.error(
                        request,
                        f'❌ Error al enviar email: {mensaje_principal}. '
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

    """Vista mejorada para enviar cotización por email con manejo robusto de errores"""
    cotizacion = get_object_or_404(Cotizacion, pk=pk)
    
    # Validar que tenga items
    tiene_items = (
        cotizacion.items_servicio.exists() or 
        cotizacion.items_material.exists() or 
        cotizacion.items_mano_obra.exists()
    )
    
    if not tiene_items:
        messages.error(request, 'La cotización debe tener al menos un item antes de enviarla')
        return redirect('cotizaciones:editar', pk=pk)
    
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
            # Generar token único para esta cotización
            if not cotizacion.token_validacion:
                cotizacion.generar_token()
            
            # Construir URL base
            base_url = request.build_absolute_uri('/')[:-1]
            
            # Generar URLs de respuesta
            url_aprobar = f"{base_url}/cotizaciones/responder/{cotizacion.token_validacion}/aprobar/"
            url_rechazar = f"{base_url}/cotizaciones/responder/{cotizacion.token_validacion}/rechazar/"
            url_modificar = f"{base_url}/cotizaciones/responder/{cotizacion.token_validacion}/modificar/"
            url_ver = f"{base_url}/cotizaciones/ver-publica/{cotizacion.token_validacion}/"
            
            # Contexto para el template del cliente
            context_cliente = {
                'cotizacion': cotizacion,
                'mensaje_adicional': mensaje_adicional,
                'url_aprobar': url_aprobar,
                'url_rechazar': url_rechazar,
                'url_modificar': url_modificar,
                'url_ver': url_ver,
                'config_empresa': ConfiguracionEmpresa.get_config(),
                'es_copia_remitente': False,
            }
            
            # Renderizar HTML
            html_content = render_to_string(
                'cotizaciones/emails/cotizacion_cliente.html',
                context_cliente
            )
            
            subject = f'Cotización N° {cotizacion.numero} - {ConfiguracionEmpresa.get_config().nombre}'
            
            logger.info(f"Iniciando envío de cotización {cotizacion.numero} a {email_destinatario}")
            
            # Enviar email principal con reintentos
            exito_principal, mensaje_principal = enviar_email_con_reintentos(
                subject=subject,
                html_content=html_content,
                recipient_list=[email_destinatario],
                max_intentos=3,
                timeout_segundos=20,
                fail_silently=False
            )
            
            if exito_principal:
                # Enviar copia si está activado
                if enviar_copia and request.user.email:
                    context_copia = context_cliente.copy()
                    context_copia['es_copia_remitente'] = True
                    context_copia['email_destinatario'] = email_destinatario
                    
                    html_content_copia = render_to_string(
                        'cotizaciones/emails/cotizacion_cliente.html',
                        context_copia
                    )
                    
                    exito_copia, mensaje_copia = enviar_email_con_reintentos(
                        subject=f'[COPIA] {subject}',
                        html_content=html_content_copia,
                        recipient_list=[request.user.email],
                        max_intentos=2,
                        timeout_segundos=15,
                        fail_silently=True  # No fallar si falla la copia
                    )
                
                # Actualizar cotización
                cotizacion.estado = 'enviada'
                cotizacion.fecha_envio = timezone.now()
                cotizacion.email_enviado_a = email_destinatario
                cotizacion.save()
                
                # Mensaje de éxito
                mensaje_exito = f'✅ Cotización enviada exitosamente a {email_destinatario}'
                
                if enviar_copia and request.user.email:
                    if exito_copia:
                        mensaje_exito += f' (copia enviada a {request.user.email})'
                    else:
                        mensaje_exito += f' (la copia a {request.user.email} no pudo ser enviada)'
                
                messages.success(request, mensaje_exito)
                logger.info(f"✅ Cotización {cotizacion.numero} enviada exitosamente")
                
                return redirect('cotizaciones:detalle', pk=pk)
            else:
                # Error en el envío
                logger.error(f"❌ Error al enviar cotización {cotizacion.numero}: {mensaje_principal}")
                
                # Mensajes de error más específicos
                if 'timeout' in mensaje_principal.lower() or 'timed out' in mensaje_principal.lower():
                    messages.error(
                        request,
                        '⏱️ El servidor de email no respondió a tiempo. '
                        'Por favor, intente nuevamente en unos momentos. '
                        'Si el problema persiste, contacte al administrador del sistema.'
                    )
                elif 'connection refused' in mensaje_principal.lower():
                    messages.error(
                        request,
                        '🚫 No se pudo conectar con el servidor de email. '
                        'Verifique la configuración del sistema o contacte al administrador.'
                    )
                elif 'authentication' in mensaje_principal.lower():
                    messages.error(
                        request,
                        '🔐 Error de autenticación con el servidor de email. '
                        'Contacte al administrador para verificar las credenciales.'
                    )
                else:
                    messages.error(
                        request,
                        f'❌ Error al enviar email: {mensaje_principal}. '
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
    cotizacion = get_object_or_404(Cotizacion, pk=pk)
    
    # Validar que tenga items
    tiene_items = (
        cotizacion.items_servicio.exists() or 
        cotizacion.items_material.exists() or 
        cotizacion.items_mano_obra.exists()
    )
    
    if not tiene_items:
        messages.error(request, 'La cotización debe tener al menos un item antes de enviarla')
        return redirect('cotizaciones:editar', pk=pk)
    
    if request.method == 'POST':
        email_destinatario = request.POST.get('email', '').strip()
        mensaje_adicional = request.POST.get('mensaje_adicional', '').strip()
        enviar_copia = request.POST.get('enviar_copia') == 'on'
        
        if not email_destinatario:
            messages.error(request, '❌ Debe ingresar un email válido')
            return redirect('cotizaciones:enviar_email', pk=pk)
        
        try:
            # Generar token si no existe
            if not cotizacion.token_validacion:
                cotizacion.generar_token()
            
            base_url = request.build_absolute_uri('/')[:-1]
            
            # Contexto para el template
            context = {
                'cotizacion': cotizacion,
                'mensaje_adicional': mensaje_adicional,
                'url_ver': f"{base_url}/cotizaciones/ver-publica/{cotizacion.token_validacion}/",
                'config_empresa': ConfiguracionEmpresa.get_config(),
            }
            
            # Renderizar HTML (Asegúrate que la ruta coincida con tu carpeta templates)
            html_content = render_to_string('cotizaciones/emails/cotizacion_cliente.html', context)
            subject = f'Cotización N° {cotizacion.numero} - {context["config_empresa"].nombre}'
            
            # Configurar el correo con EmailMultiAlternatives para evitar errores de formato
            email = EmailMultiAlternatives(
                subject=subject,
                body=f"Cotización N° {cotizacion.numero}. Puede verla en: {context['url_ver']}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email_destinatario],
            )
            email.attach_alternative(html_content, "text/html")
            
            # Enviar usando la configuración de settings.py (Resend)
            email.send(fail_silently=False)
            
            # Si se solicita copia al remitente
            if enviar_copia and request.user.email:
                email_copia = EmailMultiAlternatives(
                    subject=f"[COPIA] {subject}",
                    body=f"Copia de envío a {email_destinatario}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[request.user.email],
                )
                email_copia.attach_alternative(html_content, "text/html")
                email_copia.send(fail_silently=True)

            # Actualizar estado de la cotización
            cotizacion.estado = 'enviada'
            cotizacion.fecha_envio = timezone.now()
            cotizacion.email_enviado_a = email_destinatario
            cotizacion.save()
            
            messages.success(request, f'✅ Cotización enviada exitosamente a {email_destinatario}')
            return redirect('cotizaciones:detalle', pk=pk)
            
        except Exception as e:
            # Imprime el error exacto en la consola/logs de Railway
            print(f"DEBUG EMAIL ERROR: {str(e)}")
            messages.error(request, f'❌ Error al enviar el email: {str(e)}')
            return redirect('cotizaciones:enviar_email', pk=pk)

    # GET: Mostrar formulario
    email_sugerido = cotizacion.cliente.email if cotizacion.cliente and cotizacion.cliente.email else ''
    
    return render(request, 'cotizaciones/emails/enviar_email.html', {
        'cotizacion': cotizacion,
        'email_sugerido': email_sugerido,
    })

def recuperar_password(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        user = User.objects.filter(email=email).first()
        
        if user:
            try:
                # 1. Generar Tokens
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                base_url = request.build_absolute_uri('/')[:-1]
                url_reset = f"{base_url}{reverse('home:reset_password', kwargs={'uidb64': uid, 'token': token})}"
                
                # 2. Renderizar HTML Profesional
                subject = f"Recuperación de Clave - {user.username}"
                context = {
                    'user': user,  # Pasamos el usuario para que salga el nombre
                    'url_reset': url_reset
                }
                
                html_content = render_to_string('home/reset_password_email.html', context)

                # 3. Enviar con tu función robusta
                exito, mensaje = enviar_email_con_reintentos(
                    subject=subject,
                    html_content=html_content,
                    recipient_list=[email],
                    max_intentos=3,
                    fail_silently=False
                )

                if exito:
                    # FEEDBACK CLARO: No redirigimos al login directo, mostramos éxito aquí mismo o login con mensaje
                    messages.success(request, f'✅ ¡Listo! Hemos enviado las instrucciones a {email}. Revisa tu bandeja de entrada.')
                    return redirect('home:login') # Al login para que espere el correo
                else:
                    messages.error(request, f'Error al enviar: {mensaje}')

            except Exception as e:
                print(f"ERROR: {e}")
                messages.error(request, 'Error técnico al procesar la solicitud.')
        else:
            # Seguridad: Mensaje genérico aunque no exista
            messages.success(request, 'Si el correo está registrado, recibirás instrucciones en breve.')
            return redirect('home:login')

    return render(request, 'home/recuperar_password.html')

def reset_password(request, uidb64, token):
    """Vista que guarda la nueva contraseña"""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            # SetPasswordForm maneja la validación de contraseñas de Django
            form = SetPasswordForm(user, request.POST)
            
            if form.is_valid():
                form.save()
                # Usamos palabras clave "Éxito" y "actualizada" para que el filtro del login las deje pasar
                messages.success(request, '✅ Éxito: Tu contraseña ha sido actualizada. Inicia sesión ahora.')
                return redirect('home:login')
            else:
                # AQUÍ ESTABA EL ERROR: Antes tenías 'pass', por eso no salía nada.
                # Ahora iteramos los errores y los mostramos.
                for field, errors in form.errors.items():
                    for error in errors:
                        # Filtramos mensajes técnicos feos si es necesario, 
                        # pero Django suele dar mensajes claros aquí.
                        messages.error(request, f"⚠️ {error}")
        else:
            form = SetPasswordForm(user)
        
        return render(request, 'home/reset_password.html', {
            'form': form,
            'validlink': True 
        })
    else:
        messages.error(request, '❌ El enlace ya expiró o es inválido. Solicita uno nuevo.')
        return redirect('home:recuperar_password')