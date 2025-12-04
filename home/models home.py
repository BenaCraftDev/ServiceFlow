from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import re

def validar_rut(rut):
    """Valida el formato y dígito verificador del RUT chileno"""
    # Eliminar puntos y guión
    rut = rut.replace('.', '').replace('-', '').upper()
    
    # Verificar formato básico (7-8 dígitos + dígito verificador)
    if not re.match(r'^\d{7,8}[0-9K]$', rut):
        raise ValidationError('El RUT debe tener el formato: 12345678-9 o 12.345.678-9')
    
    # Separar número y dígito verificador
    rut_numero = rut[:-1]
    dv = rut[-1]
    
    # Calcular dígito verificador
    suma = 0
    multiplo = 2
    
    for i in reversed(rut_numero):
        suma += int(i) * multiplo
        multiplo += 1
        if multiplo == 8:
            multiplo = 2
    
    resto = suma % 11
    dv_calculado = 11 - resto
    
    if dv_calculado == 11:
        dv_calculado = '0'
    elif dv_calculado == 10:
        dv_calculado = 'K'
    else:
        dv_calculado = str(dv_calculado)
    
    if dv != dv_calculado:
        raise ValidationError('El RUT ingresado no es válido')

def formatear_rut(rut):
    """Formatea el RUT al formato 12.345.678-9"""
    # Limpiar el RUT
    rut = rut.replace('.', '').replace('-', '').upper()
    
    # Separar número y dígito verificador
    rut_numero = rut[:-1]
    dv = rut[-1]
    
    # Formatear con puntos
    rut_formateado = ""
    for i, digit in enumerate(reversed(rut_numero)):
        if i > 0 and i % 3 == 0:
            rut_formateado = "." + rut_formateado
        rut_formateado = digit + rut_formateado
    
    return f"{rut_formateado}-{dv}"

class PerfilEmpleado(models.Model):
    CARGO_CHOICES = [
        ('empleado', 'Empleado'),
        ('supervisor', 'Supervisor'),
        ('gerente', 'Gerente'),
        ('director', 'Director'),
        ('admin', 'Administrador'),
    ]
    
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE,
        verbose_name="Usuario"
    )
    rut = models.CharField(
        max_length=12,
        unique=True,
        verbose_name="RUT",
        help_text="Formato: 12.345.678-9"
    )
    cargo = models.CharField(
        max_length=20,
        choices=CARGO_CHOICES,
        default='empleado',
        verbose_name="Cargo"
    )
    fecha_ingreso = models.DateField(
        verbose_name="Fecha de Ingreso"
    )
    telefono = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        verbose_name="Teléfono"
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )
    salario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Salario"
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Creación"
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Última Actualización"
    )

    class Meta:
        verbose_name = "Perfil de Empleado"
        verbose_name_plural = "Perfiles de Empleados"
        ordering = ['user__first_name', 'user__last_name']

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.get_cargo_display()} - RUT: {self.rut}"

    def clean(self):
        """Validaciones personalizadas"""
        if self.telefono and not self.telefono.replace('+', '').replace('-', '').replace(' ', '').isdigit():
            raise ValidationError({'telefono': 'El teléfono debe contener solo números, espacios, guiones y el signo +'})
        
        # Validar RUT
        if self.rut:
            validar_rut(self.rut)

    def save(self, *args, **kwargs):
        # Formatear RUT antes de guardar
        if self.rut:
            self.rut = formatear_rut(self.rut)
        
        self.clean()
        super().save(*args, **kwargs)

    # Métodos para verificar jerarquía de cargos
    def es_admin(self):
        """Verifica si es administrador"""
        return self.cargo == 'admin'
    
    def es_director(self):
        """Verifica si es director"""
        return self.cargo == 'director'
    
    def es_gerente(self):
        """Verifica si es gerente"""
        return self.cargo == 'gerente'
    
    def es_supervisor(self):
        """Verifica si es supervisor"""
        return self.cargo == 'supervisor'
    
    def es_empleado(self):
        """Verifica si es empleado base"""
        return self.cargo == 'empleado'

    # Métodos para verificar permisos jerárquicos
    def es_director_o_superior(self):
        """Verifica si es director o administrador"""
        return self.cargo in ['director', 'admin']
    
    def es_gerente_o_superior(self):
        """Verifica si es gerente, director o administrador"""
        return self.cargo in ['gerente', 'director', 'admin']
    
    def es_supervisor_o_superior(self):
        """Verifica si es supervisor o superior"""
        return self.cargo in ['supervisor', 'gerente', 'director', 'admin']

    def puede_gestionar_usuario(self, otro_perfil):
        """Verifica si puede gestionar a otro usuario basado en la jerarquía"""
        jerarquia = {
            'empleado': 0,
            'supervisor': 1,
            'gerente': 2,
            'director': 3,
            'admin': 4
        }
        
        mi_nivel = jerarquia.get(self.cargo, 0)
        otro_nivel = jerarquia.get(otro_perfil.cargo, 0)
        
        return mi_nivel > otro_nivel

    @property
    def nivel_acceso(self):
        """Retorna el nivel de acceso numérico"""
        niveles = {
            'empleado': 1,
            'supervisor': 2,
            'gerente': 3,
            'director': 4,
            'admin': 5
        }
        return niveles.get(self.cargo, 1)

    @property
    def nombre_completo(self):
        """Retorna el nombre completo del usuario"""
        return self.user.get_full_name() or self.user.username
    
    @property
    def rut_formateado(self):
        """Retorna el RUT en formato legible"""
        return self.rut

    def get_permisos_disponibles(self):
        """Retorna una lista de permisos basados en el cargo"""
        permisos_base = ['ver_perfil', 'editar_perfil']
        
        if self.es_supervisor_o_superior():
            permisos_base.extend(['ver_empleados', 'asignar_tareas'])
        
        if self.es_gerente_o_superior():
            permisos_base.extend(['ver_reportes', 'gestionar_empleados'])
        
        if self.es_director_o_superior():
            permisos_base.extend(['ver_finanzas', 'aprobar_gastos'])
        
        if self.es_admin():
            permisos_base.extend(['gestionar_sistema', 'ver_logs', 'backup_db'])
        
        return permisos_base

