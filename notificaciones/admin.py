from django.contrib import admin
from .models import Notificacion
from .models import NotaCalendario

@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'usuario', 'tipo', 'leida', 'fecha_creacion']
    list_filter = ['tipo', 'leida', 'fecha_creacion']
    search_fields = ['titulo', 'mensaje', 'usuario__username']
    date_hierarchy = 'fecha_creacion'
    
    actions = ['marcar_como_leidas', 'marcar_como_no_leidas']
    
    def marcar_como_leidas(self, request, queryset):
        queryset.update(leida=True)
    marcar_como_leidas.short_description = "Marcar como leídas"
    
    def marcar_como_no_leidas(self, request, queryset):
        queryset.update(leida=False)
    marcar_como_no_leidas.short_description = "Marcar como no leídas"

@admin.register(NotaCalendario)
class NotaCalendarioAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'usuario', 'fecha', 'prioridad', 'color_badge', 'es_urgente_badge', 'fecha_creacion']
    list_filter = ['prioridad', 'fecha', 'usuario', 'fecha_creacion']
    search_fields = ['titulo', 'descripcion', 'usuario__username', 'usuario__first_name', 'usuario__last_name']
    date_hierarchy = 'fecha'
    readonly_fields = ['fecha_creacion', 'fecha_modificacion', 'es_pasado', 'es_hoy', 'es_urgente']
    
    fieldsets = [
        ('Información Básica', {
            'fields': ['usuario', 'titulo', 'descripcion']
        }),
        ('Fecha y Prioridad', {
            'fields': ['fecha', 'prioridad', 'color']
        }),
        ('Información del Sistema', {
            'fields': ['fecha_creacion', 'fecha_modificacion'],
            'classes': ['collapse']
        }),
        ('Estado', {
            'fields': ['es_pasado', 'es_hoy', 'es_urgente'],
            'classes': ['collapse']
        }),
    ]
    
    def color_badge(self, obj):
        """Muestra el color como un badge en el admin"""
        from django.utils.html import format_html
        return format_html(
            '<span style="display: inline-block; width: 20px; height: 20px; '
            'background-color: {}; border-radius: 50%; border: 1px solid #ccc;"></span>',
            obj.color
        )
    color_badge.short_description = 'Color'
    
    def es_urgente_badge(self, obj):
        """Muestra si es urgente como badge"""
        from django.utils.html import format_html
        if obj.es_urgente:
            return format_html('<span style="color: red; font-weight: bold;">⚠️ URGENTE</span>')
        return '—'
    es_urgente_badge.short_description = 'Urgente'
    es_urgente_badge.boolean = False
    
    def get_queryset(self, request):
        """Optimiza las consultas"""
        return super().get_queryset(request).select_related('usuario')
    
    def save_model(self, request, obj, form, change):
        """Si se crea una nota desde el admin, asignar el usuario actual si no tiene"""
        if not change and not obj.usuario:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)

# ACCIONES PERSONALIZADAS
@admin.action(description='Marcar notas seleccionadas como alta prioridad')
def marcar_alta_prioridad(modeladmin, request, queryset):
    """Acción para marcar notas como alta prioridad"""
    queryset.update(prioridad='alta')

@admin.action(description='Marcar notas seleccionadas como baja prioridad')
def marcar_baja_prioridad(modeladmin, request, queryset):
    """Acción para marcar notas como baja prioridad"""
    queryset.update(prioridad='baja')

# Agregar las acciones al admin
NotaCalendarioAdmin.actions = [marcar_alta_prioridad, marcar_baja_prioridad]

