from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone
from datetime import datetime, timedelta
import uuid

class Cliente(models.Model):
    nombre = models.CharField(max_length=200)
    rut = models.CharField(max_length=20, blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

class RepresentanteCliente(models.Model):
    """Representantes o contactos de un cliente"""
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='representantes')
    nombre = models.CharField(max_length=200)
    orden = models.IntegerField(default=0)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['orden', 'nombre']
        verbose_name = "Representante"
        verbose_name_plural = "Representantes"

    def __str__(self):
        return f"{self.nombre} ({self.cliente.nombre})"

class TipoTrabajo(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

class CategoriaServicio(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    orden = models.IntegerField(default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['orden', 'nombre']

    def __str__(self):
        return self.nombre

class ServicioBase(models.Model):
    categoria = models.ForeignKey(CategoriaServicio, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField()
    precio_base = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    unidad = models.CharField(max_length=50, default='UND')
    es_parametrizable = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['categoria', 'nombre']

    def __str__(self):
        return f"{self.categoria.nombre} - {self.nombre}"

class ParametroServicio(models.Model):
    TIPO_CHOICES = [
        ('text', 'Texto'),
        ('number', 'Número'),
        ('select', 'Selección'),
        ('boolean', 'Sí/No'),
    ]
    
    servicio = models.ForeignKey(ServicioBase, on_delete=models.CASCADE, related_name='parametros')
    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    requerido = models.BooleanField(default=True)
    opciones = models.TextField(blank=True, null=True, help_text="Para tipo select: opcion1,opcion2,opcion3")
    valor_por_defecto = models.CharField(max_length=200, blank=True, null=True)
    orden = models.IntegerField(default=0)

    class Meta:
        ordering = ['orden', 'nombre']

    def __str__(self):
        return f"{self.servicio.nombre} - {self.nombre}"

    def get_opciones_list(self):
        if self.opciones:
            return [opt.strip() for opt in self.opciones.split(',')]
        return []

class Material(models.Model):
    codigo = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    unidad = models.CharField(max_length=50, default='UND')
    categoria = models.CharField(max_length=100, blank=True, null=True)
    activo = models.BooleanField(default=True)
    
    # Campos de mantenimiento
    TIPO_MANTENIMIENTO_CHOICES = [
        ('dias', 'Por Días'),
        ('horas', 'Por Horas de Uso'),
    ]
    
    requiere_mantenimiento = models.BooleanField(default=False, verbose_name='Requiere Mantenimiento')
    tipo_mantenimiento = models.CharField(
        max_length=10,
        choices=TIPO_MANTENIMIENTO_CHOICES,
        default='dias',
        verbose_name='Tipo de Mantenimiento',
        help_text='Seleccione si el mantenimiento es por días o por horas de uso'
    )
    
    # Mantenimiento por DÍAS
    dias_entre_mantenimiento = models.IntegerField(
        null=True, 
        blank=True,
        verbose_name='Días entre Mantenimiento',
        help_text='Número de días entre cada mantenimiento'
    )
    fecha_ultimo_mantenimiento = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha Último Mantenimiento',
        help_text='Fecha del último mantenimiento realizado'
    )
    dias_alerta_previa = models.IntegerField(
        default=7,
        verbose_name='Días de Alerta Previa',
        help_text='Días antes del vencimiento para enviar notificación'
    )
    
    # Mantenimiento por HORAS
    horas_entre_mantenimiento = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Horas entre Mantenimiento',
        help_text='Número de horas de uso entre cada mantenimiento'
    )
    horas_uso_acumuladas = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='Horas de Uso Acumuladas',
        help_text='Total de horas de uso desde el último mantenimiento'
    )
    horas_alerta_previa = models.IntegerField(
        default=10,
        verbose_name='Horas de Alerta Previa',
        help_text='Horas antes del vencimiento para enviar notificación'
    )

    class Meta:
        ordering = ['categoria', 'nombre']

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"
    
    def dias_hasta_proximo_mantenimiento(self):
        """Calcula los días hasta el próximo mantenimiento (solo para tipo 'dias')"""
        if not self.requiere_mantenimiento or self.tipo_mantenimiento != 'dias':
            return None
        if not self.fecha_ultimo_mantenimiento or not self.dias_entre_mantenimiento:
            return None
        
        from datetime import timedelta
        from django.utils import timezone
        
        fecha_proximo = self.fecha_ultimo_mantenimiento + timedelta(days=self.dias_entre_mantenimiento)
        dias_restantes = (fecha_proximo - timezone.now().date()).days
        return dias_restantes
    
    def horas_hasta_proximo_mantenimiento(self):
        """Calcula las horas hasta el próximo mantenimiento (solo para tipo 'horas')"""
        if not self.requiere_mantenimiento or self.tipo_mantenimiento != 'horas':
            return None
        if not self.horas_entre_mantenimiento:
            return None
        
        horas_restantes = self.horas_entre_mantenimiento - float(self.horas_uso_acumuladas)
        return horas_restantes
    
    def necesita_mantenimiento(self):
        """Verifica si el material necesita mantenimiento pronto"""
        if not self.requiere_mantenimiento:
            return False
            
        if self.tipo_mantenimiento == 'dias':
            dias = self.dias_hasta_proximo_mantenimiento()
            if dias is None:
                return False
            return dias <= self.dias_alerta_previa
        else:  # horas
            horas = self.horas_hasta_proximo_mantenimiento()
            if horas is None:
                return False
            return horas <= self.horas_alerta_previa
    
    def esta_vencido(self):
        """Verifica si el mantenimiento está vencido"""
        if not self.requiere_mantenimiento:
            return False
            
        if self.tipo_mantenimiento == 'dias':
            dias = self.dias_hasta_proximo_mantenimiento()
            if dias is None:
                return False
            return dias < 0
        else:  # horas
            horas = self.horas_hasta_proximo_mantenimiento()
            if horas is None:
                return False
            return horas < 0
    
    def get_estado_mantenimiento(self):
        """Retorna el estado del mantenimiento para mostrar en la UI"""
        if not self.requiere_mantenimiento:
            return {'estado': 'sin_mantenimiento', 'clase': '', 'texto': 'No', 'tipo': None}
        
        if self.tipo_mantenimiento == 'dias':
            dias = self.dias_hasta_proximo_mantenimiento()
            if dias is None:
                return {'estado': 'sin_fecha', 'clase': 'warning', 'texto': 'Sin fecha inicial', 'tipo': 'dias'}
            
            if dias < 0:
                return {'estado': 'vencido', 'clase': 'danger', 'texto': f'{abs(dias)} días', 'tipo': 'dias'}
            elif dias <= self.dias_alerta_previa:
                return {'estado': 'proximo', 'clase': 'warning', 'texto': f'Vence en {dias} días', 'tipo': 'dias'}
            else:
                return {'estado': 'ok', 'clase': 'success', 'texto': f'Al día ({dias} días)', 'tipo': 'dias'}
        
        else:  # horas
            horas = self.horas_hasta_proximo_mantenimiento()
            if horas is None:
                return {'estado': 'sin_inicio', 'clase': 'warning', 'texto': 'Sin horas registradas', 'tipo': 'horas'}
            
            if horas < 0:
                return {'estado': 'vencido', 'clase': 'danger', 'texto': f'{abs(horas):.1f}h extra', 'tipo': 'horas'}
            elif horas <= self.horas_alerta_previa:
                return {'estado': 'proximo', 'clase': 'warning', 'texto': f'{horas:.1f}h restantes', 'tipo': 'horas'}
            else:
                return {'estado': 'ok', 'clase': 'success', 'texto': f'{horas:.1f}h disponibles', 'tipo': 'horas'}
        
    def esta_prestado(self):
        """Verifica si el material está en préstamo"""
        return hasattr(self, 'prestamo_actual')

    def get_info_prestamo(self):
        """Obtiene info del préstamo si existe"""
        if self.esta_prestado():
            return {
                'prestado': True,
                'prestado_a': self.prestamo_actual.prestado_a,
                'fecha_devolucion': self.prestamo_actual.fecha_devolucion,
                'dias_restantes': self.prestamo_actual.dias_restantes(),
                'vencido': self.prestamo_actual.esta_vencido()
            }
        return {'prestado': False}

class Cotizacion(models.Model):
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('enviada', 'Enviada'),
        ('revisada', 'En Revisión'),
        ('aprobada', 'Aprobada'),
        ('rechazada', 'Rechazada'),
        ('requiere_cambios', 'Requiere Cambios'),
        ('vencida', 'Vencida'),
        ('finalizada', 'Finalizada'),
    ]

    numero = models.CharField(max_length=20, unique=True, null=True, blank=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True)
    cliente_nombre_respaldo = models.CharField(max_length=200, blank=True, help_text="Nombre del cliente guardado como respaldo")
    representante = models.ForeignKey('RepresentanteCliente', on_delete=models.SET_NULL, null=True, blank=True, related_name='cotizaciones')
    representante_nombre_respaldo = models.CharField(max_length=200, blank=True, help_text="Nombre del representante guardado como respaldo")
    referencia = models.TextField()
    lugar = models.CharField(max_length=200)
    tipo_trabajo = models.ForeignKey(TipoTrabajo, on_delete=models.CASCADE)
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_vencimiento = models.DateField(blank=True, null=True)

    fecha_realizacion = models.DateField(blank=True, null=True,verbose_name="Fecha Aproximada de Realización",help_text="Fecha estimada para realizar el trabajo (solo para cotizaciones aprobadas)")
    fecha_realizacion_original = models.DateField(blank=True, null=True,verbose_name="Fecha Original de Realización",help_text="Guarda la fecha original para detectar cambios")
    fecha_finalizacion = models.DateTimeField(blank=True, null=True,verbose_name="Fecha de Finalización",help_text="Fecha en que se completó el trabajo")
    feedback_solicitado = models.BooleanField(default=False,verbose_name="Feedback Solicitado",help_text="Indica si ya se envió el correo de feedback al cliente")
    fecha_feedback = models.DateTimeField(blank=True,null=True,verbose_name="Fecha de Solicitud de Feedback",help_text="Fecha en que se envió la solicitud de feedback")   
    
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='borrador')
    
    # Valores calculados
    subtotal_servicios = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    subtotal_materiales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    subtotal_mano_obra = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gastos_traslado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    valor_neto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    valor_iva = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    valor_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    observaciones = models.TextField(blank=True, null=True)
    creado_por = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # NUEVOS CAMPOS PARA EMAIL
    token_validacion = models.CharField(max_length=64, unique=True, null=True, blank=True)
    fecha_envio = models.DateTimeField(null=True, blank=True)
    email_enviado_a = models.EmailField(null=True, blank=True)
    fecha_respuesta_cliente = models.DateTimeField(null=True, blank=True)
    motivo_rechazo = models.TextField(null=True, blank=True)
    comentarios_cliente = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha_creacion']

    def save(self, *args, **kwargs):
        # Guardar nombre del cliente como respaldo antes de guardar
        if self.cliente:
            self.cliente_nombre_respaldo = self.cliente.nombre
        
        if self.representante:
            self.representante_nombre_respaldo = self.representante.nombre
        
        # ⭐ DEBUG: Imprimir antes de guardar
        print(f"💾 GUARDANDO Cotización:")
        print(f"   - fecha_realizacion: {self.fecha_realizacion}")
        print(f"   - fecha_finalizacion: {self.fecha_finalizacion}")
        
        super().save(*args, **kwargs)
        
        # ⭐ DEBUG: Imprimir después de guardar
        print(f"✅ GUARDADO OK - ID: {self.pk}")
    
    def get_nombre_cliente(self):
        """Retorna el nombre del cliente, incluso si fue eliminado"""
        if self.cliente:
            return self.cliente.nombre
        return self.cliente_nombre_respaldo or "Cliente Eliminado"
    
    def get_nombre_representante(self):
        """Retorna el nombre del representante"""
        if self.representante:
            return self.representante.nombre
        return self.representante_nombre_respaldo or ""
    
    def __str__(self):
        return f"Cotización {self.numero} - {self.get_nombre_cliente()}"

    def calcular_totales(self):
        # Calcular subtotales de servicios
        self.subtotal_servicios = sum(
            item.subtotal for item in self.items_servicio.all()
        )
        
        # Calcular subtotales de materiales
        self.subtotal_materiales = sum(
            item.subtotal for item in self.items_material.all()
        )
        
        # Calcular subtotales de mano de obra
        self.subtotal_mano_obra = sum(
            item.subtotal for item in self.items_mano_obra.all()
        )
        
        # Calcular valor neto
        self.valor_neto = (
            self.subtotal_servicios + 
            self.subtotal_materiales + 
            self.subtotal_mano_obra + 
            self.gastos_traslado
        )
        
        # Calcular IVA (19%)
        self.valor_iva = self.valor_neto * Decimal('0.19')
        
        # Calcular total
        self.valor_total = self.valor_neto + self.valor_iva
        
        self.save()

    def generar_numero(self):
        if not self.numero:
            ultimo_numero = Cotizacion.objects.filter(
                numero__startswith=f"{self.fecha_creacion.year}"
            ).order_by('-numero').first()
            
            if ultimo_numero:
                ultimo_num = int(ultimo_numero.numero.split('-')[-1])
                nuevo_num = ultimo_num + 1
            else:
                nuevo_num = 1
                
            self.numero = f"{self.fecha_creacion.year}-{nuevo_num:04d}"
    
    # NUEVOS MÉTODOS PARA EMAIL
    def generar_token(self):
        """Genera un token único para validación de respuestas"""
        import secrets
        self.token_validacion = secrets.token_urlsafe(48)
        self.save()
        return self.token_validacion
    
    def puede_responder(self):
        """Verifica si la cotización puede recibir respuestas"""
        return self.estado in ['enviada', 'revisada']
    
    def acumular_horas_materiales(self):
        """
        Acumula las horas de uso de los materiales cuando la cotización 
        se aprueba o finaliza.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Solo acumular si la cotización está aprobada o finalizada
        if self.estado not in ['aprobada', 'finalizada']:
            logger.info(f"Cotización {self.numero} - Estado '{self.estado}' no permite acumular horas")
            return
        
        logger.info(f"Iniciando acumulación de horas para cotización {self.numero}")
        
        # Iterar sobre todos los items de material
        items_procesados = 0
        for item in self.items_material.all():
            material = item.material
            
            logger.info(f"Procesando material {material.codigo} - {material.nombre}")
            logger.info(f"  - Requiere mantenimiento: {material.requiere_mantenimiento}")
            logger.info(f"  - Tipo mantenimiento: {material.tipo_mantenimiento}")
            logger.info(f"  - Horas uso item: {item.horas_uso}")
            logger.info(f"  - Horas acumuladas actual: {material.horas_uso_acumuladas}")
            
            # Si el material requiere mantenimiento por horas y hay horas registradas
            if (material.requiere_mantenimiento and 
                material.tipo_mantenimiento == 'horas' and 
                item.horas_uso is not None and  # ✅ FIX 1: Verifica explícitamente None
                item.horas_uso > 0):              # ✅ FIX 2: Verifica que sea > 0
                
                horas_previas = material.horas_uso_acumuladas
                # Acumular las horas al material con conversión explícita
                material.horas_uso_acumuladas = float(material.horas_uso_acumuladas) + float(item.horas_uso)  # ✅ FIX 3
                material.save()
                items_procesados += 1
                
                logger.info(f"  ✓ Horas acumuladas: {horas_previas} + {item.horas_uso} = {material.horas_uso_acumuladas}")
            else:
                logger.info(f"  ✗ Material no cumple condiciones para acumular horas")
        
        logger.info(f"Finalizado. Total items procesados: {items_procesados}")

    def puede_editarse(self):
        """
        Verifica si la cotización puede editarse.
        - Borradores: siempre editables
        - Aprobadas: editables pero cambia a requiere_cambios
        - Requiere cambios: editables
        - Otras: no editables
        """
        return self.estado in ['borrador', 'aprobada', 'requiere_cambios']
    
    def requiere_notificacion_fecha(self):
        """
        Verifica si se debe notificar al cliente sobre cambio de fecha.
        Retorna True si la fecha de realización cambió y la cotización está aprobada.
        """
        if self.estado != 'aprobada':
            return False
        
        if not self.fecha_realizacion:
            return False
        
        # Si hay fecha original y es diferente a la actual
        if self.fecha_realizacion_original and self.fecha_realizacion != self.fecha_realizacion_original:
            return True
        
        return False
    
    def actualizar_fecha_realizacion(self, nueva_fecha, usuario=None):
        """
        Actualiza la fecha de realización y maneja las notificaciones necesarias.
        
        Args:
            nueva_fecha: Nueva fecha de realización
            usuario: Usuario que hace el cambio (para notificaciones)
        
        Returns:
            dict con información sobre las acciones realizadas
        """
        from notificaciones.models import Notificacion
        from django.core.mail import send_mail
        from django.conf import settings
        
        resultado = {
            'fecha_actualizada': False,
            'notificacion_enviada': False,
            'email_enviado': False,
            'error': None
        }
        
        # Si no hay cambio, no hacer nada
        if self.fecha_realizacion == nueva_fecha:
            return resultado
        
        # Guardar fecha original si no existe
        if not self.fecha_realizacion_original and self.fecha_realizacion:
            self.fecha_realizacion_original = self.fecha_realizacion
        
        fecha_anterior = self.fecha_realizacion
        self.fecha_realizacion = nueva_fecha
        self.save()
        resultado['fecha_actualizada'] = True
        
        # Si la cotización está aprobada, notificar
        if self.estado == 'aprobada' and fecha_anterior:
            # Crear notificación para el creador de la cotización
            if usuario:
                try:
                    Notificacion.objects.create(
                        usuario=self.creado_por,
                        titulo=f"Fecha de Realización Actualizada",
                        mensaje=f"La cotización {self.numero} cambió su fecha de realización de {fecha_anterior.strftime('%d/%m/%Y')} a {nueva_fecha.strftime('%d/%m/%Y')}",
                        tipo='info',
                        url=f'/cotizaciones/{self.pk}/'
                    )
                    resultado['notificacion_enviada'] = True
                except Exception as e:
                    resultado['error'] = f"Error creando notificación: {str(e)}"
            
            # Enviar email al cliente si tiene email
            if self.email_enviado_a:
                try:
                    asunto = f"Cambio de Fecha - Cotización {self.numero}"
                    mensaje = f"""