class ConfiguracionUsuario(models.Model):
    """Configuraciones y herramientas personales de cada usuario"""
    
    TEMA_CHOICES = [
        ('light', 'Claro'),
        ('dark', 'Oscuro'),
        ('auto', 'Automático'),
    ]
    
    TAMANO_FUENTE_CHOICES = [
        ('small', 'Pequeño'),
        ('medium', 'Mediano'),
        ('large', 'Grande'),
    ]
    
    IDIOMA_CHOICES = [
        ('es', 'Español'),
        ('en', 'English'),
    ]
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='configuracion',
        verbose_name="Usuario"
    )
    
    # Apariencia
    tema = models.CharField(
        max_length=10,
        choices=TEMA_CHOICES,
        default='light',
        verbose_name="Tema"
    )
    tamano_fuente = models.CharField(
        max_length=10,
        choices=TAMANO_FUENTE_CHOICES,
        default='medium',
        verbose_name="Tamaño de Fuente"
    )
    idioma = models.CharField(
        max_length=5,
        choices=IDIOMA_CHOICES,
        default='es',
        verbose_name="Idioma"
    )
    
    # Notificaciones
    notificaciones_email = models.BooleanField(
        default=True,
        verbose_name="Recibir notificaciones por email"
    )
    notificaciones_sistema = models.BooleanField(
        default=True,
        verbose_name="Mostrar notificaciones en el sistema"
    )
    
    # Herramientas habilitadas (cada usuario puede activar/desactivar)
    herramienta_calculadora = models.BooleanField(
        default=True,
        verbose_name="Calculadora"
    )
    herramienta_notas = models.BooleanField(
        default=True,
        verbose_name="Bloc de Notas"
    )
    herramienta_recordatorios = models.BooleanField(
        default=True,
        verbose_name="Recordatorios"
    )
    herramienta_conversor = models.BooleanField(
        default=True,
        verbose_name="Conversor de Unidades"
    )
    
    # Preferencias de visualización
    mostrar_tutorial = models.BooleanField(
        default=True,
        verbose_name="Mostrar tutorial inicial"
    )
    compactar_sidebar = models.BooleanField(
        default=False,
        verbose_name="Sidebar compacta por defecto"
    )
    items_por_pagina = models.IntegerField(
        default=15,
        verbose_name="Items por página"
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Configuración de Usuario"
        verbose_name_plural = "Configuraciones de Usuarios"
    
    def __str__(self):
        return f"Configuración de {self.user.username}"
    
    @classmethod
    def obtener_o_crear(cls, user):
        """Obtiene o crea la configuración para un usuario"""
        config, created = cls.objects.get_or_create(user=user)
        return config