import os
import logging
from time import sleep
from django.conf import settings
from django.template.loader import render_to_string

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
