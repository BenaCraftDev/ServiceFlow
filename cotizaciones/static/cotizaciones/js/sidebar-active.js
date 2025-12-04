// sidebar-active.js
// Script para activar automáticamente el enlace correcto del sidebar

document.addEventListener('DOMContentLoaded', function() {
    activarMenuActual();
});

function activarMenuActual() {
    const currentPath = window.location.pathname;
    const sidebarLinks = document.querySelectorAll('#sidebar-nav a[data-page]');
    
    if (!sidebarLinks.length) return;
    
    // Remover todas las clases active primero
    sidebarLinks.forEach(link => link.classList.remove('active'));
    
    // Mapeo de URLs a páginas
    const urlPatterns = [
        { pattern: /\/panel[\/]?$/, page: 'panel_empleados' },
        { pattern: /\/usuarios[\/]?/, page: 'gestion_usuarios' },
        { pattern: /\/cotizaciones\/dashboard[\/]?$/, page: 'dashboard' },
        { pattern: /\/cotizaciones\/clientes[\/]?/, page: 'gestionar_clientes' },
        { pattern: /\/cotizaciones\/servicios[\/]?/, page: 'gestionar_servicios' },
        { pattern: /\/cotizaciones\/materiales[\/]?/, page: 'gestionar_materiales' },
        { pattern: /\/cotizaciones\/categorias-empleados[\/]?/, page: 'gestionar_categorias_empleados' },
        { pattern: /\/cotizaciones\/reportes[\/]?/, page: 'reportes_dashboard' },
        { pattern: /\/cotizaciones\/seguimiento-trabajos[\/]?/, page: 'seguimiento_trabajos' }
    ];
    
    // Buscar coincidencia con la URL actual
    for (const { pattern, page } of urlPatterns) {
        if (pattern.test(currentPath)) {
            const activeLink = document.querySelector(`#sidebar-nav a[data-page="${page}"]`);
            if (activeLink) {
                activeLink.classList.add('active');
                break;
            }
        }
    }
}