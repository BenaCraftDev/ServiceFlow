function getCSRFToken() {
    // Buscar en meta tag primero
    const metaToken = document.querySelector('meta[name="csrf-token"]');
    if (metaToken) {
        return metaToken.getAttribute('content');
    }
    
    // Buscar en input como fallback
    const inputToken = document.querySelector('[name=csrfmiddlewaretoken]');
    if (inputToken) {
        return inputToken.value;
    }
    
    // Buscar en cookies como último recurso
    return getCookie('csrftoken') || '';
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Funciones para modales
function mostrarModal(modalId) {
    document.getElementById(modalId).classList.add('show');
}

function cerrarModal(modalId) {
    document.getElementById(modalId).classList.remove('show');
    limpiarFormularioModal(modalId);
}

function limpiarFormularioModal(modalId) {
    const modal = document.getElementById(modalId);
    const inputs = modal.querySelectorAll('input, select, textarea');
    inputs.forEach(input => {
        if (input.type === 'checkbox') {
            input.checked = false;
        } else {
            input.value = '';
        }
    });
    
    // Limpiar contenedores dinámicos
    const parametrosContainer = modal.querySelector('.parametros-container');
    if (parametrosContainer) {
        parametrosContainer.classList.remove('show');
        parametrosContainer.innerHTML = '';
    }
}

// Cerrar modales al hacer clic fuera
window.onclick = function(event) {
    const modales = document.querySelectorAll('.modal');
    modales.forEach(modal => {
        if (event.target === modal) {
            modal.classList.remove('show');
        }
    });
}

// Función genérica para peticiones AJAX
async function hacerPeticionAjax(url, method = 'GET', data = null) {
    const config = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        }
    };
    
    if (data) {
        config.body = JSON.stringify(data);
    }
    
    try {
        const response = await fetch(url, config);
        return await response.json();
    } catch (error) {
        console.error('Error en petición AJAX:', error);
        throw error;
    }
}

// Cargar servicios por categoría
async function cargarServicios() {
    const categoriaId = document.getElementById('categoria-servicio').value;
    const servicioSelect = document.getElementById('servicio-select');
    
    servicioSelect.innerHTML = '<option value="">Seleccionar servicio</option>';
    
    const parametrosContainer = document.getElementById('parametros-servicio');
    if (parametrosContainer) {
        parametrosContainer.classList.remove('show');
    }
    
    if (!categoriaId) return;
    
    try {
        const servicios = await hacerPeticionAjax(`/cotizaciones/api/categoria/${categoriaId}/servicios/`);
        
        servicios.forEach(servicio => {
            const option = document.createElement('option');
            option.value = servicio.id;
            option.textContent = servicio.nombre;
            option.dataset.precio = servicio.precio_base;
            option.dataset.parametrizable = servicio.es_parametrizable;
            servicioSelect.appendChild(option);
        });
    } catch (error) {
        console.error('Error cargando servicios:', error);
        alert('Error al cargar los servicios');
    }
}

// Cargar parámetros del servicio
async function cargarParametrosServicio() {
    const servicioSelect = document.getElementById('servicio-select');
    const servicioId = servicioSelect.value;
    const selectedOption = servicioSelect.selectedOptions[0];
    
    // Establecer precio base
    if (selectedOption) {
        const precioInput = document.getElementById('precio-servicio');
        if (precioInput) {
            precioInput.value = selectedOption.dataset.precio;
        }
    }
    
    const parametrosContainer = document.getElementById('parametros-servicio');
    if (!parametrosContainer) return;
    
    parametrosContainer.innerHTML = '';
    parametrosContainer.classList.remove('show');
    
    if (!servicioId || selectedOption.dataset.parametrizable === 'false') return;
    
    try {
        const parametros = await hacerPeticionAjax(`/cotizaciones/api/servicio/${servicioId}/parametros/`);
        
        if (parametros.length > 0) {
            parametrosContainer.innerHTML = '<h4 style="margin: 0 0 12px; color: var(--azul-700);">Parámetros del Servicio</h4>';
            
            parametros.forEach(param => {
                const formGroup = document.createElement('div');
                formGroup.className = 'form-group';
                
                let inputHtml = '';
                if (param.tipo === 'select') {
                    const opciones = param.opciones_list.map(opt => `<option value="${opt}">${opt}</option>`).join('');
                    inputHtml = `<select id="param-${param.id}">${opciones}</select>`;
                } else if (param.tipo === 'boolean') {
                    inputHtml = `<select id="param-${param.id}">
                        <option value="true">Sí</option>
                        <option value="false">No</option>
                    </select>`;
                } else {
                    const type = param.tipo === 'number' ? 'number' : 'text';
                    inputHtml = `<input type="${type}" id="param-${param.id}" value="${param.valor_por_defecto || ''}">`;
                }
                
                formGroup.innerHTML = `
                    <label for="param-${param.id}">${param.nombre}${param.requerido ? ' *' : ''}</label>
                    ${inputHtml}
                `;
                
                parametrosContainer.appendChild(formGroup);
            });
            
            parametrosContainer.classList.add('show');
        }
    } catch (error) {
        console.error('Error cargando parámetros:', error);
    }
}