Estimado/a {self.get_nombre_cliente()},

Le informamos que la fecha de realización del trabajo para la cotización {self.numero} ha sido modificada.

Detalles:
- Referencia: {self.referencia}
- Fecha anterior: {fecha_anterior.strftime('%d/%m/%Y')}
- Nueva fecha: {nueva_fecha.strftime('%d/%m/%Y')}
- Lugar: {self.lugar}

Cualquier consulta, no dude en contactarnos.

Saludos cordiales,
{settings.DEFAULT_FROM_EMAIL}
                    """
                    
                    send_mail(
                        asunto,
                        mensaje,
                        settings.DEFAULT_FROM_EMAIL,
                        [self.email_enviado_a],
                        fail_silently=False,
                    )
                    resultado['email_enviado'] = True
                except Exception as e:
                    resultado['error'] = f"Error enviando email: {str(e)}"
        
        return resultado
    
    def debe_solicitar_feedback(self):
        """
        Verifica si debe solicitarse feedback al cliente.
        Condiciones:
        - Estado: finalizada
        - No se ha solicitado feedback antes
        - Han pasado 7 días desde la finalización
        - Cliente tiene email
        """
        if self.estado != 'finalizada':
            return False
        
        if self.feedback_solicitado:
            return False
        
        if not self.email_enviado_a:
            return False
        
        # Verificar si pasaron 7 días desde que se finalizó
        # Asumimos que fecha_respuesta_cliente se usa cuando se finaliza
        # O podríamos agregar un campo fecha_finalizacion
        if hasattr(self, 'fecha_finalizacion') and self.fecha_finalizacion:
            dias_transcurridos = (timezone.now().date() - self.fecha_finalizacion).days
            return dias_transcurridos >= 7
        
        return False
    
    def solicitar_feedback_cliente(self):
        """
        Envía email solicitando feedback al cliente 1 semana después de finalizar.
        Usa Resend API con HTML profesional.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        if not self.debe_solicitar_feedback():
            return {'success': False, 'error': 'No cumple condiciones para solicitar feedback'}
        
        try:
            config_empresa = ConfiguracionEmpresa.get_config()
            asunto = f"¿Cómo estuvo nuestro trabajo? - Cotización {self.numero}"
            
            # HTML del email
            html_mensaje = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
            </head>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <div style="background: linear-gradient(135deg, #1f5fa5, #2575c0); color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                        <h2 style="margin: 0;">{config_empresa.nombre}</h2>
                        <p style="margin: 5px 0; opacity: 0.9;">Solicitud de Feedback</p>
                    </div>
                    
                    <div style="background: white; padding: 20px; border: 1px solid #ddd; border-top: none;">
                        <h3 style="color: #1f5fa5;">¿Cómo estuvo nuestro trabajo?</h3>
                        
                        <p style="margin: 20px 0;">Estimado/a <strong>{self.get_nombre_cliente()}</strong>,</p>
                        
                        <p>Esperamos que el trabajo realizado haya cumplido con sus expectativas.</p>
                        
                        <div style="background: #f0f8ff; padding: 15px; border-left: 4px solid #2575c0; margin: 20px 0;">
                            <h4 style="margin: 0 0 10px; color: #1f5fa5;">Detalles del trabajo:</h4>
                            <table style="width: 100%;">
                                <tr>
                                    <td style="padding: 4px; font-weight: bold;">Cotización:</td>
                                    <td style="padding: 4px;">{self.numero}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 4px; font-weight: bold;">Referencia:</td>
                                    <td style="padding: 4px;">{self.referencia}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 4px; font-weight: bold;">Lugar:</td>
                                    <td style="padding: 4px;">{self.lugar}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 4px; font-weight: bold;">Tipo de trabajo:</td>
                                    <td style="padding: 4px;">{self.tipo_trabajo.nombre}</td>
                                </tr>
                            </table>
                        </div>
                        
                        <p>Nos encantaría conocer su opinión sobre el servicio prestado. Su feedback es voluntario 
                        pero muy importante para nosotros, ya que nos ayuda a mejorar continuamente.</p>
                        
                        <p>Si desea compartir su experiencia, puede responder este correo con sus comentarios.</p>
                        
                        <p style="margin-top: 30px;">¡Muchas gracias por confiar en nosotros!</p>
                        
                        <p><strong>Saludos cordiales</strong><br>
                        {config_empresa.nombre}</p>
                    </div>
                    
                    <div style="text-align: center; padding: 20px; color: #666; font-size: 12px; border-top: 1px solid #ddd;">
                        <p style="margin: 5px 0;">📧 {config_empresa.email}</p>
                        <p style="margin: 5px 0;">📞 {config_empresa.telefono}</p>
                        <p style="margin: 5px 0;">📍 {config_empresa.direccion}</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Importar función de envío con reintentos
            from cotizaciones.views import enviar_email_con_reintentos
            
            exito, mensaje_resultado = enviar_email_con_reintentos(
                subject=asunto,
                html_content=html_mensaje,
                recipient_list=[self.email_enviado_a],
                max_intentos=3,
                timeout_segundos=20,
                fail_silently=False
            )
            
            if exito:
                # Marcar como solicitado
                self.feedback_solicitado = True
                self.fecha_feedback = timezone.now()
                self.save()
                
                logger.info(f"✅ Feedback solicitado para cotización {self.numero}")
                return {'success': True, 'mensaje': 'Feedback solicitado exitosamente'}
            else:
                logger.error(f"❌ Error al solicitar feedback para {self.numero}: {mensaje_resultado}")
                return {'success': False, 'error': mensaje_resultado}
            
        except Exception as e:
            logger.error(f"❌ Excepción al solicitar feedback para {self.numero}: {str(e)}")
            return {'success': False, 'error': str(e)}

    fecha_finalizacion = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Fecha de Finalización",
        help_text="Fecha en que se finalizó el trabajo"
    )

    def marcar_como_finalizada(self, usuario=None):
        """
        Marca la cotización como finalizada y registra la fecha.
        """
        if self.estado != 'aprobada':
            return {'success': False, 'error': 'Solo se pueden finalizar cotizaciones aprobadas'}
        
        self.estado = 'finalizada'
        self.fecha_finalizacion = timezone.now()
        self.save()
        
        # Crear notificación
        if usuario:
            from notificaciones.models import Notificacion
            Notificacion.objects.create(
                usuario=self.creado_por,
                titulo=f"Trabajo Finalizado",
                mensaje=f"El trabajo de la cotización {self.numero} ha sido marcado como finalizado",
                tipo='success',
                url=f'/cotizaciones/{self.pk}/'
            )
        
        return {'success': True, 'mensaje': 'Cotización finalizada exitosamente'}

class ItemServicio(models.Model):
    cotizacion = models.ForeignKey(Cotizacion, on_delete=models.CASCADE, related_name='items_servicio')
    servicio = models.ForeignKey(ServicioBase, on_delete=models.CASCADE)
    descripcion_personalizada = models.TextField(blank=True, null=True)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    orden = models.IntegerField(default=0)

    class Meta:
        ordering = ['orden']

    def save(self, *args, **kwargs):
        self.subtotal = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)

class ParametroItemServicio(models.Model):
    item_servicio = models.ForeignKey(ItemServicio, on_delete=models.CASCADE, related_name='parametros')
    parametro = models.ForeignKey(ParametroServicio, on_delete=models.CASCADE)
    valor = models.TextField()

class ItemMaterial(models.Model):
    cotizacion = models.ForeignKey(Cotizacion, on_delete=models.CASCADE, related_name='items_material')
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    descripcion_personalizada = models.TextField(blank=True, null=True)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Campo para materiales con mantenimiento por horas
    horas_uso = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name='Horas de Uso',
        help_text='Horas de uso estimadas para materiales con mantenimiento por horas'
    )

    class Meta:
        ordering = ['material__categoria', 'material__nombre']

    def save(self, *args, **kwargs):
        self.subtotal = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)

class ItemManoObra(models.Model):
    cotizacion = models.ForeignKey(Cotizacion, on_delete=models.CASCADE, related_name='items_mano_obra')
    descripcion = models.TextField()
    horas = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)])
    precio_hora = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.subtotal = self.horas * self.precio_hora
        super().save(*args, **kwargs)

