from django.contrib import admin
from .models import (
    Cliente, RepresentanteCliente, Cotizacion, TipoTrabajo,
    CategoriaServicio, ServicioBase, ParametroServicio,
    Material, ItemServicio, ItemMaterial, ItemManoObra,
    PlantillaCotizacion, ItemPlantillaServicio, ParametroItemServicio,
    CategoriaEmpleado, EmpleadoCategoria, ItemManoObraEmpleado,
    TrabajoEmpleado, PrestamoMaterial, HistorialPrestamo,
    EvidenciaTrabajo, GastoTrabajo
)

# Registros básicos
admin.site.register(Cliente)
admin.site.register(RepresentanteCliente)
admin.site.register(TipoTrabajo)
admin.site.register(CategoriaServicio)
admin.site.register(ServicioBase)
admin.site.register(ParametroServicio)
admin.site.register(Material)
admin.site.register(PlantillaCotizacion)
admin.site.register(ItemPlantillaServicio)
admin.site.register(CategoriaEmpleado)
admin.site.register(EmpleadoCategoria)
admin.site.register(ItemManoObraEmpleado)
admin.site.register(TrabajoEmpleado)
admin.site.register(PrestamoMaterial)
admin.site.register(HistorialPrestamo)

# Admin personalizado para Cotización
@admin.register(Cotizacion)
class CotizacionAdmin(admin.ModelAdmin):
    list_display = ('numero', 'cliente', 'estado', 'fecha_creacion', 'valor_total')
    list_filter = ('estado', 'fecha_creacion')
    search_fields = ('numero', 'cliente__nombre')
    date_hierarchy = 'fecha_creacion'

# Admin para items
@admin.register(ItemServicio)
class ItemServicioAdmin(admin.ModelAdmin):
    list_display = ('cotizacion', 'servicio', 'cantidad', 'precio_unitario', 'subtotal')
    list_filter = ('cotizacion__estado',)
    search_fields = ('cotizacion__numero', 'servicio__nombre')

@admin.register(ItemMaterial)
class ItemMaterialAdmin(admin.ModelAdmin):
    list_display = ('cotizacion', 'material', 'cantidad', 'precio_unitario', 'subtotal')
    list_filter = ('cotizacion__estado',)
    search_fields = ('cotizacion__numero', 'material__nombre')

@admin.register(ItemManoObra)
class ItemManoObraAdmin(admin.ModelAdmin):
    list_display = ('cotizacion', 'descripcion_corta', 'horas', 'precio_hora', 'subtotal')
    list_filter = ('cotizacion__estado',)
    search_fields = ('cotizacion__numero', 'descripcion')
    
    def descripcion_corta(self, obj):
        return obj.descripcion[:50] + '...' if len(obj.descripcion) > 50 else obj.descripcion
    descripcion_corta.short_description = 'Descripción'

@admin.register(ParametroItemServicio)
class ParametroItemServicioAdmin(admin.ModelAdmin):
    list_display = ('item_servicio', 'parametro', 'valor')
    list_filter = ('parametro__tipo',)

# Admin para EvidenciaTrabajo
@admin.register(EvidenciaTrabajo)
class EvidenciaTrabajoAdmin(admin.ModelAdmin):
    list_display = ('id', 'trabajo', 'descripcion_corta', 'fecha_subida')
    list_filter = ('fecha_subida',)
    search_fields = ('trabajo__id', 'descripcion')
    date_hierarchy = 'fecha_subida'
    readonly_fields = ('fecha_subida',)
    
    def descripcion_corta(self, obj):
        if obj.descripcion:
            return obj.descripcion[:50] + '...' if len(obj.descripcion) > 50 else obj.descripcion
        return '(Sin descripción)'
    descripcion_corta.short_description = 'Descripción'

# Admin para GastoTrabajo
@admin.register(GastoTrabajo)
class GastoTrabajoAdmin(admin.ModelAdmin):
    list_display = ('id', 'trabajo', 'materiales', 'transporte', 'otros', 'total_gastos', 'fecha_actualizacion')
    list_filter = ('fecha_creacion', 'fecha_actualizacion')
    search_fields = ('trabajo__id', 'materiales_detalle', 'transporte_detalle', 'otros_detalle')
    date_hierarchy = 'fecha_creacion'
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion')
    
    fieldsets = (
        ('Trabajo', {
            'fields': ('trabajo',)
        }),
        ('Materiales', {
            'fields': ('materiales', 'materiales_detalle')
        }),
        ('Transporte', {
            'fields': ('transporte', 'transporte_detalle')
        }),
        ('Otros Gastos', {
            'fields': ('otros', 'otros_detalle')
        }),
        ('Metadata', {
            'fields': ('fecha_creacion', 'fecha_actualizacion'),
            'classes': ('collapse',)
        })
    )
    
    def total_gastos(self, obj):
        return f'${obj.total:,.2f}'
    total_gastos.short_description = 'Total'