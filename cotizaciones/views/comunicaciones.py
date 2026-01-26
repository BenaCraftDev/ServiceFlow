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

