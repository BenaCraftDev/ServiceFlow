from django import forms
from .models import PrestamoMaterial, Material
from django.core.exceptions import ValidationError


class PrestamoForm(forms.ModelForm):
    """Formulario simple para préstamos"""
    
    class Meta:
        model = PrestamoMaterial
        fields = ['material', 'prestado_a', 'fecha_devolucion', 'observaciones']
        widgets = {
            'material': forms.Select(attrs={
                'class': 'form-control',
            }),
            'prestado_a': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre de persona/empresa'
            }),
            'fecha_devolucion': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Observaciones (opcional)'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Solo materiales activos y NO prestados
        if not self.instance.pk:  # Solo al crear
            self.fields['material'].queryset = Material.objects.filter(
                activo=True,
                prestamo_actual__isnull=True  # Sin préstamo actual
            )
        else:  # Al editar, no cambiar material
            self.fields['material'].disabled = True
        
        self.fields['observaciones'].required = False
    
    def clean_material(self):
        material = self.cleaned_data.get('material')
        
        # Validar que no esté prestado (solo al crear)
        if not self.instance.pk and material and material.esta_prestado():
            raise ValidationError(
                f'El material {material.codigo} ya está en préstamo'
            )
        
        return material






