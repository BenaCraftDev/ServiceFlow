from django import template
from django.utils.safestring import mark_safe
import locale

register = template.Library()

@register.filter
def formato_miles(valor):
    """
    Formatea un número con separador de miles estilo chileno
    Ejemplo: 250000 -> 250.000
    """
    try:
        if valor is None or valor == '':
            return '0'
        
        # Convertir a entero
        numero = int(float(valor))
        
        # Formatear con separador de miles
        return f"{numero:,}".replace(',', '.')
        
    except (ValueError, TypeError):
        return valor

@register.filter
def formato_precio(valor):
    """
    Formatea un número como precio chileno
    Ejemplo: 250000 -> $250.000
    """
    try:
        if valor is None or valor == '':
            return '$0'
        
        numero = int(float(valor))
        numero_formateado = f"{numero:,}".replace(',', '.')
        return mark_safe(f'${numero_formateado}')
        
    except (ValueError, TypeError):
        return f'${valor}'