class PlantillaCotizacion(models.Model):
    nombre = models.CharField(max_length=200)
    tipo_trabajo = models.ForeignKey(TipoTrabajo, on_delete=models.CASCADE)
    descripcion = models.TextField(blank=True, null=True)
    activa = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

class ItemPlantillaServicio(models.Model):
    plantilla = models.ForeignKey(PlantillaCotizacion, on_delete=models.CASCADE, related_name='servicios')
    servicio = models.ForeignKey(ServicioBase, on_delete=models.CASCADE)
    cantidad_default = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    orden = models.IntegerField(default=0)

    class Meta:
        ordering = ['orden']

class ConfiguracionEmpresa(models.Model):
    nombre = models.CharField(max_length=200, default="JOSE E. ALVARADO N.")
    descripcion = models.TextField(default="SERVISIOS ELECTROMECANICOS\nINSTALACIÓN, MANTENCIÓN Y REPARACIÓN DE BOMBAS DE AGUA.\nSUPERFICIE Y SUMERGIBLES")
    direccion = models.CharField(max_length=200, default="PJE. SANTA ELISA 2437 OSORNO")
    telefono = models.CharField(max_length=100, default="9-76193683")
    email = models.EmailField(default="J_ALVARADO33@HOTMAIL.COM")
    logo = models.ImageField(upload_to='logos/', blank=True, null=True)
    
    class Meta:
        verbose_name = "Configuración de Empresa"
        verbose_name_plural = "Configuración de Empresa"
    
    def save(self, *args, **kwargs):
        # Asegurar que solo exista una instancia
        if not self.pk and ConfiguracionEmpresa.objects.exists():
            raise ValidationError('Solo puede existir una configuración de empresa')
        super().save(*args, **kwargs)
    
    @classmethod
    def get_config(cls):
        config, created = cls.objects.get_or_create(pk=1)
        return config

