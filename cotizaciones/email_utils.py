from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import logging
import socket
from smtplib import SMTPException
from time import sleep

logger = logging.getLogger(__name__)

class EmailSendError(Exception):
    """Excepción personalizada para errores de envío de email"""
    pass


def enviar_email_con_reintentos(
    subject,
    html_content,
    recipient_list,
    from_email=None,
    max_intentos=3,
    timeout_segundos=30,
    fail_silently=False
):
    """
    Envía un email con manejo de timeouts y reintentos
    
    Args:
        subject: Asunto del email
        html_content: Contenido HTML del email
        recipient_list: Lista de destinatarios
        from_email: Email del remitente (opcional, usa DEFAULT_FROM_EMAIL)
        max_intentos: Número máximo de intentos (default: 3)
        timeout_segundos: Timeout en segundos por intento (default: 30)
        fail_silently: Si True, no lanza excepción en caso de error
        
    Returns:
        tuple: (éxito: bool, mensaje: str)
    """
    
    if from_email is None:
        from_email = settings.DEFAULT_FROM_EMAIL
    
    # Configurar timeout para sockets
    socket.setdefaulttimeout(timeout_segundos)
    
    text_content = strip_tags(html_content)
    
    for intento in range(1, max_intentos + 1):
        try:
            logger.info(f"Intento {intento}/{max_intentos} de enviar email a {recipient_list}")
            
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=from_email,
                to=recipient_list
            )
            email.attach_alternative(html_content, "text/html")
            
            # Enviar con timeout
            email.send(fail_silently=False)
            
            logger.info(f"✅ Email enviado exitosamente a {recipient_list}")
            return True, f"Email enviado exitosamente"
            
        except socket.timeout:
            error_msg = f"⏱️ Timeout al conectar con servidor SMTP (intento {intento}/{max_intentos})"
            logger.warning(error_msg)
            
            if intento < max_intentos:
                sleep(2 ** intento)  # Backoff exponencial: 2s, 4s, 8s
                continue
            else:
                logger.error(f"❌ Timeout definitivo después de {max_intentos} intentos")
                if not fail_silently:
                    raise EmailSendError("No se pudo conectar con el servidor de email. Por favor, intente más tarde.")
                return False, "Timeout al enviar email"
                
        except SMTPException as e:
            error_msg = f"Error SMTP: {str(e)}"
            logger.error(f"❌ {error_msg} (intento {intento}/{max_intentos})")
            
            if intento < max_intentos:
                sleep(2 ** intento)
                continue
            else:
                if not fail_silently:
                    raise EmailSendError(f"Error al enviar email: {str(e)}")
                return False, str(e)
                
        except Exception as e:
            error_msg = f"Error inesperado: {str(e)}"
            logger.error(f"❌ {error_msg}")
            
            if not fail_silently:
                raise EmailSendError(f"Error al enviar email: {str(e)}")
            return False, str(e)
    
    # Si llegamos aquí, todos los intentos fallaron
    return False, "No se pudo enviar el email después de múltiples intentos"


def enviar_cotizacion_email_async(
    cotizacion,
    email_destinatario,
    mensaje_adicional='',
    enviar_copia=False,
    email_copia=None,
    base_url=''
):
    """
    Envía email de cotización de forma más robusta
    
    Args:
        cotizacion: Instancia de Cotizacion
        email_destinatario: Email del cliente
        mensaje_adicional: Mensaje personalizado
        enviar_copia: Si se debe enviar copia
        email_copia: Email para la copia
        base_url: URL base para generar enlaces
        
    Returns:
        tuple: (éxito: bool, mensaje: str, detalles: dict)
    """
    from cotizaciones.models import ConfiguracionEmpresa
    
    try:
        # Generar token si no existe
        if not cotizacion.token_validacion:
            cotizacion.generar_token()
        
        # Generar URLs
        url_aprobar = f"{base_url}/cotizaciones/responder/{cotizacion.token_validacion}/aprobar/"
        url_rechazar = f"{base_url}/cotizaciones/responder/{cotizacion.token_validacion}/rechazar/"
        url_modificar = f"{base_url}/cotizaciones/responder/{cotizacion.token_validacion}/modificar/"
        url_ver = f"{base_url}/cotizaciones/ver-publica/{cotizacion.token_validacion}/"
        
        config_empresa = ConfiguracionEmpresa.get_config()
        
        # Contexto para el template del cliente
        context_cliente = {
            'cotizacion': cotizacion,
            'mensaje_adicional': mensaje_adicional,
            'url_aprobar': url_aprobar,
            'url_rechazar': url_rechazar,
            'url_modificar': url_modificar,
            'url_ver': url_ver,
            'config_empresa': config_empresa,
            'es_copia_remitente': False,
        }
        
        # Renderizar HTML
        html_content = render_to_string(
            'cotizaciones/emails/cotizacion_cliente.html',
            context_cliente
        )
        
        subject = f'Cotización N° {cotizacion.numero} - {config_empresa.nombre}'
        
        # Enviar email principal con reintentos
        exito_principal, mensaje_principal = enviar_email_con_reintentos(
            subject=subject,
            html_content=html_content,
            recipient_list=[email_destinatario],
            max_intentos=3,
            timeout_segundos=20,
            fail_silently=False
        )
        
        resultado = {
            'email_principal': {
                'exito': exito_principal,
                'mensaje': mensaje_principal,
                'destinatario': email_destinatario
            }
        }
        
        # Enviar copia si está activado
        if enviar_copia and email_copia:
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
                recipient_list=[email_copia],
                max_intentos=2,
                timeout_segundos=15,
                fail_silently=True  # No fallar si falla la copia
            )
            
            resultado['email_copia'] = {
                'exito': exito_copia,
                'mensaje': mensaje_copia,
                'destinatario': email_copia
            }
        
        return exito_principal, mensaje_principal, resultado
        
    except Exception as e:
        logger.error(f"Error en enviar_cotizacion_email_async: {str(e)}")
        return False, str(e), {'error': str(e)}


def verificar_configuracion_email():
    """
    Verifica que la configuración de email esté correcta
    
    Returns:
        tuple: (válido: bool, errores: list)
    """
    errores = []
    
    if not hasattr(settings, 'EMAIL_HOST') or not settings.EMAIL_HOST:
        errores.append("EMAIL_HOST no está configurado")
    
    if not hasattr(settings, 'EMAIL_PORT') or not settings.EMAIL_PORT:
        errores.append("EMAIL_PORT no está configurado")
    
    if not hasattr(settings, 'DEFAULT_FROM_EMAIL') or not settings.DEFAULT_FROM_EMAIL:
        errores.append("DEFAULT_FROM_EMAIL no está configurado")
    
    # Verificar si EMAIL_BACKEND está configurado
    if hasattr(settings, 'EMAIL_BACKEND'):
        if 'console' in settings.EMAIL_BACKEND.lower():
            errores.append("EMAIL_BACKEND está en modo console (solo para desarrollo)")
    
    return len(errores) == 0, errores






