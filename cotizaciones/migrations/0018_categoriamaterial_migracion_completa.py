from django.db import migrations, models
import django.db.models.deletion


def crear_categorias_desde_texto(apps, schema_editor):
    """
    Crea objetos CategoriaMaterial desde los valores únicos del campo categoria (CharField)
    """
    Material = apps.get_model('cotizaciones', 'Material')
    CategoriaMaterial = apps.get_model('cotizaciones', 'CategoriaMaterial')
    
    # Obtener categorías únicas existentes (excluyendo vacías y None)
    categorias_texto = Material.objects.exclude(
        models.Q(categoria__isnull=True) | models.Q(categoria='')
    ).values_list('categoria', flat=True).distinct()
    
    # Crear objetos CategoriaMaterial
    orden = 0
    print(f"\n🏷️  Creando categorías desde datos existentes...")
    for cat_texto in categorias_texto:
        categoria, created = CategoriaMaterial.objects.get_or_create(
            nombre=cat_texto,
            defaults={
                'descripcion': f'Categoría migrada automáticamente',
                'orden': orden,
                'activo': True
            }
        )
        if created:
            print(f"   ✅ Creada categoría: {cat_texto}")
        orden += 1
    
    print(f"   Total categorías creadas: {orden}\n")


def migrar_categorias_a_fk(apps, schema_editor):
    """
    Migra las categorías de texto al campo ForeignKey temporal
    """
    Material = apps.get_model('cotizaciones', 'Material')
    CategoriaMaterial = apps.get_model('cotizaciones', 'CategoriaMaterial')
    
    print("\n🔄 Migrando categorías de materiales...")
    migrados = 0
    sin_categoria = 0
    
    for material in Material.objects.all():
        if material.categoria and material.categoria.strip():  # Si tiene categoría como texto
            try:
                categoria_obj = CategoriaMaterial.objects.get(nombre=material.categoria)
                material.categoria_nueva = categoria_obj
                material.save(update_fields=['categoria_nueva'])
                migrados += 1
            except CategoriaMaterial.DoesNotExist:
                print(f"   ⚠️  No se encontró categoría '{material.categoria}' para material {material.codigo}")
                sin_categoria += 1
        else:
            sin_categoria += 1
    
    print(f"   ✅ Materiales migrados: {migrados}")
    print(f"   ℹ️  Materiales sin categoría: {sin_categoria}\n")


class Migration(migrations.Migration):

    dependencies = [
        ('cotizaciones', '0017_solicitud_web_delete_solicitudweb_and_more'), 
    ]

    operations = [
        # PASO 1: Crear el modelo CategoriaMaterial
        migrations.CreateModel(
            name='CategoriaMaterial',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100)),
                ('descripcion', models.TextField(blank=True, null=True)),
                ('orden', models.IntegerField(default=0)),
                ('activo', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Categoría de Material',
                'verbose_name_plural': 'Categorías de Materiales',
                'ordering': ['orden', 'nombre'],
            },
        ),
        
        # PASO 2: Crear categorías desde los valores de texto existentes
        migrations.RunPython(
            code=crear_categorias_desde_texto,
            reverse_code=migrations.RunPython.noop,
        ),
        
        # PASO 3: Agregar nuevo campo ForeignKey temporal (sin afectar el campo original)
        migrations.AddField(
            model_name='material',
            name='categoria_nueva',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='materiales_temp',
                to='cotizaciones.categoriamaterial',
                db_column='categoria_nueva_id',  # Nombre explícito para la columna
            ),
        ),
        
        # PASO 4: Migrar datos del campo antiguo (CharField) al nuevo (ForeignKey)
        migrations.RunPython(
            code=migrar_categorias_a_fk,
            reverse_code=migrations.RunPython.noop,
        ),
        
        # PASO 5: Eliminar el campo antiguo 'categoria' (CharField)
        migrations.RemoveField(
            model_name='material',
            name='categoria',
        ),
        
        # PASO 6: Renombrar categoria_nueva a categoria
        migrations.RenameField(
            model_name='material',
            old_name='categoria_nueva',
            new_name='categoria',
        ),
        
        # PASO 7: Actualizar related_name después del renombre
        migrations.AlterField(
            model_name='material',
            name='categoria',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='materiales',
                to='cotizaciones.categoriamaterial'
            ),
        ),
    ]