class CategoriaEmpleado(models.Model):
    """Categorías de trabajo que pueden realizar los empleados"""
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    orden = models.IntegerField(default=0)

    class Meta:
        ordering = ['orden', 'nombre']
        verbose_name = "Categoría de Empleado"
        verbose_name_plural = "Categorías de Empleados"

    def __str__(self):
        return self.nombre

class EmpleadoCategoria(models.Model):
    """Relación entre empleados y categorías de trabajo"""
    empleado = models.ForeignKey(
        'home.PerfilEmpleado', 
        on_delete=models.CASCADE,
        related_name='categorias_trabajo'
    )
    categoria = models.ForeignKey(
        CategoriaEmpleado, 
        on_delete=models.CASCADE,
        related_name='empleados'
    )
    fecha_asignacion = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True)

    class Meta:
        unique_together = ('empleado', 'categoria')
        verbose_name = "Empleado-Categoría"
        verbose_name_plural = "Empleados-Categorías"

    def __str__(self):
        return f"{self.empleado.nombre_completo} - {self.categoria.nombre}"

class ItemManoObraEmpleado(models.Model):
    """Empleados asignados a items de mano de obra"""
    item_mano_obra = models.ForeignKey(
        ItemManoObra, 
        on_delete=models.CASCADE,
        related_name='empleados_asignados'
    )
    empleado = models.ForeignKey(
        'home.PerfilEmpleado',
        on_delete=models.CASCADE,
        related_name='trabajos_asignados'
    )
    fecha_asignacion = models.DateTimeField(auto_now_add=True)
    horas_asignadas = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        validators=[MinValueValidator(0)]
    )
    completado = models.BooleanField(default=False)
    fecha_completado = models.DateTimeField(blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('item_mano_obra', 'empleado')
        verbose_name = "Empleado Asignado"
        verbose_name_plural = "Empleados Asignados"

    def __str__(self):
        return f"{self.empleado.nombre_completo} - {self.item_mano_obra.descripcion}"

    def marcar_completado(self):
        """Marca el trabajo como completado"""
        self.completado = True
        self.fecha_completado = timezone.now()
        self.save()

class TrabajoEmpleado(models.Model):
    """Vista de trabajos para empleados"""
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('en_progreso', 'En Progreso'),
        ('completado', 'Completado'),
        ('suspendido', 'Suspendido'),
    ]

    empleado = models.ForeignKey(
        'home.PerfilEmpleado',
        on_delete=models.CASCADE,
        related_name='mis_trabajos'
    )
    cotizacion = models.ForeignKey(
        Cotizacion,
        on_delete=models.CASCADE,
        related_name='trabajos_empleados'
    )
    item_mano_obra = models.ForeignKey(
        ItemManoObra,
        on_delete=models.CASCADE
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente'
    )
    fecha_inicio = models.DateTimeField(blank=True, null=True)
    fecha_fin = models.DateTimeField(blank=True, null=True)
    horas_trabajadas = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )
    observaciones_empleado = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('empleado', 'item_mano_obra')
        ordering = ['-fecha_inicio']

    def __str__(self):
        return f"{self.empleado.nombre_completo} - {self.cotizacion.numero}"

