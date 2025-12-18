# cotizaciones/migrations/0014_evidenciatrabajo_gastotrabajo.py

from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('cotizaciones', '0013_alter_cotizacion_numero'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS cotizaciones_evidenciatrabajo (
                id bigserial NOT NULL PRIMARY KEY,
                trabajo_id bigint NOT NULL,
                imagen varchar(100) NOT NULL,
                descripcion text,
                fecha_subida timestamp with time zone NOT NULL,
                CONSTRAINT cotizaciones_evidenciatrabajo_trabajo_id_fkey 
                    FOREIGN KEY (trabajo_id) 
                    REFERENCES cotizaciones_trabajoempleado(id) 
                    ON DELETE CASCADE
            );
            
            CREATE INDEX IF NOT EXISTS cotizaciones_evidenciatrabajo_trabajo_id_idx 
                ON cotizaciones_evidenciatrabajo(trabajo_id);
            
            CREATE TABLE IF NOT EXISTS cotizaciones_gastotrabajo (
                id bigserial NOT NULL PRIMARY KEY,
                trabajo_id bigint NOT NULL UNIQUE,
                materiales numeric(10, 2) NOT NULL DEFAULT 0,
                materiales_detalle text,
                transporte numeric(10, 2) NOT NULL DEFAULT 0,
                transporte_detalle text,
                otros numeric(10, 2) NOT NULL DEFAULT 0,
                otros_detalle text,
                fecha_creacion timestamp with time zone NOT NULL,
                fecha_actualizacion timestamp with time zone NOT NULL,
                CONSTRAINT cotizaciones_gastotrabajo_trabajo_id_fkey 
                    FOREIGN KEY (trabajo_id) 
                    REFERENCES cotizaciones_trabajoempleado(id) 
                    ON DELETE CASCADE
            );
            """,
            reverse_sql="""
            DROP TABLE IF EXISTS cotizaciones_gastotrabajo CASCADE;
            DROP TABLE IF EXISTS cotizaciones_evidenciatrabajo CASCADE;
            """
        ),
    ]