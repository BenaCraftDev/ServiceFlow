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

    numero = models.CharField(max_length=20, unique=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True)
    cliente_nombre_respaldo = models.CharField(max_length=200, blank=True, help_text="Nombre del cliente guardado como respaldo")
    representante = models.ForeignKey('RepresentanteCliente', on_delete=models.SET_NULL, null=True, blank=True, related_name='cotizaciones')
    representante_nombre_respaldo = models.CharField(max_length=200, blank=True, help_text="Nombre del representante guardado como respaldo")
    referencia = models.TextField()
    lugar = models.CharField(max_length=200)
    tipo_trabajo = models.ForeignKey(TipoTrabajo, on_delete=models.CASCADE)
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_vencimiento = models.DateField(blank=True, null=True)
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
        super().save(*args, **kwargs)
    
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