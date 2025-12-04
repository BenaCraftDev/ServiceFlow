# cotizaciones/forms_empleados.py
from django import forms
from django.contrib.auth.models import User
from home.models import PerfilEmpleado
from .models import CategoriaEmpleado, EmpleadoCategoria, ItemManoObraEmpleado, TrabajoEmpleado

class CategoriaEmpleadoForm(forms.ModelForm):
    class Meta:
        model = CategoriaEmpleado
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
                'min': 0
            }),
            'activo': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }

class AsignarEmpleadoCategoriaForm(forms.ModelForm):
    empleado = forms.ModelChoiceField(
        queryset=PerfilEmpleado.objects.filter(
            activo=True,
            cargo='empleado'
        ).select_related('user'),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Seleccionar empleado"
    )
    
    categoria = forms.ModelChoiceField(
        queryset=CategoriaEmpleado.objects.filter(activo=True),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Seleccionar categoría"
    )

    class Meta:
        model = EmpleadoCategoria
        fields = ['empleado', 'categoria', 'activo']
        widgets = {
            'activo': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Personalizar la representación de empleados
        self.fields['empleado'].queryset = PerfilEmpleado.objects.filter(
            activo=True,
            cargo='empleado'
        ).select_related('user').order_by('user__first_name', 'user__last_name')

class ItemManoObraEmpleadoForm(forms.ModelForm):
    empleado = forms.ModelChoiceField(
        queryset=PerfilEmpleado.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Seleccionar empleado"
    )

    class Meta:
        model = ItemManoObraEmpleado
        fields = ['empleado', 'horas_asignadas', 'observaciones']
        widgets = {
            'horas_asignadas': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.5',
                'min': '0'
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Observaciones adicionales'
            })
        }

    def __init__(self, *args, categoria_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        if categoria_id:
            # Filtrar empleados por categoría
            self.fields['empleado'].queryset = PerfilEmpleado.objects.filter(
                activo=True,
                cargo='empleado',
                categorias_trabajo__categoria_id=categoria_id,
                categorias_trabajo__activo=True
            ).select_related('user').distinct()
        else:
            # Mostrar todos los empleados activos
            self.fields['empleado'].queryset = PerfilEmpleado.objects.filter(
                activo=True,
                cargo='empleado'
            ).select_related('user')

class TrabajoEmpleadoForm(forms.ModelForm):
    class Meta:
        model = TrabajoEmpleado
        fields = ['estado', 'fecha_inicio', 'fecha_fin', 'horas_trabajadas', 'observaciones_empleado']
        widgets = {
            'estado': forms.Select(attrs={'class': 'form-control'}),
            'fecha_inicio': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'fecha_fin': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'horas_trabajadas': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.5',
                'min': '0'
            }),
            'observaciones_empleado': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Observaciones del trabajo realizado'
            })
        }