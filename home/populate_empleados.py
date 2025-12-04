from django.contrib.auth.models import User
from home.models import PerfilEmpleado  # Ajusta la importación según tu estructura
from datetime import date, datetime
from django.db import transaction

def crear_empleados():
    """Crea usuarios y perfiles de empleados de prueba"""
    
    empleados_data = [
        # Administradores
        {
            'username': 'admin',
            'email': 'admin@empresa.com',
            'first_name': 'Carlos',
            'last_name': 'Rodríguez',
            'password': 'admin123',
            'cargo': 'admin',
            'departamento': 'TI',
            'fecha_ingreso': date(2020, 1, 15),
            'telefono': '+56 9 8765 4321',
            'salario': 2500000,
        },

        # Empleados
        {
            'username': 'empleado',
            'email': 'empleado1@empresa.com',
            'first_name': 'José',
            'last_name': 'Martínez',
            'password': 'empleado123',
            'cargo': 'empleado',
            'departamento': 'Ventas',
            'fecha_ingreso': date(2022, 6, 1),
            'telefono': '+56 9 8765 4328',
            'salario': 800000,
        },
        
        # Empleado inactivo (para pruebas)
        {
            'username': 'empleado_inactivo',
            'email': 'inactivo@empresa.com',
            'first_name': 'Ricardo',
            'last_name': 'Mendoza',
            'password': 'inactivo123',
            'cargo': 'empleado',
            'departamento': 'Ventas',
            'fecha_ingreso': date(2021, 12, 1),
            'telefono': '+56 9 8765 4332',
            'salario': 680000,
            'activo': False,  # Este estará inactivo
        },
    ]
    
    with transaction.atomic():
        print("Creando usuarios y perfiles de empleados...")
        
        for emp_data in empleados_data:
            # Verificar si el usuario ya existe
            if User.objects.filter(username=emp_data['username']).exists():
                print(f"Usuario {emp_data['username']} ya existe, saltando...")
                continue
            
            # Crear el usuario
            user = User.objects.create_user(
                username=emp_data['username'],
                email=emp_data['email'],
                first_name=emp_data['first_name'],
                last_name=emp_data['last_name'],
                password=emp_data['password']
            )
            
            # Crear el perfil del empleado
            perfil = PerfilEmpleado.objects.create(
                user=user,
                cargo=emp_data['cargo'],
                departamento=emp_data['departamento'],
                fecha_ingreso=emp_data['fecha_ingreso'],
                telefono=emp_data['telefono'],
                salario=emp_data['salario'],
                activo=emp_data.get('activo', True)
            )
            
            print(f"✓ Creado: {user.get_full_name()} - {perfil.get_cargo_display()}")

def mostrar_usuarios_creados():
    """Muestra un resumen de los usuarios creados"""
    print("\n" + "="*50)
    print("RESUMEN DE USUARIOS CREADOS")
    print("="*50)
    
    perfiles = PerfilEmpleado.objects.all().order_by('cargo', 'user__first_name')
    
    cargo_anterior = None
    for perfil in perfiles:
        if perfil.cargo != cargo_anterior:
            print(f"\n--- {perfil.get_cargo_display().upper()} ---")
            cargo_anterior = perfil.cargo
        
        estado = "✓ Activo" if perfil.activo else "✗ Inactivo"
        print(f"Usuario: {perfil.user.username:<15} | "
              f"Nombre: {perfil.nombre_completo:<20} | "
              f"Depto: {perfil.departamento:<15} | "
              f"{estado}")
    
    print(f"\nTotal de usuarios creados: {User.objects.count()}")
    print(f"Total de perfiles activos: {PerfilEmpleado.objects.filter(activo=True).count()}")
    print(f"Total de perfiles inactivos: {PerfilEmpleado.objects.filter(activo=False).count()}")
    
    print("\n" + "="*50)
    print("CREDENCIALES DE ACCESO")
    print("="*50)
    print("Administrador: admin / admin123")
    print("Gerente: gerente1 / gerente123")
    print("Supervisor: supervisor1 / supervisor123")
    print("Empleado: empleado1 / empleado123")
    print("Empleado Inactivo: empleado_inactivo / inactivo123")

if __name__ == "__main__":
    crear_empleados()
    mostrar_usuarios_creados()