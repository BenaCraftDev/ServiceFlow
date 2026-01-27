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
from django.core.mail import EmailMultiAlternatives

@login_required
@requiere_gerente_o_superior
def enviar_cotizacion_email(request, pk):
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