class PrestamoMaterial(models.Model):
    """Sistema simple de préstamos de materiales"""
    
    material = models.OneToOneField(
        Material, 
        on_delete=models.CASCADE, 
        related_name='prestamo_actual',
        help_text='Material prestado'
    )
    
    prestado_a = models.CharField(
        max_length=200,
        verbose_name='Prestado a'
    )
    
    fecha_prestamo = models.DateField(
        default=timezone.now,
        verbose_name='Fecha de Préstamo'
    )
    
    fecha_devolucion = models.DateField(
        verbose_name='Fecha de Devolución'
    )
    
    observaciones = models.TextField(
        blank=True,
        null=True,
        verbose_name='Observaciones'
    )
    
    usuario_registro = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Registrado por'
    )
    
    fecha_registro = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-fecha_prestamo']
        verbose_name = 'Préstamo de Material'
        verbose_name_plural = 'Préstamos de Materiales'
    
    def __str__(self):
        return f"{self.material.codigo} - {self.prestado_a}"
    
    def save(self, *args, **kwargs):
        # Al crear préstamo, marcar material como inactivo
        self.material.activo = False
        self.material.save()
        super().save(*args, **kwargs)
    
    # NOTA: El método delete() se maneja en la vista para evitar conflictos
    # La vista eliminar_prestamo() se encarga de:
    # 1. Guardar en historial
    # 2. Marcar material como activo
    # 3. Eliminar préstamo
    
    def dias_restantes(self):
        """Días hasta devolución"""
        from datetime import date
        diferencia = (self.fecha_devolucion - date.today()).days
        return diferencia
    
    def esta_vencido(self):
        """Verifica si está vencido"""
        return self.dias_restantes() < 0
    
    def get_estado(self):
        """Estado del préstamo"""
        dias = self.dias_restantes()
        if dias < 0:
            return {
                'clase': 'danger',
                'texto': f'Vencido hace {abs(dias)} días',
                'icono': '🚨'
            }
        elif dias <= 3:
            return {
                'clase': 'warning',
                'texto': f'Vence en {dias} días',
                'icono': '⚠️'
            }
        else:
            return {
                'clase': 'success',
                'texto': f'{dias} días restantes',
                'icono': '✓'
            }

