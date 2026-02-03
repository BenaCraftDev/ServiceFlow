import json
import csv
from decimal import Decimal
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from django.template.loader import render_to_string
from django.conf import settings
from ..models import *
from ..forms import *
from ..forms_empleados import *
from ..forms_prestamos import *
from home.decorators import requiere_admin, requiere_gerente_o_superior
from notificaciones.models import Notificacion
from notificaciones.utils import crear_notificacion
from home.models import PerfilEmpleado
from ..utils_mantenimiento import verificar_mantenimientos_materiales

# === Crud Materiales === 

@login_required
@requiere_gerente_o_superior
def gestionar_materiales(request):
    verificar_mantenimientos_materiales(request)
    print(verificar_mantenimientos_materiales(request))
    """Gestión de materiales"""
    
    # Código original de la vista
    materiales = Material.objects.select_related('categoria', 'unidad').all().order_by('categoria__nombre', 'nombre')
    
    busqueda = request.GET.get('busqueda', '')
    categoria_filtro = request.GET.get('categoria', '')
    
    if busqueda:
        materiales = materiales.filter(
            Q(nombre__icontains=busqueda) |
            Q(codigo__icontains=busqueda) |
            Q(descripcion__icontains=busqueda)
        )
    
    if categoria_filtro:
        materiales = materiales.filter(categoria_id=categoria_filtro)
    
    categorias = CategoriaMaterial.objects.filter(activo=True).order_by('orden', 'nombre')
    unidades = UnidadMaterial.objects.filter(activo=True).order_by('orden', 'abreviatura')
    
    # Estadísticas
    materiales_activos = materiales.filter(activo=True).count()
    precio_promedio = materiales.aggregate(promedio=models.Avg('precio_unitario'))['promedio'] or 0
    
    paginator = Paginator(materiales, 20)
    page = request.GET.get('page')
    materiales = paginator.get_page(page)
    
    return render(request, 'cotizaciones/gestionar_materiales.html', {
        'materiales': materiales,
        'categorias': categorias,
        'unidades': unidades,
        'busqueda': busqueda,
        'categoria_filtro': categoria_filtro,
        'materiales_activos': materiales_activos,
        'precio_promedio': precio_promedio,
    })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def crear_material(request):
    """Crear nuevo material vía AJAX"""
    try:
        data = json.loads(request.body)
        
        # Procesar fecha de último mantenimiento si viene
        fecha_ultimo_mantenimiento = None
        if data.get('fecha_ultimo_mantenimiento'):
            try:
                from datetime import datetime
                fecha_ultimo_mantenimiento = datetime.strptime(
                    data.get('fecha_ultimo_mantenimiento'), 
                    '%Y-%m-%d'
                ).date()
            except:
                pass
        
        # Obtener categoría si viene
        categoria = None
        if data.get('categoria'):
            try:
                categoria = CategoriaMaterial.objects.get(pk=data.get('categoria'))
            except CategoriaMaterial.DoesNotExist:
                pass
        
        # Obtener unidad si viene
        unidad = None
        if data.get('unidad'):
            try:
                unidad = UnidadMaterial.objects.get(pk=data.get('unidad'))
            except UnidadMaterial.DoesNotExist:
                pass
        
        material = Material.objects.create(
            codigo=data.get('codigo'),
            nombre=data.get('nombre'),
            descripcion=data.get('descripcion', ''),
            precio_unitario=data.get('precio_unitario'),
            unidad=unidad,
            categoria=categoria,
            activo=data.get('activo', True),
            
            # Campos de mantenimiento
            requiere_mantenimiento=data.get('requiere_mantenimiento', False),
            
            # ⏱️ NUEVO: Tipo de mantenimiento
            tipo_mantenimiento=data.get('tipo_mantenimiento', 'dias'),
            
            # Campos para mantenimiento por DÍAS
            dias_entre_mantenimiento=data.get('dias_entre_mantenimiento') or None,
            dias_alerta_previa=data.get('dias_alerta_previa', 7),
            fecha_ultimo_mantenimiento=fecha_ultimo_mantenimiento,
            
            # ⏱️ NUEVO: Campos para mantenimiento por HORAS
            horas_entre_mantenimiento=data.get('horas_entre_mantenimiento') or None,
            horas_alerta_previa=data.get('horas_alerta_previa', 10),
            horas_uso_acumuladas=data.get('horas_uso_acumuladas', 0),
        )
        
        return JsonResponse({
            'success': True,
            'material_id': material.id,
            'message': 'Material creado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["GET"])
def obtener_material(request, material_id):
    """Obtener datos de un material vía AJAX"""
    try:
        material = get_object_or_404(Material, pk=material_id)
        
        return JsonResponse({
            'success': True,
            'material': {
                'id': material.id,
                'codigo': material.codigo,
                'nombre': material.nombre,
                'descripcion': material.descripcion or '',
                'precio_unitario': float(material.precio_unitario),
                'unidad': material.unidad.id if material.unidad else '',
                'categoria': material.categoria.id if material.categoria else '',
                'activo': material.activo,
                'requiere_mantenimiento': material.requiere_mantenimiento,
                
                # ⏱️ NUEVO: Tipo de mantenimiento
                'tipo_mantenimiento': material.tipo_mantenimiento,
                
                # Campos DÍAS
                'dias_entre_mantenimiento': material.dias_entre_mantenimiento,
                'dias_alerta_previa': material.dias_alerta_previa,
                'fecha_ultimo_mantenimiento': material.fecha_ultimo_mantenimiento.isoformat() if material.fecha_ultimo_mantenimiento else None,
                
                # ⏱️ NUEVO: Campos HORAS
                'horas_entre_mantenimiento': material.horas_entre_mantenimiento,
                'horas_alerta_previa': material.horas_alerta_previa,
                'horas_uso_acumuladas': float(material.horas_uso_acumuladas),
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["PUT"])
def editar_material(request, material_id):
    """Editar material existente vía AJAX"""
    try:
        material = get_object_or_404(Material, pk=material_id)
        data = json.loads(request.body)
        
        material.codigo = data.get('codigo', material.codigo)
        material.nombre = data.get('nombre', material.nombre)
        material.descripcion = data.get('descripcion', material.descripcion)
        material.precio_unitario = data.get('precio_unitario', material.precio_unitario)
        
        # Actualizar unidad
        if data.get('unidad'):
            try:
                material.unidad = UnidadMaterial.objects.get(pk=data.get('unidad'))
            except UnidadMaterial.DoesNotExist:
                material.unidad = None
        else:
            material.unidad = None
        
        # Actualizar categoría
        if data.get('categoria'):
            try:
                material.categoria = CategoriaMaterial.objects.get(pk=data.get('categoria'))
            except CategoriaMaterial.DoesNotExist:
                material.categoria = None
        else:
            material.categoria = None
        
        material.activo = data.get('activo', material.activo)
        
        # Campos de mantenimiento
        material.requiere_mantenimiento = data.get('requiere_mantenimiento', False)
        
        # ⏱️ NUEVO: Tipo de mantenimiento
        material.tipo_mantenimiento = data.get('tipo_mantenimiento', 'dias')
        
        if material.requiere_mantenimiento:
            # Campos para DÍAS
            material.dias_entre_mantenimiento = data.get('dias_entre_mantenimiento') or None
            material.dias_alerta_previa = data.get('dias_alerta_previa', 7)
            
            # Procesar fecha de último mantenimiento
            fecha_str = data.get('fecha_ultimo_mantenimiento')
            if fecha_str:
                try:
                    from datetime import datetime
                    material.fecha_ultimo_mantenimiento = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                except:
                    pass
            else:
                if not material.fecha_ultimo_mantenimiento:
                    material.fecha_ultimo_mantenimiento = None
            
            # ⏱️ NUEVO: Campos para HORAS
            material.horas_entre_mantenimiento = data.get('horas_entre_mantenimiento') or None
            material.horas_alerta_previa = data.get('horas_alerta_previa', 10)
            material.horas_uso_acumuladas = data.get('horas_uso_acumuladas', 0)
        else:
            # Si se desmarca, limpiar todos los campos
            material.dias_entre_mantenimiento = None
            material.dias_alerta_previa = 7
            material.fecha_ultimo_mantenimiento = None
            material.horas_entre_mantenimiento = None
            material.horas_alerta_previa = 10
            material.horas_uso_acumuladas = 0
        
        material.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Material actualizado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["DELETE"])
def eliminar_material(request, material_id):
    try:
        material = get_object_or_404(Material, pk=material_id)
        nombre_material = material.nombre
        material.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Material {nombre_material} eliminado exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
def validar_codigo_material(request):
    """Validar si un código de material está disponible"""
    codigo = request.GET.get('codigo', '')
    existe = Material.objects.filter(codigo=codigo).exists()
    
    return JsonResponse({
        'disponible': not existe,
        'codigo': codigo
    })

@login_required
@requiere_admin
@require_http_methods(["POST"])
def registrar_mantenimiento_material(request, material_id):
    """Registra que se realizó el mantenimiento de un material"""
    try:
        material = get_object_or_404(Material, pk=material_id)
        
        if not material.requiere_mantenimiento:
            return JsonResponse({
                'success': False,
                'error': 'Este material no requiere mantenimiento'
            })
        
        # ⏱️ MANEJO SEGÚN TIPO DE MANTENIMIENTO
        if material.tipo_mantenimiento == 'horas':
            # Para mantenimiento por HORAS: Reiniciar contador
            material.horas_uso_acumuladas = 0
            mensaje_notificacion = f'Se ha registrado exitosamente el mantenimiento del material "{material.nombre}". El contador de horas se ha reiniciado a 0. Próximo mantenimiento en {material.horas_entre_mantenimiento} horas de uso.'
            nueva_fecha_texto = f'Contador reiniciado a 0 horas'
            
        else:
            # Para mantenimiento por DÍAS: Actualizar fecha
            material.fecha_ultimo_mantenimiento = timezone.now().date()
            mensaje_notificacion = f'Se ha registrado exitosamente el mantenimiento del material "{material.nombre}". Próximo mantenimiento en {material.dias_entre_mantenimiento} días.'
            nueva_fecha_texto = material.fecha_ultimo_mantenimiento.strftime('%d/%m/%Y')
        
        material.save()
        
        # Crear notificación de confirmación para el usuario
        crear_notificacion(
            usuario=request.user,
            titulo=f'✓ Mantenimiento registrado: {material.codigo}',
            mensaje=mensaje_notificacion,
            tipo='success',
            url=f'/cotizaciones/materiales/?buscar={material.codigo}',
            datos_extra={
                'material_id': material.id,
                'material_codigo': material.codigo,
                'tipo_mantenimiento': material.tipo_mantenimiento,
                'fecha_mantenimiento': material.fecha_ultimo_mantenimiento.isoformat() if material.fecha_ultimo_mantenimiento else None,
                'horas_acumuladas': float(material.horas_uso_acumuladas) if material.tipo_mantenimiento == 'horas' else None,
            }
        )
        
        estado = material.get_estado_mantenimiento()
        
        return JsonResponse({
            'success': True,
            'message': f'Mantenimiento registrado para {material.nombre}',
            'nueva_fecha': nueva_fecha_texto,
            'estado_mantenimiento': estado
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
def obtener_alertas_mantenimiento(request):
    """Obtiene lista de materiales que necesitan mantenimiento"""
    try:
        materiales_mantenimiento = Material.objects.filter(
            requiere_mantenimiento=True,
            activo=True,
            fecha_ultimo_mantenimiento__isnull=False,
            dias_entre_mantenimiento__isnull=False
        )
        
        alertas = []
        for material in materiales_mantenimiento:
            dias = material.dias_hasta_proximo_mantenimiento()
            if dias is not None and dias <= material.dias_alerta_previa:
                estado = material.get_estado_mantenimiento()
                alertas.append({
                    'id': material.id,
                    'codigo': material.codigo,
                    'nombre': material.nombre,
                    'categoria': material.categoria,
                    'dias_restantes': dias,
                    'estado': estado,
                    'fecha_ultimo': material.fecha_ultimo_mantenimiento.strftime('%d/%m/%Y') if material.fecha_ultimo_mantenimiento else None,
                })
        
        # Ordenar: vencidos primero, luego por días restantes
        alertas.sort(key=lambda x: (x['dias_restantes'] >= 0, x['dias_restantes']))
        
        return JsonResponse({
            'success': True,
            'alertas': alertas,
            'total': len(alertas)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def importar_materiales_csv(request):
    """Importar materiales desde archivo CSV"""
    try:
        if 'archivo' not in request.FILES:
            return JsonResponse({'success': False, 'error': 'No se encontró archivo'})
        
        archivo = request.FILES['archivo']
        actualizar_existentes = request.POST.get('actualizar_existentes') == 'true'
        
        # Leer archivo CSV
        contenido = archivo.read().decode('utf-8')
        lineas = contenido.strip().split('\n')
        
        if len(lineas) < 2:
            return JsonResponse({'success': False, 'error': 'Archivo CSV vacío o sin datos'})
        
        # Procesar header
        headers = [h.strip().lower() for h in lineas[0].split(',')]
        required_fields = ['codigo', 'nombre', 'precio_unitario']
        
        for field in required_fields:
            if field not in headers:
                return JsonResponse({'success': False, 'error': f'Campo requerido faltante: {field}'})
        
        materiales_creados = 0
        materiales_actualizados = 0
        
        # Procesar datos
        for i, linea in enumerate(lineas[1:], 2):
            try:
                valores = [v.strip().strip('"') for v in linea.split(',')]
                if len(valores) != len(headers):
                    continue
                
                data = dict(zip(headers, valores))
                
                # Validar datos requeridos
                if not data.get('codigo') or not data.get('nombre'):
                    continue
                
                material_data = {
                    'codigo': data['codigo'],
                    'nombre': data['nombre'],
                    'categoria': data.get('categoria', ''),
                    'precio_unitario': float(data['precio_unitario']),
                    'unidad': data.get('unidad', 'UND'),
                    'descripcion': data.get('descripcion', ''),
                    'activo': True
                }
                
                # Verificar si existe
                material_existente = Material.objects.filter(codigo=data['codigo']).first()
                
                if material_existente:
                    if actualizar_existentes:
                        for key, value in material_data.items():
                            setattr(material_existente, key, value)
                        material_existente.save()
                        materiales_actualizados += 1
                else:
                    Material.objects.create(**material_data)
                    materiales_creados += 1
                    
            except (ValueError, IndexError) as e:
                continue  # Saltar líneas con errores
        
        mensaje = f'Importación completada: {materiales_creados} creados'
        if materiales_actualizados:
            mensaje += f', {materiales_actualizados} actualizados'
        
        return JsonResponse({
            'success': True,
            'materiales_creados': materiales_creados,
            'materiales_actualizados': materiales_actualizados,
            'message': mensaje
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

# === Prestamos ===

@login_required
@requiere_gerente_o_superior
def lista_prestamos(request):
    """Lista todos los préstamos activos"""
    
    buscar = request.GET.get('buscar', '').strip()
    
    prestamos = PrestamoMaterial.objects.select_related(
        'material', 'usuario_registro'
    ).all()
    
    if buscar:
        prestamos = prestamos.filter(
            Q(material__codigo__icontains=buscar) |
            Q(material__nombre__icontains=buscar) |
            Q(prestado_a__icontains=buscar)
        )
    
    # Contar estados
    total = prestamos.count()
    vencidos = sum(1 for p in prestamos if p.esta_vencido())
    proximos = sum(1 for p in prestamos if not p.esta_vencido() and p.dias_restantes() <= 3)
    
    # Materiales disponibles = materiales activos
    materiales_disponibles_count = Material.objects.filter(activo=True).count()
    
    # Materiales para el formulario = solo activos
    materiales_disponibles_form = Material.objects.filter(
        activo=True
    ).order_by('codigo')
    
    context = {
        'prestamos': prestamos,
        'total': total,
        'vencidos': vencidos,
        'proximos': proximos,
        'materiales_disponibles': materiales_disponibles_count,
        'materiales_disponibles_form': materiales_disponibles_form,
        'buscar': buscar,
    }
    
    return render(request, 'cotizaciones/prestamos/lista_prestamos.html', context)

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def crear_prestamo(request):
    """Crear préstamo vía AJAX"""
    
    try:
        data = json.loads(request.body)
        
        material = Material.objects.get(pk=data['material_id'])
        
        # Validar que esté activo (disponible)
        if not material.activo:
            return JsonResponse({
                'success': False,
                'error': f'El material {material.codigo} no está disponible (inactivo o prestado)'
            })
        
        # Crear préstamo (automáticamente marca material como inactivo)
        prestamo = PrestamoMaterial.objects.create(
            material=material,
            prestado_a=data['prestado_a'],
            fecha_devolucion=data['fecha_devolucion'],
            observaciones=data.get('observaciones', ''),
            usuario_registro=request.user
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Préstamo creado: {material.codigo} - {data["prestado_a"]}'
        })
        
    except Material.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Material no encontrado'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
def obtener_datos_prestamo(request, pk):
    """Obtener datos de un préstamo para edición"""
    
    prestamo = get_object_or_404(PrestamoMaterial, pk=pk)
    
    return JsonResponse({
        'success': True,
        'prestamo': {
            'id': prestamo.id,
            'material_id': prestamo.material.id,
            'material_codigo': prestamo.material.codigo,
            'material_nombre': prestamo.material.nombre,
            'prestado_a': prestamo.prestado_a,
            'fecha_devolucion': prestamo.fecha_devolucion.strftime('%Y-%m-%d'),
            'observaciones': prestamo.observaciones or ''
        }
    })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["PUT"])
def editar_prestamo(request, pk):
    """Editar préstamo vía AJAX"""
    
    try:
        prestamo = get_object_or_404(PrestamoMaterial, pk=pk)
        data = json.loads(request.body)
        
        # Actualizar datos (NO se puede cambiar el material)
        prestamo.prestado_a = data['prestado_a']
        prestamo.fecha_devolucion = data['fecha_devolucion']
        prestamo.observaciones = data.get('observaciones', '')
        prestamo.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Préstamo actualizado correctamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["DELETE"])
def eliminar_prestamo(request, pk):
    """Eliminar/Devolver préstamo vía AJAX"""
    
    try:
        from django.utils import timezone
        from ..models import HistorialPrestamo
        
        prestamo = get_object_or_404(PrestamoMaterial, pk=pk)
        material_codigo = prestamo.material.codigo
        
        # Guardar en historial ANTES de eliminar
        HistorialPrestamo.objects.create(
            material_codigo=prestamo.material.codigo,
            material_nombre=prestamo.material.nombre,
            prestado_a=prestamo.prestado_a,
            fecha_prestamo=prestamo.fecha_prestamo,
            fecha_devolucion=prestamo.fecha_devolucion,
            fecha_devuelto=timezone.now().date(),
            observaciones=prestamo.observaciones,
            usuario_registro=prestamo.usuario_registro
        )
        
        # Marcar material como activo
        material = prestamo.material
        material.activo = True
        material.save()
        
        # Eliminar préstamo
        prestamo.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Material devuelto: {material_codigo}'
        })
        
    except PrestamoMaterial.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Préstamo no encontrado'
        }, status=404)
    except Exception as e:
        import traceback
        print(f"ERROR en eliminar_prestamo: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def verificar_material_disponible(request):
    """Verifica si un material está disponible (activo)"""
    
    material_id = request.GET.get('material_id')
    
    if not material_id:
        return JsonResponse({'disponible': True})
    
    try:
        material = Material.objects.get(pk=material_id)
        
        if not material.activo:
            # Si no está activo, verificar si es por préstamo
            if hasattr(material, 'prestamo_actual'):
                prestamo = material.prestamo_actual
                return JsonResponse({
                    'disponible': False,
                    'mensaje': f'Material en préstamo hasta el {prestamo.fecha_devolucion.strftime("%d/%m/%Y")}',
                    'prestado_a': prestamo.prestado_a
                })
            else:
                return JsonResponse({
                    'disponible': False,
                    'mensaje': 'Material no disponible (inactivo)'
                })
        
        return JsonResponse({
            'disponible': True,
            'mensaje': 'Material disponible'
        })
    
    except Material.DoesNotExist:
        return JsonResponse({'disponible': False, 'mensaje': 'Material no encontrado'})

@login_required
@requiere_gerente_o_superior
def obtener_historial(request):
    """Obtiene el historial de préstamos"""
    
    try:
        from ..models import HistorialPrestamo
        
        historial = HistorialPrestamo.objects.all().order_by('-fecha_devuelto')
        
        data = []
        for item in historial:
            data.append({
                'id': item.id,
                'material_codigo': item.material_codigo,
                'material_nombre': item.material_nombre,
                'prestado_a': item.prestado_a,
                'fecha_prestamo': item.fecha_prestamo.isoformat(),
                'fecha_devolucion': item.fecha_devolucion.isoformat(),
                'fecha_devuelto': item.fecha_devuelto.isoformat() if item.fecha_devuelto else None,
                'duracion_dias': item.duracion_dias(),
                'observaciones': item.observaciones or ''
            })
        
        return JsonResponse({
            'success': True,
            'historial': data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

# === Categorias ===

@login_required
@requiere_gerente_o_superior
@require_http_methods(["POST"])
def crear_categoria_material(request):
    """Crear nueva categoría de material vía AJAX"""
    try:
        data = json.loads(request.body)
        
        categoria = CategoriaMaterial.objects.create(
            nombre=data.get('nombre'),
            descripcion=data.get('descripcion', ''),
            orden=data.get('orden', 0),
            activo=True
        )
        
        return JsonResponse({
            'success': True,
            'categoria_id': categoria.id,
            'message': 'Categoría creada exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["GET"])
def obtener_categoria_material(request, categoria_id):
    """Obtener datos de una categoría de material"""
    try:
        categoria = get_object_or_404(CategoriaMaterial, pk=categoria_id)
        
        return JsonResponse({
            'success': True,
            'categoria': {
                'id': categoria.id,
                'nombre': categoria.nombre,
                'descripcion': categoria.descripcion,
                'orden': categoria.orden,
                'activo': categoria.activo
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["PUT", "POST"])
def editar_categoria_material(request, categoria_id):
    """Editar categoría de material existente"""
    try:
        categoria = get_object_or_404(CategoriaMaterial, pk=categoria_id)
        data = json.loads(request.body)
        
        categoria.nombre = data.get('nombre', categoria.nombre)
        categoria.descripcion = data.get('descripcion', categoria.descripcion)
        categoria.orden = data.get('orden', categoria.orden)
        categoria.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Categoría actualizada exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@requiere_gerente_o_superior
@require_http_methods(["DELETE"])
def eliminar_categoria_material(request, categoria_id):
    """Eliminar categoría de material"""
    try:
        categoria = get_object_or_404(CategoriaMaterial, pk=categoria_id)
        
        # Verificar si hay materiales asociados
        materiales_count = categoria.materiales.count()
        
        if materiales_count > 0:
            return JsonResponse({
                'success': False,
                'error': f'No se puede eliminar la categoría porque tiene {materiales_count} material(es) asociado(s)'
            })
        
        categoria.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Categoría eliminada exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })