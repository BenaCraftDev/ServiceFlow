from django.db import migrations, models
import django.db.models.deletion


def crear_unidades_por_defecto(apps, schema_editor):
    """
    Crea unidades estándar por defecto
    """
    UnidadMaterial = apps.get_model('cotizaciones', 'UnidadMaterial')
    
    unidades_defecto = [
        {'nombre': 'Unidad', 'abreviatura': 'UND', 'descripcion': 'Unidad', 'orden': 0},
        {'nombre': 'Metro', 'abreviatura': 'MT', 'descripcion': 'Metro lineal', 'orden': 1},
        {'nombre': 'Metro Cuadrado', 'abreviatura': 'M2', 'descripcion': 'Metro cuadrado', 'orden': 2},
        {'nombre': 'Metro Cúbico', 'abreviatura': 'M3', 'descripcion': 'Metro cúbico', 'orden': 3},
        {'nombre': 'Kilogramo', 'abreviatura': 'KG', 'descripcion': 'Kilogramo', 'orden': 4},
        {'nombre': 'Gramo', 'abreviatura': 'GR', 'descripcion': 'Gramo', 'orden': 5},
        {'nombre': 'Litro', 'abreviatura': 'LT', 'descripcion': 'Litro', 'orden': 6},
        {'nombre': 'Mililitro', 'abreviatura': 'ML', 'descripcion': 'Mililitro', 'orden': 7},
        {'nombre': 'Caja', 'abreviatura': 'CAJ', 'descripcion': 'Caja', 'orden': 8},
        {'nombre': 'Paquete', 'abreviatura': 'PAQ', 'descripcion': 'Paquete', 'orden': 9},
        {'nombre': 'Rollo', 'abreviatura': 'ROL', 'descripcion': 'Rollo', 'orden': 10},
        {'nombre': 'Set', 'abreviatura': 'SET', 'descripcion': 'Set o conjunto', 'orden': 11},
        {'nombre': 'Par', 'abreviatura': 'PAR', 'descripción': 'Par', 'orden': 12},
        {'nombre': 'Docena', 'abreviatura': 'DOC', 'descripcion': 'Docena', 'orden': 13},
        {'nombre': 'Galón', 'abreviatura': 'GAL', 'descripcion': 'Galón', 'orden': 14},
        {'nombre': 'Pulgada', 'abreviatura': 'PLG', 'descripcion': 'Pulgada', 'orden': 15},
        {'nombre': 'Pie', 'abreviatura': 'PIE', 'descripcion': 'Pie', 'orden': 16},
        {'nombre': 'Hora', 'abreviatura': 'HR', 'descripcion': 'Hora de trabajo', 'orden': 17},
    ]
    
    print(f"\n📏 Creando unidades estándar...")
    for unidad_data in unidades_defecto:
        unidad, created = UnidadMaterial.objects.get_or_create(
            abreviatura=unidad_data['abreviatura'],
            defaults={
                'nombre': unidad_data['nombre'],
                'descripcion': unidad_data.get('descripcion', ''),
                'orden': unidad_data['orden'],
                'activo': True
            }
        )
        if created:
            print(f"   ✅ Creada unidad: {unidad_data['abreviatura']} - {unidad_data['nombre']}")
    
    print(f"   Total unidades creadas: {len(unidades_defecto)}\n")


def migrar_unidades_a_fk(apps, schema_editor):
    """
    Migra las unidades de texto al campo ForeignKey
    """
    Material = apps.get_model('cotizaciones', 'Material')
    UnidadMaterial = apps.get_model('cotizaciones', 'UnidadMaterial')
    
    print("\n🔄 Migrando unidades de materiales...")
    migrados = 0
    sin_unidad = 0
    creadas = 0
    
    for material in Material.objects.all():
        if material.unidad and material.unidad.strip():  # Si tiene unidad como texto
            unidad_texto = material.unidad.strip().upper()
            
            # Buscar unidad existente por abreviatura
            unidad_obj = UnidadMaterial.objects.filter(abreviatura=unidad_texto).first()
            
            # Si no existe, crear una nueva
            if not unidad_obj:
                unidad_obj, created = UnidadMaterial.objects.get_or_create(
                    abreviatura=unidad_texto,
                    defaults={
                        'nombre': unidad_texto,
                        'descripcion': f'Unidad migrada automáticamente: {unidad_texto}',
                        'orden': 100 + creadas,
                        'activo': True
                    }
                )
                if created:
                    print(f"   ℹ️  Nueva unidad creada: {unidad_texto}")
                    creadas += 1
            
            material.unidad_nueva = unidad_obj
            material.save(update_fields=['unidad_nueva'])
            migrados += 1
        else:
            sin_unidad += 1
    
    print(f"   ✅ Materiales migrados: {migrados}")
    print(f"   ➕ Nuevas unidades creadas: {creadas}")
    print(f"   ℹ️  Materiales sin unidad: {sin_unidad}\n")


class Migration(migrations.Migration):

    dependencies = [
        ('cotizaciones', '0018_categoriamaterial_migracion_completa'),  # ⚠️ ACTUALIZA esto
    ]

    operations = [
        # PASO 1: Crear el modelo UnidadMaterial
        migrations.CreateModel(
            name='UnidadMaterial',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=50, unique=True)),
                ('abreviatura', models.CharField(max_length=10)),
                ('descripcion', models.TextField(blank=True, null=True)),
                ('orden', models.IntegerField(default=0)),
                ('activo', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Unidad de Material',
                'verbose_name_plural': 'Unidades de Materiales',
                'ordering': ['orden', 'abreviatura'],
            },
        ),
        
        # PASO 2: Crear unidades por defecto
        migrations.RunPython(
            code=crear_unidades_por_defecto,
            reverse_code=migrations.RunPython.noop,
        ),
        
        # PASO 3: Agregar nuevo campo ForeignKey temporal
        migrations.AddField(
            model_name='material',
            name='unidad_nueva',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='materiales_temp',
                to='cotizaciones.unidadmaterial',
                db_column='unidad_nueva_id',
            ),
        ),
        
        # PASO 4: Migrar datos del campo antiguo (CharField) al nuevo (ForeignKey)
        migrations.RunPython(
            code=migrar_unidades_a_fk,
            reverse_code=migrations.RunPython.noop,
        ),
        
        # PASO 5: Eliminar el campo antiguo 'unidad' (CharField)
        migrations.RemoveField(
            model_name='material',
            name='unidad',
        ),
        
        # PASO 6: Renombrar unidad_nueva a unidad
        migrations.RenameField(
            model_name='material',
            old_name='unidad_nueva',
            new_name='unidad',
        ),
        
        # PASO 7: Actualizar related_name después del renombre
        migrations.AlterField(
            model_name='material',
            name='unidad',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='materiales',
                to='cotizaciones.unidadmaterial'
            ),
        ),
    ]