class HistorialPrestamo(models.Model):
    """Historial de préstamos devueltos"""
    
    material_codigo = models.CharField(max_length=50)
    material_nombre = models.CharField(max_length=200)
    
    prestado_a = models.CharField(max_length=200)
    
    fecha_prestamo = models.DateField()
    fecha_devolucion = models.DateField(verbose_name='Fecha esperada de devolución')
    fecha_devuelto = models.DateField(verbose_name='Fecha real de devolución')
    
    observaciones = models.TextField(blank=True, null=True)
    
    usuario_registro = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )
    
    fecha_registro = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-fecha_devuelto']
        verbose_name = 'Historial de Préstamo'
        verbose_name_plural = 'Historial de Préstamos'
    
    def __str__(self):
        return f"{self.material_codigo} - {self.prestado_a} ({self.fecha_devuelto})"
    
    def duracion_dias(self):
        """Duración real del préstamo"""
        return (self.fecha_devuelto - self.fecha_prestamo).days









    """Historial de préstamos devueltos"""
    
    material_codigo = models.CharField(max_length=50)
    material_nombre = models.CharField(max_length=200)
    
    prestado_a = models.CharField(max_length=200)
    
    fecha_prestamo = models.DateField()
    fecha_devolucion = models.DateField(verbose_name='Fecha esperada de devolución')
    fecha_devuelto = models.DateField(verbose_name='Fecha real de devolución')
    
    observaciones = models.TextField(blank=True, null=True)
    
    usuario_registro = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )
    
    fecha_registro = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-fecha_devuelto']
        verbose_name = 'Historial de Préstamo'
        verbose_name_plural = 'Historial de Préstamos'
    
    def __str__(self):
        return f"{self.material_codigo} - {self.prestado_a} ({self.fecha_devuelto})"
    
    def duracion_dias(self):
        """Duración real del préstamo"""
        return (self.fecha_devuelto - self.fecha_prestamo).day

class Solicitud_Web(models.Model):
    """
    Modelo INDEPENDIENTE para solicitudes desde la web pública.
    NO modifica clientes ni cotizaciones existentes.
    """
    
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('en_revision', 'En Revisión'),
        ('convertida', 'Convertida a Cotización'),
        ('descartada', 'Descartada'),
    ]
    
    # Datos del solicitante (guardados como STRING, no vinculados)
    nombre_solicitante = models.CharField(
        max_length=200,
        verbose_name='Nombre del Solicitante',
        help_text='Nombre ingresado por el visitante'
    )
    email_solicitante = models.EmailField(
        verbose_name='Email del Solicitante',
        blank=True,
        null=True
    )
    telefono_solicitante = models.CharField(
        max_length=50,
        verbose_name='Teléfono del Solicitante'
    )
    
    # Datos de la solicitud
    tipo_servicio_solicitado = models.CharField(
        max_length=299,
        verbose_name='Servicio Solicitado',
        help_text='Nombre del servicio que solicita'
    )
    ubicacion_trabajo = models.TextField(
        verbose_name='Ubicación del Trabajo',
        help_text='Dirección o lugar donde se requiere el servicio'
    )
    informacion_adicional = models.TextField(
        blank=True,
        null=True,
        verbose_name='Información Adicional',
        help_text='Detalles adicionales proporcionados por el cliente'
    )
    es_servicio_personalizado = models.BooleanField(
        default=False,
        verbose_name='Es Servicio Personalizado',
        help_text='Indica si es un servicio fuera del catálogo'
    )
    
    # Control de estado
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
        verbose_name='Estado'
    )
    
    # Fechas
    fecha_solicitud = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Solicitud'
    )
    fecha_revision = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Fecha de Revisión',
        help_text='Cuando un admin la revisa'
    )
    fecha_conversion = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Fecha de Conversión',
        help_text='Cuando se convierte a cotización'
    )
    
    # Vinculación SOLO después de conversión
    cotizacion_generada = models.ForeignKey(
        'Cotizacion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='solicitud_origen',
        verbose_name='Cotización Generada',
        help_text='Cotización creada a partir de esta solicitud (solo después de conversión)'
    )
    
    # Usuario que procesó (admin/gerente)
    procesada_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Procesada Por',
        help_text='Usuario que convirtió la solicitud'
    )
    
    # Notas internas (solo para admins)
    notas_internas = models.TextField(
        blank=True,
        null=True,
        verbose_name='Notas Internas',
        help_text='Notas del administrador (no visibles para el cliente)'
    )
    
    # Metadatos
    ip_origen = models.GenericIPAddressField(
        blank=True,
        null=True,
        verbose_name='IP de Origen'
    )
    user_agent = models.TextField(
        blank=True,
        null=True,
        verbose_name='User Agent'
    )
    
    class Meta:
        ordering = ['-fecha_solicitud']
        verbose_name = 'Solicitud Web'
        verbose_name_plural = 'Solicitudes Web'
        indexes = [
            models.Index(fields=['-fecha_solicitud']),
            models.Index(fields=['estado']),
        ]
    
    def __str__(self):
        return f"Solicitud #{self.id} - {self.nombre_solicitante} - {self.tipo_servicio_solicitado}"
    
    def marcar_en_revision(self, usuario):
        """Marca la solicitud como en revisión"""
        self.estado = 'en_revision'
        self.fecha_revision = timezone.now()
        self.procesada_por = usuario
        self.save()
    
    def marcar_descartada(self, usuario, motivo=''):
        """Marca la solicitud como descartada"""
        self.estado = 'descartada'
        if motivo:
            self.notas_internas = f"DESCARTADA: {motivo}\n\n{self.notas_internas or ''}"
        self.procesada_por = usuario
        self.save()
    
    def convertir_a_cotizacion(self, usuario, cliente, tipo_trabajo):
        from django.utils import timezone
        
        # Generar número de cotización
        anio_actual = timezone.now().year
        from cotizaciones.models import Cotizacion
        
        ultima_cotizacion = Cotizacion.objects.filter(
            numero__startswith=f'{anio_actual}-'
        ).exclude(
            numero__isnull=True
        ).order_by('-numero').first()
        
        if ultima_cotizacion and ultima_cotizacion.numero:
            try:
                ultimo_numero = int(ultima_cotizacion.numero.split('-')[1])
                nuevo_numero = ultimo_numero + 1
            except (ValueError, IndexError):
                nuevo_numero = 1
        else:
            nuevo_numero = 1
        
        numero_cotizacion = f'{anio_actual}-{nuevo_numero:04d}'
        
        # Preparar observaciones con datos de la solicitud
        observaciones = self.informacion_adicional
        
        # Crear cotización (sin modificar nada existente)
        cotizacion = Cotizacion.objects.create(
            numero=numero_cotizacion,
            cliente=cliente,
            cliente_nombre_respaldo=cliente.nombre,
            tipo_trabajo=tipo_trabajo,
            referencia=self.tipo_servicio_solicitado,
            lugar=self.ubicacion_trabajo,
            observaciones=observaciones,
            creado_por=usuario,
            estado='borrador',
            subtotal_servicios=0,
            subtotal_materiales=0,
            subtotal_mano_obra=0,
            gastos_traslado=0,
            valor_neto=0,
            valor_iva=0,
            valor_total=0
        )
        
        # Vincular cotización a esta solicitud
        self.cotizacion_generada = cotizacion
        self.estado = 'convertida'
        self.fecha_conversion = timezone.now()
        self.procesada_por = usuario
        self.save()
        
        return cotizacion
    
    def get_dias_pendiente(self):
        """Retorna cuántos días lleva pendiente"""
        if self.estado != 'pendiente':
            return 0
        delta = timezone.now() - self.fecha_solicitud
        return delta.days
    
    @property
    def es_urgente(self):
        """Solicitud con más de 2 días sin atender"""
        return self.estado == 'pendiente' and self.get_dias_pendiente() > 2

# ============================================================
# APP MOVIL -EVIDENCIA
# ============================================================

class EvidenciaTrabajo(models.Model):
    """Evidencias fotográficas del trabajo realizado"""
    trabajo = models.ForeignKey(
        TrabajoEmpleado,
        on_delete=models.CASCADE,
        related_name='evidencias'
    )
    imagen = models.ImageField(
        upload_to='evidencias_trabajos/%Y/%m/%d/',
        help_text='Foto de evidencia del trabajo'
    )
    descripcion = models.TextField(
        blank=True,
        null=True,
        help_text='Descripción de la evidencia'
    )
    fecha_subida = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-fecha_subida']
        verbose_name = 'Evidencia de Trabajo'
        verbose_name_plural = 'Evidencias de Trabajos'
    
    def __str__(self):
        return f"Evidencia {self.id} - Trabajo {self.trabajo.id}"

class GastoTrabajo(models.Model):
    """Gastos asociados a un trabajo"""
    trabajo = models.OneToOneField(
        TrabajoEmpleado,
        on_delete=models.CASCADE,
        related_name='gastos'
    )
    
    # Campos de gastos
    materiales = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Costo de materiales'
    )
    materiales_detalle = models.TextField(
        blank=True,
        null=True,
        help_text='Detalle de materiales utilizados'
    )
    
    transporte = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Costo de transporte'
    )
    transporte_detalle = models.TextField(
        blank=True,
        null=True,
        help_text='Detalle del transporte'
    )
    
    otros = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Otros gastos'
    )
    otros_detalle = models.TextField(
        blank=True,
        null=True,
        help_text='Detalle de otros gastos'
    )
    
    # Total calculado
    @property
    def total(self):
        return self.materiales + self.transporte + self.otros
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Gasto de Trabajo'
        verbose_name_plural = 'Gastos de Trabajos'
    
    def __str__(self):
        return f"Gastos - Trabajo {self.trabajo.id} - Total: ${self.total}"