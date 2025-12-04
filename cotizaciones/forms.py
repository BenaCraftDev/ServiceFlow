from django import forms
from django.core.exceptions import ValidationError
from .models import CategoriaEmpleado
from home.models import PerfilEmpleado
from .models import *
from .utils_mantenimiento import calcular_dias_alerta
import math


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombre', 'rut', 'direccion', 'telefono', 'email']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del cliente'
            }),
            'rut': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '12.345.678-9'
            }),
            'direccion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Dirección completa'
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+56 9 1234 5678'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'cliente@email.com'
            }),
        }

class ServicioBaseForm(forms.ModelForm):
    class Meta:
        model = ServicioBase
        fields = ['categoria', 'nombre', 'descripcion', 'precio_base', 'unidad', 'es_parametrizable', 'activo']
        widgets = {
            'categoria': forms.Select(attrs={'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del servicio'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Descripción detallada del servicio'
            }),
            'precio_base': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'unidad': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'UND, MT, KG, etc.'
            }),
            'es_parametrizable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

class ParametroServicioForm(forms.ModelForm):
    class Meta:
        model = ParametroServicio
        fields = ['nombre', 'tipo', 'requerido', 'opciones', 'valor_por_defecto', 'orden']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del parámetro'
            }),
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'requerido': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'opciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Para tipo select: opción1,opción2,opción3'
            }),
            'valor_por_defecto': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Valor por defecto (opcional)'
            }),
            'orden': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            })
        }

class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ['codigo', 'nombre', 'descripcion', 'precio_unitario', 'unidad', 'categoria', 'activo',
                  'requiere_mantenimiento', 'dias_entre_mantenimiento', 'fecha_ultimo_mantenimiento', 'dias_alerta_previa']
        widgets = {
            'codigo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Código único del material'
            }),
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del material'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descripción detallada'
            }),
            'precio_unitario': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'unidad': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'UND, MT, KG, etc.'
            }),
            'categoria': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Categoría del material'
            }),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'requiere_mantenimiento': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'id_requiere_mantenimiento'
            }),
            'dias_entre_mantenimiento': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': 'Ej: 30, 60, 90, 180...',
                'id': 'id_dias_entre_mantenimiento'
            }),
            'fecha_ultimo_mantenimiento': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'dias_alerta_previa': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': 'Se calcula automáticamente (puede modificarse)',
                'id': 'id_dias_alerta_previa'
            })
        }
        help_texts = {
            'dias_alerta_previa': 'Se calcula automáticamente. Puede modificarlo si lo desea.'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Si es un material nuevo Y tiene dias_entre_mantenimiento en los datos
        if not self.instance.pk and 'dias_entre_mantenimiento' in self.data:
            try:
                dias_entre = int(self.data.get('dias_entre_mantenimiento'))
                if dias_entre > 0:
                    # Calcular días de alerta automáticamente
                    dias_alerta_auto = calcular_dias_alerta(dias_entre)
                    
                    # Si no se especificó dias_alerta_previa, usar el calculado
                    if 'dias_alerta_previa' not in self.data or not self.data.get('dias_alerta_previa'):
                        self.initial['dias_alerta_previa'] = dias_alerta_auto
            except (ValueError, TypeError):
                pass
        
        # Si es edición y el material no tiene dias_alerta_previa configurado
        elif self.instance.pk and self.instance.dias_entre_mantenimiento:
            if not self.instance.dias_alerta_previa or self.instance.dias_alerta_previa == 0:
                # Sugerir el valor calculado automáticamente
                dias_alerta_auto = calcular_dias_alerta(self.instance.dias_entre_mantenimiento)
                self.fields['dias_alerta_previa'].help_text = f'Valor sugerido automáticamente: {dias_alerta_auto} días'
                self.fields['dias_alerta_previa'].widget.attrs['placeholder'] = f'Sugerido: {dias_alerta_auto} días'


class TipoTrabajoForm(forms.ModelForm):
    class Meta:
        model = TipoTrabajo
        fields = ['nombre', 'descripcion', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del tipo de trabajo'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descripción del tipo de trabajo'
            }),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

class CategoriaServicioForm(forms.ModelForm):
    class Meta:
        model = CategoriaServicio
        fields = ['nombre', 'descripcion', 'orden', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre de la categoría'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descripción de la categoría'
            }),
            'orden': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

