from django.contrib import admin
from .models import Notificacion

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