// Cargar precio del material
function cargarPrecioMaterial() {
    const materialSelect = document.getElementById('material-select');
    const selectedOption = materialSelect.selectedOptions[0];
    
    if (selectedOption) {
        const precioInput = document.getElementById('precio-material');
        if (precioInput) {
            precioInput.value = selectedOption.dataset.precio;
        }
    }
}

// Agregar servicio
async function agregarServicio() {
    const cotizacionId = window.cotizacionId;
    if (!cotizacionId) {
        alert('Error: No se encontró ID de cotización');
        return;
    }
    
    const servicioId = document.getElementById('servicio-select').value;
    const cantidad = document.getElementById('cantidad-servicio').value;
    const precioUnitario = document.getElementById('precio-servicio').value;
    const descripcionPersonalizada = document.getElementById('descripcion-servicio').value;
    
    if (!servicioId || !cantidad || !precioUnitario) {
        alert('Por favor completa todos los campos requeridos');
        return;
    }
    
    // Recopilar parámetros
    const parametros = {};
    const parametrosContainer = document.getElementById('parametros-servicio');
    if (parametrosContainer) {
        const inputs = parametrosContainer.querySelectorAll('input, select');
        inputs.forEach(input => {
            if (input.id.startsWith('param-')) {
                const paramId = input.id.replace('param-', '');
                parametros[paramId] = input.value;
            }
        });
    }
    
    try {
        const result = await hacerPeticionAjax(`/cotizaciones/${cotizacionId}/item-servicio/`, 'POST', {
            servicio_id: servicioId,
            cantidad: cantidad,
            precio_unitario: precioUnitario,
            descripcion_personalizada: descripcionPersonalizada,
            parametros: parametros
        });
        
        if (result.success) {
            location.reload();
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        console.error('Error agregando servicio:', error);
        alert('Error al agregar el servicio');
    }
}

// Agregar material
async function agregarMaterial() {
    const cotizacionId = window.cotizacionId;
    if (!cotizacionId) {
        alert('Error: No se encontró ID de cotización');
        return;
    }
    
    const materialId = document.getElementById('material-select').value;
    const cantidad = document.getElementById('cantidad-material').value;
    const precioUnitario = document.getElementById('precio-material').value;
    const descripcionPersonalizada = document.getElementById('descripcion-personalizada-material').value;
    
    if (!materialId || !cantidad || !precioUnitario) {
        alert('Por favor completa todos los campos requeridos');
        return;
    }
    
    try {
        const result = await hacerPeticionAjax(`/cotizaciones/${cotizacionId}/item-material/`, 'POST', {
            material_id: materialId,
            cantidad: cantidad,
            precio_unitario: precioUnitario,
            descripcion_personalizada: descripcionPersonalizada
        });
        
        if (result.success) {
            location.reload();
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        console.error('Error agregando material:', error);
        alert('Error al agregar el material');
    }
}

// Agregar mano de obra
async function agregarManoObra() {
    const cotizacionId = window.cotizacionId;
    if (!cotizacionId) {
        alert('Error: No se encontró ID de cotización');
        return;
    }
    
    const descripcion = document.getElementById('descripcion-mano-obra').value;
    const horas = document.getElementById('horas-mano-obra').value;
    const precioHora = document.getElementById('precio-hora-mano-obra').value;
    
    if (!descripcion || !horas || !precioHora) {
        alert('Por favor completa todos los campos requeridos');
        return;
    }
    
    try {
        const result = await hacerPeticionAjax(`/cotizaciones/${cotizacionId}/item-mano-obra/`, 'POST', {
            descripcion: descripcion,
            horas: horas,
            precio_hora: precioHora
        });
        
        if (result.success) {
            location.reload();
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        console.error('Error agregando mano de obra:', error);
        alert('Error al agregar la mano de obra');
    }
}

// Eliminar items
async function eliminarItem(tipo, itemId) {
    const cotizacionId = window.cotizacionId;
    if (!cotizacionId) {
        alert('Error: No se encontró ID de cotización');
        return;
    }
    
    const tipoTexto = {
        'servicio': 'servicio',
        'material': 'material',
        'mano-obra': 'trabajo'
    };
    
    if (!confirm(`¿Estás seguro de eliminar este ${tipoTexto[tipo]}?`)) return;
    
    try {
        const result = await hacerPeticionAjax(
            `/cotizaciones/${cotizacionId}/item-${tipo}/${itemId}/eliminar/`, 
            'DELETE'
        );
        
        if (result.success) {
            location.reload();
        } else {
            alert(`Error al eliminar el ${tipoTexto[tipo]}`);
        }
    } catch (error) {
        console.error(`Error eliminando ${tipo}:`, error);
        alert(`Error al eliminar el ${tipoTexto[tipo]}`);
    }
}

function eliminarItemServicio(itemId) { eliminarItem('servicio', itemId); }
function eliminarItemMaterial(itemId) { eliminarItem('material', itemId); }
function eliminarItemManoObra(itemId) { eliminarItem('mano-obra', itemId); }

// Actualizar gastos de traslado
async function actualizarGastosTraslado() {
    const cotizacionId = window.cotizacionId;
    if (!cotizacionId) return;
    
    const gastosTraslado = document.getElementById('gastos-traslado').value;
    
    try {
        const result = await hacerPeticionAjax(`/cotizaciones/${cotizacionId}/gastos-traslado/`, 'POST', {
            gastos_traslado: gastosTraslado
        });
        
        if (result.success) {
            // Actualizar totales en pantalla
            actualizarTotalesEnPantalla(result);
        }
    } catch (error) {
        console.error('Error actualizando gastos de traslado:', error);
    }
}

// Actualizar totales en pantalla
function actualizarTotalesEnPantalla(data) {
    const elementos = {
        'display-gastos-traslado': data.gastos_traslado || 0,
        'valor-neto': data.valor_neto || 0,
        'valor-iva': data.valor_iva || 0,
        'valor-total': data.valor_total || 0
    };
    
    Object.keys(elementos).forEach(id => {
        const elemento = document.getElementById(id);
        if (elemento) {
            elemento.textContent = `$${parseInt(elementos[id]).toLocaleString()}`;
        }
    });
}

// Cambiar estado de cotización
async function cambiarEstado(nuevoEstado) {
    const cotizacionId = window.cotizacionId;
    if (!cotizacionId) return;
    
    if (!confirm('¿Estás seguro de cambiar el estado de la cotización?')) {
        return;
    }

    try {
        const result = await hacerPeticionAjax(`/cotizaciones/${cotizacionId}/estado/`, 'POST', {
            estado: nuevoEstado
        });

        if (result.success) {
            location.reload();
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        console.error('Error cambiando estado:', error);
        alert('Error al cambiar el estado');
    }

    // Cerrar menú de estado
    const menu = document.getElementById('estado-menu');
    if (menu) {
        menu.style.display = 'none';
    }
}

// Toggle menú de estado
function toggleEstadoMenu() {
    const menu = document.getElementById('estado-menu');
    if (menu) {
        menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
    }
}

// Cerrar menú de estado al hacer clic fuera
document.addEventListener('click', function(event) {
    const menu = document.getElementById('estado-menu');
    const button = event.target.closest('button');
    
    if (menu && (!button || !button.onclick || button.onclick.toString().indexOf('toggleEstadoMenu') === -1)) {
        menu.style.display = 'none';
    }
});

// Función para guardar cotización (modo editar)
function guardarCotizacion() {
    const form = document.getElementById('cotizacion-form');
    if (form) {
        form.submit();
    }
}

// Funciones para gestión de entidades (clientes, servicios, materiales)
function mostrarModalCliente() {
    mostrarModal('modal-cliente');
}

function mostrarModalServicioBase() {
    mostrarModal('modal-servicio-base');
}

function mostrarModalMaterialBase() {
    mostrarModal('modal-material-base');
}

// Función genérica para eliminar entidades
async function eliminarEntidad(tipo, id, nombre = '') {
    const tipos = {
        cliente: 'cliente',
        servicio: 'servicio', 
        material: 'material'
    };
    
    const mensaje = nombre ? 
        `¿Estás seguro de eliminar ${tipos[tipo]} "${nombre}"?` : 
        `¿Estás seguro de eliminar este ${tipos[tipo]}?`;
    
    if (!confirm(mensaje)) return;
    
    try {
        const response = await fetch(`/cotizaciones/${tipo}/${id}/eliminar/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCSRFToken()
            }
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(result.message);
            location.reload();
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        console.error(`Error eliminando ${tipo}:`, error);
        alert(`Error al eliminar el ${tipos[tipo]}`);
    }
}

// Funciones específicas para cada tipo
function eliminarCliente(id, nombre) {
    eliminarEntidad('cliente', id, nombre);
}

function eliminarServicio(id, nombre) {
    eliminarEntidad('servicio', id, nombre);
}

function eliminarMaterial(id, nombre) {
    eliminarEntidad('material', id, nombre);
}

// Función para formatear números como moneda
function formatearMoneda(numero) {
    return new Intl.NumberFormat('es-CL', {
        style: 'currency',
        currency: 'CLP',
        minimumFractionDigits: 0
    }).format(numero);
}

// Función para validar formularios
function validarFormulario(formId) {
    const form = document.getElementById(formId);
    if (!form) return false;
    
    const requeridos = form.querySelectorAll('[required]');
    let valido = true;
    
    requeridos.forEach(campo => {
        if (!campo.value.trim()) {
            campo.style.borderColor = 'var(--rojo-600)';
            valido = false;
        } else {
            campo.style.borderColor = 'var(--gris-300)';
        }
    });
    
    return valido;
}

function formatearNumero(numero) {
    if (!numero) return '0';
    
    // Convertir a número si es string
    const num = typeof numero === 'string' ? parseFloat(numero) : numero;
    
    // Formatear con separador de miles (punto) estilo chileno
    return num.toLocaleString('es-CL', { 
        minimumFractionDigits: 0,
        maximumFractionDigits: 0 
    });
}

// Función para formatear precios con signo peso
function formatearPrecio(numero) {
    return '$' + formatearNumero(numero);
}

// Aplicar formato a todos los números al cargar la página
document.addEventListener('DOMContentLoaded', function() {
    // Formatear todos los elementos con clase 'numero'
    document.querySelectorAll('.numero, .precio, .total').forEach(function(elemento) {
        const valor = elemento.textContent || elemento.innerText;
        const numeroLimpio = valor.replace(/[^\d]/g, ''); // Solo números
        
        if (numeroLimpio) {
            if (elemento.classList.contains('precio') || valor.includes('$')) {
                elemento.textContent = formatearPrecio(numeroLimpio);
            } else {
                elemento.textContent = formatearNumero(numeroLimpio);
            }
        }
    });
    
    // Formatear totales en tiempo real
    if (typeof calcularTotales === 'function') {
        calcularTotales();
    }
});

// SISTEMA DE FILTROS EN TIEMPO REAL

// Filtros para USUARIOS
function initFiltrosUsuarios() {
    const inputBusqueda = document.querySelector('.filters input[name="busqueda"]');
    const selectCargo = document.querySelector('#filtro-cargo');
    const selectActivo = document.querySelector('#filtro-activo');
    const inputFecha = document.querySelector('#filtro-fecha');
    const tabla = document.querySelector('.table-wrap table tbody');
    
    if (!inputBusqueda || !tabla) return;
    
    const todasLasFilas = Array.from(tabla.querySelectorAll('tr'));
    
    function filtrarTabla() {
        const textoBusqueda = inputBusqueda.value.toLowerCase().trim();
        const cargoSeleccionado = selectCargo ? selectCargo.value : '';
        const estadoSeleccionado = selectActivo ? selectActivo.value : '';
        const fechaDesde = inputFecha ? inputFecha.value : '';
        
        let filasVisibles = 0;
        
        todasLasFilas.forEach(function(fila) {
            if (fila.querySelector('td[colspan]')) {
                fila.style.display = 'none';
                return;
            }
            
            const textoFila = fila.textContent.toLowerCase();
            const coincideTexto = textoBusqueda === '' || textoFila.includes(textoBusqueda);
            
            let coincideCargo = true;
            if (cargoSeleccionado && selectCargo) {
                const cargoPill = fila.querySelector('.pill[class*="cargo-"]');
                if (cargoPill) {
                    coincideCargo = cargoPill.className.includes('cargo-' + cargoSeleccionado);
                }
            }
            
            let coincideEstado = true;
            if (estadoSeleccionado && selectActivo) {
                const estadoPill = fila.querySelectorAll('.pill')[1];
                if (estadoPill) {
                    const esActivo = estadoPill.classList.contains('activo');
                    coincideEstado = (estadoSeleccionado === '1') ? esActivo : !esActivo;
                }
            }
            
            // Filtro por fecha de ingreso (últimos 30 días)
            let coincideFecha = true;
            if (fechaDesde) {
                const fechaIngreso = fila.getAttribute('data-fecha-ingreso');
                if (fechaIngreso) {
                    coincideFecha = fechaIngreso >= fechaDesde;
                }
            }
            
            if (coincideTexto && coincideCargo && coincideEstado && coincideFecha) {
                fila.style.display = '';
                filasVisibles++;
            } else {
                fila.style.display = 'none';
            }
        });
        
        actualizarContadorResultados(filasVisibles);
        mostrarMensajeSinResultados(tabla, filasVisibles, 6);
        calcularEstadisticasUsuarios();
    }
    
    inputBusqueda.addEventListener('input', filtrarTabla);
    if (selectCargo) selectCargo.addEventListener('change', filtrarTabla);
    if (selectActivo) selectActivo.addEventListener('change', filtrarTabla);
    if (inputFecha) inputFecha.addEventListener('change', filtrarTabla);
    
    const btnLimpiar = document.querySelector('.filters a[href*="gestion_usuarios"]');
    if (btnLimpiar) {
        btnLimpiar.addEventListener('click', function(e) {
            e.preventDefault();
            inputBusqueda.value = '';
            if (selectCargo) selectCargo.value = '';
            if (selectActivo) selectActivo.value = '';
            if (inputFecha) {
                inputFecha.value = '';
                const filterFechaGroup = document.querySelector('#filter-fecha-group');
                if (filterFechaGroup) filterFechaGroup.style.display = 'none';
            }
            
            // Limpiar indicador visual de cards
            document.querySelectorAll('.cards .card').forEach(card => {
                card.classList.remove('active');
            });
            
            filtrarTabla();
        });
    }
    
    calcularEstadisticasUsuarios();
}

// Filtros para CLIENTES
function initFiltrosClientes() {
    const inputBusqueda = document.querySelector('#busqueda');
    const selectRepresentante = document.querySelector('#filtro-representante');
    const selectContacto = document.querySelector('#filtro-contacto');
    const tabla = document.querySelector('#tabla-clientes tbody');
    
    if (!inputBusqueda || !tabla) return;
    
    const todasLasFilas = Array.from(tabla.querySelectorAll('tr'));
    const totalOriginal = todasLasFilas.filter(f => !f.querySelector('td[colspan]')).length;
    
    function filtrarTabla() {
        const textoBusqueda = inputBusqueda.value.toLowerCase().trim();
        const filtroRep = selectRepresentante ? selectRepresentante.value : '';
        const filtroContacto = selectContacto ? selectContacto.value : '';
        
        let filasVisibles = 0;
        
        todasLasFilas.forEach(function(fila) {
            if (fila.querySelector('td[colspan]')) {
                fila.style.display = 'none';
                return;
            }
            
            const celdas = fila.querySelectorAll('td');
            const nombreCliente = celdas[0]?.textContent.toLowerCase() || '';
            const representantes = celdas[1]?.textContent.toLowerCase() || '';
            const rut = celdas[2]?.textContent.toLowerCase() || '';
            const telefono = celdas[3]?.textContent.toLowerCase() || '';
            const email = celdas[4]?.textContent.toLowerCase() || '';
            
            const coincideTexto = textoBusqueda === '' || 
                nombreCliente.includes(textoBusqueda) ||
                representantes.includes(textoBusqueda) ||
                rut.includes(textoBusqueda) ||
                telefono.includes(textoBusqueda) ||
                email.includes(textoBusqueda);
            
            let coincideRep = true;
            if (filtroRep) {
                if (filtroRep === 'con') {
                    coincideRep = !representantes.includes('sin representantes');
                } else if (filtroRep === 'sin') {
                    coincideRep = representantes.includes('sin representantes');
                }
            }
            
            let coincideContacto = true;
            if (filtroContacto) {
                if (filtroContacto === 'email') {
                    coincideContacto = !email.includes('-');
                } else if (filtroContacto === 'telefono') {
                    coincideContacto = !telefono.includes('-');
                } else if (filtroContacto === 'ambos') {
                    coincideContacto = !email.includes('-') && !telefono.includes('-');
                } else if (filtroContacto === 'ninguno') {
                    coincideContacto = email.includes('-') && telefono.includes('-');
                }
            }
            
            if (coincideTexto && coincideRep && coincideContacto) {
                fila.style.display = '';
                filasVisibles++;
            } else {
                fila.style.display = 'none';
            }
        });
        
        const badge = document.querySelector('.filter-badge');
        if (badge) {
            badge.textContent = `${filasVisibles} de ${totalOriginal} clientes`;
            badge.style.backgroundColor = filasVisibles < totalOriginal ? 'var(--naranja-600)' : 'var(--azul-600)';
        }
        
        mostrarMensajeSinResultados(tabla, filasVisibles, 7);
        calcularEstadisticasClientes();
    }
    
    inputBusqueda.addEventListener('input', filtrarTabla);
    if (selectRepresentante) selectRepresentante.addEventListener('change', filtrarTabla);
    if (selectContacto) selectContacto.addEventListener('change', filtrarTabla);
    
    window.limpiarFiltros = function() {
        inputBusqueda.value = '';
        if (selectRepresentante) selectRepresentante.value = '';
        if (selectContacto) selectContacto.value = '';
        filtrarTabla();
    };
    
    calcularEstadisticasClientes();
}

// Filtros para MATERIALES
function initFiltrosMateriales() {
    const inputBusqueda = document.querySelector('#busqueda');
    const selectCategoria = document.querySelector('#categoria');
    const tabla = document.querySelector('#tabla-materiales tbody');
    
    if (!inputBusqueda || !tabla) return;
    
    const todasLasFilas = Array.from(tabla.querySelectorAll('tr'));
    
    function filtrarTabla() {
        const textoBusqueda = inputBusqueda.value.toLowerCase().trim();
        const categoriaSeleccionada = selectCategoria ? selectCategoria.value : '';
        
        let filasVisibles = 0;
        
        todasLasFilas.forEach(function(fila) {
            if (fila.querySelector('td[colspan]')) {
                fila.style.display = 'none';
                return;
            }
            
            const textoFila = fila.textContent.toLowerCase();
            const coincideTexto = textoBusqueda === '' || textoFila.includes(textoBusqueda);
            
            let coincideCategoria = true;
            if (categoriaSeleccionada) {
                const categoriaPill = fila.querySelector('td:nth-child(3)');
                if (categoriaPill) {
                    coincideCategoria = categoriaPill.textContent.toLowerCase().includes(categoriaSeleccionada.toLowerCase());
                }
            }
            
            if (coincideTexto && coincideCategoria) {
                fila.style.display = '';
                filasVisibles++;
            } else {
                fila.style.display = 'none';
            }
        });
        
        mostrarMensajeSinResultados(tabla, filasVisibles, 7);
        calcularEstadisticasMateriales();
    }
    
    inputBusqueda.addEventListener('input', filtrarTabla);
    if (selectCategoria) selectCategoria.addEventListener('change', filtrarTabla);

    window.limpiarFiltros = function() {
        document.getElementById('busqueda').value = '';
        document.getElementById('estado').value = '';
        document.getElementById('cliente').value = '';
        window.location.href = '{% url "cotizaciones:lista" %}';
        };

    calcularEstadisticasMateriales();
}

// Filtros para SERVICIOS
function initFiltrosServicios() {
    const inputBusqueda = document.querySelector('#busqueda');
    const selectCategoria = document.querySelector('#categoria');
    const tabla = document.querySelector('#tabla-servicios tbody');
    
    if (!inputBusqueda || !tabla) return;
    
    const todasLasFilas = Array.from(tabla.querySelectorAll('tr'));
    
    function filtrarTabla() {
        const textoBusqueda = inputBusqueda.value.toLowerCase().trim();
        const categoriaIdSeleccionada = selectCategoria ? selectCategoria.value : '';
        
        let filasVisibles = 0;
        
        todasLasFilas.forEach(function(fila) {
            if (fila.querySelector('td[colspan]')) {
                fila.style.display = 'none';
                return;
            }
            
            const celdas = fila.querySelectorAll('td');
            
            // Buscar en todas las celdas para el texto
            const textoFila = fila.textContent.toLowerCase();
            const coincideTexto = textoBusqueda === '' || textoFila.includes(textoBusqueda);
            
            // Filtro de categoría
            let coincideCategoria = true;
            if (categoriaIdSeleccionada) {
                // Obtener el texto de la opción seleccionada
                const optionSeleccionada = selectCategoria.options[selectCategoria.selectedIndex];
                const nombreCategoriaSeleccionada = optionSeleccionada ? optionSeleccionada.text.toLowerCase().trim() : '';
                
                // Obtener el texto de la celda de categoría (columna 2, índice 1)
                const categoriaCell = celdas[1];
                const categoriaCellTexto = categoriaCell ? categoriaCell.textContent.toLowerCase().trim() : '';
                
                // Comparar
                coincideCategoria = categoriaCellTexto.includes(nombreCategoriaSeleccionada);
            }
            
            if (coincideTexto && coincideCategoria) {
                fila.style.display = '';
                filasVisibles++;
            } else {
                fila.style.display = 'none';
            }
        });
        
        mostrarMensajeSinResultados(tabla, filasVisibles, 7);
        calcularEstadisticasServicios();
    }
    
    inputBusqueda.addEventListener('input', filtrarTabla);
    if (selectCategoria) selectCategoria.addEventListener('change', filtrarTabla);

    window.limpiarFiltros = function() {
        inputBusqueda.value = '';
        if (selectCategoria) selectCategoria.value = '';
        filtrarTabla();
    };
    
    calcularEstadisticasServicios();
}

// Funciones auxiliares
function actualizarContadorResultados(cantidad) {
    const contador = document.querySelector('.actions-right .muted');
    if (contador) {
        contador.textContent = `${cantidad} resultado(s)`;
    }
}

function mostrarMensajeSinResultados(tabla, cantidad, colspan) {
    let filaSinResultados = tabla.querySelector('.fila-sin-resultados');
    
    if (cantidad === 0) {
        if (!filaSinResultados) {
            filaSinResultados = document.createElement('tr');
            filaSinResultados.className = 'fila-sin-resultados';
            filaSinResultados.innerHTML = `
                <td colspan="${colspan}" style="text-align:center; padding:40px;">
                    <div class="muted">
                        <h3>😕 No se encontraron resultados</h3>
                        <p>Intenta cambiar los filtros de búsqueda.</p>
                    </div>
                </td>
            `;
            tabla.appendChild(filaSinResultados);
        }
        filaSinResultados.style.display = '';
    } else if (filaSinResultados) {
        filaSinResultados.style.display = 'none';
    }
}

// Calcular Estadisticas
function calcularEstadisticasUsuarios() {
    const tabla = document.querySelector('.tabla-usuarios tbody');
    if (!tabla) return;
    
    const filasVisibles = Array.from(tabla.querySelectorAll('tr'))
        .filter(f => f.style.display !== 'none' && !f.querySelector('td[colspan]'));
    
    let totalEmpleados = filasVisibles.length;
    let empleadosActivos = 0;
    let empleadosInactivos = 0;
    const cargosSet = new Set();

    filasVisibles.forEach(fila => {
        const celdas = fila.querySelectorAll('td');
        
        // Cargo (columna 2) - para contar categorías únicas
        const cargoPill = celdas[2]?.querySelector('.pill');
        if (cargoPill) {
            cargosSet.add(cargoPill.textContent.trim());
        }
        
        // Estado (columna 4)
        const estadoPill = celdas[4]?.querySelector('.pill');
        if (estadoPill) {
            if (estadoPill.classList.contains('activo')) {
                empleadosActivos++;
            } else {
                empleadosInactivos++;
            }
        }
    });

    // Calcular porcentaje de activos
    const porcentajeActivos = totalEmpleados > 0 
        ? Math.round((empleadosActivos / totalEmpleados) * 100) 
        : 0;

    // Actualizar KPIs en las tarjetas
    const kpis = document.querySelectorAll('.cards .card');
    if (kpis.length >= 4) {
        // Total Empleados
        const kpiTotal = kpis[0].querySelector('.kpi');
        if (kpiTotal) kpiTotal.textContent = totalEmpleados;
        
        // Activos
        const kpiActivos = kpis[1].querySelector('.kpi');
        if (kpiActivos) kpiActivos.textContent = empleadosActivos;
        
        const mutedActivos = kpis[1].querySelector('.muted');
        if (mutedActivos) mutedActivos.textContent = `${porcentajeActivos}% del total`;
        
        // Inactivos
        const kpiInactivos = kpis[2].querySelector('.kpi');
        if (kpiInactivos) kpiInactivos.textContent = empleadosInactivos;
        
        // Nota: El KPI "Nuevos (30d)" no se puede calcular con filtros en tiempo real
        // ya que requiere datos de fecha_creacion que no están visibles en la tabla
    }
}

function calcularEstadisticasClientes() {
    const tabla = document.querySelector('#tabla-clientes tbody');
    if (!tabla) return;
    
    const filasVisibles = Array.from(tabla.querySelectorAll('tr'))
        .filter(f => f.style.display !== 'none' && !f.querySelector('td[colspan]'));
    
    let conRepresentantes = 0;
    let conEmail = 0;
    let conTelefono = 0;

    filasVisibles.forEach(fila => {
        const celdas = fila.querySelectorAll('td');
        
        const repText = celdas[1]?.textContent || '';
        if (!repText.includes('Sin representantes')) conRepresentantes++;
        
        const telText = celdas[3]?.textContent.trim() || '';
        if (telText !== '-') conTelefono++;
        
        const emailText = celdas[4]?.textContent.trim() || '';
        if (emailText !== '-') conEmail++;
    });

    const statConNom = document.getElementById('stat-con-nom');
    const statConRep = document.getElementById('stat-con-rep');
    const statConEmail = document.getElementById('stat-con-email');
    const statConTel = document.getElementById('stat-con-tel');
    
    if (statConNom) statConNom.textContent = filasVisibles.length;
    if (statConRep) statConRep.textContent = conRepresentantes;
    if (statConEmail) statConEmail.textContent = conEmail;
    if (statConTel) statConTel.textContent = conTelefono;
}

function calcularEstadisticasMateriales() {
    const tabla = document.querySelector('#tabla-materiales tbody');
    if (!tabla) return;
    
    const filasVisibles = Array.from(tabla.querySelectorAll('tr'))
        .filter(f => f.style.display !== 'none' && !f.querySelector('td[colspan]'));
    
    let totalMateriales = filasVisibles.length;
    let materialesActivos = 0;
    let sumaPrecios = 0;
    const categoriasSet = new Set();

    filasVisibles.forEach(fila => {
        const celdas = fila.querySelectorAll('td');
        
        // Categoría (columna 2)
        const categoriaText = celdas[2]?.textContent.trim() || '';
        if (!categoriaText.includes('Sin categoría')) {
            categoriasSet.add(categoriaText);
        }
        
        // Precio (columna 3) - extraer solo números
        const precioText = celdas[3]?.textContent.trim() || '0';
        const precio = parseFloat(precioText.replace(/[^0-9]/g, '')) || 0;
        sumaPrecios += precio;
        
        // Estado (columna 5)
        const estadoCell = celdas[5];
        if (estadoCell && estadoCell.textContent.includes('Activo')) {
            materialesActivos++;
        }
    });

    const precioPromedio = totalMateriales > 0 ? Math.round(sumaPrecios / totalMateriales) : 0;

    // Actualizar KPIs
    const kpis = document.querySelectorAll('.card .kpi');
    if (kpis.length >= 4) {
        kpis[0].textContent = totalMateriales; // Total
        kpis[1].textContent = categoriasSet.size; // Categorías
        kpis[2].textContent = materialesActivos; // Activos
        kpis[3].textContent = '$' + precioPromedio.toLocaleString('es-CL'); // Promedio
    }
}

function calcularEstadisticasServicios() {
    const tabla = document.querySelector('#tabla-servicios tbody');
    if (!tabla) return;
    
    const filasVisibles = Array.from(tabla.querySelectorAll('tr'))
        .filter(f => f.style.display !== 'none' && !f.querySelector('td[colspan]'));
    
    let totalServicios = filasVisibles.length;
    let serviciosParametrizables = 0;
    let serviciosActivos = 0;
    const categoriasSet = new Set();

    filasVisibles.forEach(fila => {
        const celdas = fila.querySelectorAll('td');
        
        // Categoría (columna 1)
        const categoriaText = celdas[1]?.textContent.trim() || '';
        if (categoriaText) {
            categoriasSet.add(categoriaText);
        }
        
        // Parametrizable (columna 4)
        const paramCell = celdas[4];
        if (paramCell && paramCell.textContent.includes('Sí')) {
            serviciosParametrizables++;
        }
        
        // Estado (columna 5)
        const estadoCell = celdas[5];
        if (estadoCell && estadoCell.textContent.includes('Activo')) {
            serviciosActivos++;
        }
    });

    // Actualizar KPIs
    const kpis = document.querySelectorAll('.card .kpi');
    if (kpis.length >= 4) {
        kpis[0].textContent = totalServicios; // Total
        kpis[1].textContent = serviciosParametrizables; // Parametrizables
        kpis[2].textContent = categoriasSet.size; // Categorías
        kpis[3].textContent = serviciosActivos; // Activos
    }
}

// INICIALIZACIÓN AUTOMÁTICA DE FILTROS
(function() {
    // Esperar a que el DOM esté listo
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initFiltros);
    } else {
        // El DOM ya está listo
        initFiltros();
    }
    
    function initFiltros() {
        // Detectar qué página es e inicializar filtros correspondientes
        if (document.querySelector('.tabla-usuarios')) {
            
            initFiltrosUsuarios();
        }
        
        if (document.querySelector('#tabla-clientes')) {
            
            initFiltrosClientes();
        }
        
        if (document.querySelector('#tabla-materiales')) {
            
            initFiltrosMateriales();
        }
        
        if (document.querySelector('#tabla-servicios')) {
            
            initFiltrosServicios();
        }
        
        
    }
})();