class PlantillaCotizacionForm(forms.ModelForm):
    class Meta:
        model = PlantillaCotizacion
        fields = ['nombre', 'tipo_trabajo', 'descripcion', 'activa']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre de la plantilla'
            }),
            'tipo_trabajo': forms.Select(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descripción de la plantilla'
            }),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

class ConfiguracionEmpresaForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionEmpresa
        fields = ['nombre', 'descripcion', 'direccion', 'telefono', 'email', 'logo']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre de la empresa'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Descripción de servicios'
            }),
            'direccion': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Dirección completa'
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Teléfono de contacto'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@empresa.com'
            }),
            'logo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            })
        }

# Formsets para manejar múltiples items
from django.forms import inlineformset_factory

ParametroServicioFormSet = inlineformset_factory(
    ServicioBase,
    ParametroServicio,
    form=ParametroServicioForm,
    extra=1,
    can_delete=True,
    fields=['nombre', 'tipo', 'requerido', 'opciones', 'valor_por_defecto', 'orden']
)

ItemPlantillaServicioFormSet = inlineformset_factory(
    PlantillaCotizacion,
    ItemPlantillaServicio,
    fields=['servicio', 'cantidad_default', 'orden'],
    extra=1,
    can_delete=True,
    widgets={
        'servicio': forms.Select(attrs={'class': 'form-control'}),
        'cantidad_default': forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0'
        }),
        'orden': forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0'
        })
    }
)

class CotizacionForm(forms.ModelForm):
    class Meta:
        model = Cotizacion
        fields = ['cliente', 'representante', 'tipo_trabajo', 'referencia', 'lugar', 
                  'fecha_vencimiento', 'observaciones']
        widgets = {
            'cliente': forms.Select(attrs={
                'class': 'form-control', 
                'required': True,
                'id': 'id_cliente'
            }),
            'representante': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_representante'
            }),
            'tipo_trabajo': forms.Select(attrs={
                'class': 'form-control', 
                'required': True
            }),
            'referencia': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3, 
                'required': True
            }),
            'lugar': forms.TextInput(attrs={
                'class': 'form-control', 
                'required': True
            }),
            'fecha_vencimiento': forms.DateInput(attrs={
                'class': 'form-control', 
                'type': 'date'
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 4
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Configurar queryset inicial para representante
        self.fields['representante'].queryset = RepresentanteCliente.objects.none()
        self.fields['representante'].required = False
        
        # Si hay una instancia existente con cliente
        if self.instance.pk and self.instance.cliente:
            self.fields['representante'].queryset = RepresentanteCliente.objects.filter(
                cliente=self.instance.cliente
            ).order_by('orden', 'nombre')
        
        # Si se está enviando el formulario con un cliente
        elif 'cliente' in self.data:
            try:
                cliente_id = int(self.data.get('cliente'))
                self.fields['representante'].queryset = RepresentanteCliente.objects.filter(
                    cliente_id=cliente_id
                ).order_by('orden', 'nombre')
            except (ValueError, TypeError):
                pass

# Formulario para gestión rápida de empleados en cotizaciones
class AsignacionEmpleadoForm(forms.Form):
    """Formulario para asignar empleados a trabajos"""
    
    categoria = forms.ModelChoiceField(
        queryset=CategoriaEmpleado.objects.filter(activo=True),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Filtrar por categoría",
        required=False
    )
    
    empleado = forms.ModelChoiceField(
        queryset=PerfilEmpleado.objects.filter(activo=True, cargo='empleado'),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Seleccionar empleado"
    )
    
    horas_asignadas = forms.DecimalField(
        max_digits=8,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.5',
            'min': '0'
        })
    )
    
    def __init__(self, *args, categoria_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        if categoria_id:
            # Filtrar empleados por categoría
            self.fields['empleado'].queryset = PerfilEmpleado.objects.filter(
                activo=True,
                cargo='empleado',
                categorias_trabajo__categoria_id=categoria_id,
                categorias_trabajo__activo=True
            ).distinct()
        
        # Personalizar labels
        self.fields['empleado'].label_from_instance = lambda obj: f"{obj.nombre_completo} - {obj.departamento or 'Sin dept.'}"