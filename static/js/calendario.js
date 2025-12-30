// ============================================
// CALENDARIO.JS - Sistema de Calendario Completo
// ============================================

(function() {
  'use strict';

  // Estado global
  let mesActual = new Date();
  let diaSeleccionado = null;
  let eventos = {
    trabajos: [],
    mantenciones: [],
    notas: []
  };
  let filtros = {
    trabajos: true,
    mantenciones: true,
    prestamos: true,
    notas: true
  };

  // Elementos del DOM
  const elementos = {
    mesActual: document.getElementById('mes-actual'),
    calendarioGrid: document.getElementById('calendario-grid'),
    eventosDia: document.getElementById('eventos-dia'),
    btnPrevMes: document.getElementById('btn-prev-mes'),
    btnNextMes: document.getElementById('btn-next-mes'),
    btnHoy: document.getElementById('btn-hoy'),
    btnNuevaNota: document.getElementById('btn-nueva-nota'),
    modalNota: document.getElementById('modal-nota'),
    modalEvento: document.getElementById('modal-evento'),
    formNota: document.getElementById('form-nota'),
    filterTrabajos: document.getElementById('filter-trabajos'),
    filterMantenciones: document.getElementById('filter-mantenciones'),
    filterPrestamos: document.getElementById('filter-prestamos'),
    filterNotas: document.getElementById('filter-notas')
  };

  // ============================================
  // INICIALIZACIÓN
  // ============================================

  function init() {
    console.log('✅ Inicializando calendario...');
    
    if (!validarElementos()) {
      console.error('❌ Error: Faltan elementos del DOM');
      return;
    }

    configurarEventListeners();
    cargarEventos();
    renderizarCalendario();
  }

  function validarElementos() {
    return Object.values(elementos).every(el => el !== null);
  }

  function configurarEventListeners() {
    // Navegación del calendario
    elementos.btnPrevMes.addEventListener('click', () => cambiarMes(-1));
    elementos.btnNextMes.addEventListener('click', () => cambiarMes(1));
    elementos.btnHoy.addEventListener('click', irHoy);

    // Filtros
    elementos.filterTrabajos.addEventListener('change', (e) => {
      filtros.trabajos = e.target.checked;
      renderizarCalendario();
    });
    elementos.filterMantenciones.addEventListener('change', (e) => {
      filtros.mantenciones = e.target.checked;
      renderizarCalendario();
    });
    elementos.filterPrestamos.addEventListener('change', (e) => {
      filtros.prestamos = e.target.checked;
      renderizarCalendario();
    });
    elementos.filterNotas.addEventListener('change', (e) => {
      filtros.notas = e.target.checked;
      renderizarCalendario();
    });

    // Modal de nota
    elementos.btnNuevaNota.addEventListener('click', () => abrirModalNota());
    document.getElementById('close-modal-nota').addEventListener('click', cerrarModalNota);
    document.getElementById('btn-cancelar-nota').addEventListener('click', cerrarModalNota);
    elementos.formNota.addEventListener('submit', guardarNota);

    // Modal de evento
    document.getElementById('close-modal-evento').addEventListener('click', cerrarModalEvento);

    // Cerrar modales al hacer click fuera
    window.addEventListener('click', (e) => {
      if (e.target === elementos.modalNota) cerrarModalNota();
      if (e.target === elementos.modalEvento) cerrarModalEvento();
    });
  }

  // ============================================
  // CARGA DE DATOS
  // ============================================

  async function cargarEventos() {
    try {
      const response = await fetch(`/notificaciones/api/calendario-eventos/?mes=${mesActual.getMonth() + 1}&anio=${mesActual.getFullYear()}`);
      
      if (!response.ok) throw new Error('Error al cargar eventos');
      
      const data = await response.json();
      eventos = data;
      
      renderizarCalendario();
      
      console.log('✅ Eventos cargados:', eventos);
    } catch (error) {
      console.error('❌ Error al cargar eventos:', error);
      mostrarError('Error al cargar eventos del calendario');
    }
  }

  // ============================================
  // RENDERIZADO DEL CALENDARIO
  // ============================================

  function renderizarCalendario() {
    const año = mesActual.getFullYear();
    const mes = mesActual.getMonth();

    // Actualizar título
    elementos.mesActual.textContent = mesActual.toLocaleDateString('es-ES', { 
      month: 'long', 
      year: 'numeric' 
    }).replace(/^\w/, c => c.toUpperCase());

    // Limpiar contenedor
    elementos.calendarioGrid.innerHTML = '';

    // Crear cabeceras de días de la semana
    const diasSemana = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];
    diasSemana.forEach(dia => {
      const cabecera = document.createElement('div');
      cabecera.className = 'dia-semana';
      cabecera.textContent = dia;
      elementos.calendarioGrid.appendChild(cabecera);
    });

    // Primer día del mes (0 = domingo, 1 = lunes, etc.)
    let primerDia = new Date(año, mes, 1).getDay();
    const diasDelMes = new Date(año, mes + 1, 0).getDate();
    const diasMesAnterior = new Date(año, mes, 0).getDate();

    // Ajustar para que lunes sea el primer día (0)
    // Si es domingo (0), debe ser 6 (última columna)
    // Si es lunes (1), debe ser 0 (primera columna)
    primerDia = primerDia === 0 ? 6 : primerDia - 1;

    // Días del mes anterior para llenar el inicio
    for (let i = primerDia - 1; i >= 0; i--) {
      const dia = diasMesAnterior - i;
      const fecha = new Date(año, mes - 1, dia);
      crearCeldaDia(dia, fecha, true);
    }

    // Días del mes actual
    for (let dia = 1; dia <= diasDelMes; dia++) {
      const fecha = new Date(año, mes, dia);
      crearCeldaDia(dia, fecha, false);
    }

    // Días del mes siguiente (para completar la última semana)
    const totalCeldas = elementos.calendarioGrid.children.length - 7; // Restar las cabeceras
    const celdasFaltantes = totalCeldas % 7 === 0 ? 0 : 7 - (totalCeldas % 7);
    
    for (let dia = 1; dia <= celdasFaltantes; dia++) {
      const fecha = new Date(año, mes + 1, dia);
      crearCeldaDia(dia, fecha, true);
    }
  }

  function crearCeldaDia(dia, fecha, otroMes) {
    const celda = document.createElement('div');
    celda.className = 'dia-celda';
    
    if (otroMes) {
      celda.classList.add('otro-mes');
    }

    // Marcar hoy
    const hoy = new Date();
    if (fecha.toDateString() === hoy.toDateString()) {
      celda.classList.add('hoy');
    }

    // Marcar día seleccionado
    if (diaSeleccionado && fecha.toDateString() === diaSeleccionado.toDateString()) {
      celda.classList.add('seleccionado');
    }

    // Número del día
    const numero = document.createElement('div');
    numero.className = 'dia-numero';
    numero.textContent = dia;
    celda.appendChild(numero);

    // Contenedor de eventos
    const eventosContainer = document.createElement('div');
    eventosContainer.className = 'dia-eventos';

    // Obtener eventos del día
    const eventosDelDia = obtenerEventosDelDia(fecha);
    const eventosVisibles = eventosDelDia.slice(0, 3);
    const eventosRestantes = eventosDelDia.length - 3;

    // Renderizar eventos
    eventosVisibles.forEach(evento => {
      const eventoMini = crearEventoMini(evento);
      eventosContainer.appendChild(eventoMini);
    });

    // Contador de eventos adicionales
    if (eventosRestantes > 0) {
      const contador = document.createElement('div');
      contador.className = 'evento-contador';
      contador.textContent = `+${eventosRestantes} más`;
      eventosContainer.appendChild(contador);
    }

    celda.appendChild(eventosContainer);

    // Marcar si tiene eventos
    if (eventosDelDia.length > 0) {
      celda.classList.add('tiene-eventos');
    }

    // Click en la celda
    celda.addEventListener('click', () => seleccionarDia(fecha));

    elementos.calendarioGrid.appendChild(celda);
  }

  function crearEventoMini(evento) {
    const div = document.createElement('div');
    div.className = `evento-mini ${evento.tipo}`;
    
    if (evento.tipo === 'nota' && evento.color) {
      div.style.background = evento.color;
    }

    let icono = '';
    switch (evento.tipo) {
      case 'trabajo':
        icono = '🔧';
        break;
      case 'mantencion':
        icono = '⚙️';
        break;
      case 'prestamo':
        icono = '📦';
        break;
      case 'nota':
        icono = '📝';
        break;
    }

    div.innerHTML = `<span>${icono}</span><span>${evento.titulo}</span>`;
    
    div.addEventListener('click', (e) => {
      e.stopPropagation();
      mostrarDetalleEvento(evento);
    });

    return div;
  }

  function obtenerEventosDelDia(fecha) {
    const fechaStr = formatearFecha(fecha);
    const eventosDelDia = [];

    // Trabajos
    if (filtros.trabajos && eventos.trabajos) {
      eventos.trabajos
        .filter(t => t.fecha === fechaStr)
        .forEach(t => eventosDelDia.push({
          ...t,
          tipo: 'trabajo',
          titulo: `Cot. ${t.numero}`
        }));
    }

    // Mantenciones
    if (filtros.mantenciones && eventos.mantenciones) {
      eventos.mantenciones
        .filter(m => m.fecha === fechaStr)
        .forEach(m => eventosDelDia.push({
          ...m,
          tipo: 'mantencion',
          titulo: m.material
        }));
    }
    
    // Préstamos
    if (filtros.prestamos && eventos.prestamos) {
      eventos.prestamos
        .filter(p => p.fecha === fechaStr)
        .forEach(p => eventosDelDia.push({
          ...p,
          tipo: 'prestamo',
          titulo: `${p.codigo} - ${p.prestado_a}`
        }));
    }

    // Notas
    if (filtros.notas && eventos.notas) {
      eventos.notas
        .filter(n => n.fecha === fechaStr)
        .forEach(n => eventosDelDia.push({
          ...n,
          tipo: 'nota'
        }));
    }

    return eventosDelDia.sort((a, b) => {
      const orden = { trabajo: 1, prestamo: 2, mantencion: 3, nota: 4 };
      return orden[a.tipo] - orden[b.tipo];
    });
  }

  // ============================================
  // SELECCIÓN DE DÍA Y EVENTOS
  // ============================================

  function seleccionarDia(fecha) {
    diaSeleccionado = fecha;
    renderizarCalendario();
    mostrarEventosDia(fecha);
  }

  function mostrarEventosDia(fecha) {
    const eventosDelDia = obtenerEventosDelDia(fecha);

    if (eventosDelDia.length === 0) {
      elementos.eventosDia.innerHTML = '<p class="muted">No hay eventos en este día</p>';
      return;
    }

    elementos.eventosDia.innerHTML = '';

    eventosDelDia.forEach(evento => {
      const eventoDetalle = crearEventoDetalle(evento);
      elementos.eventosDia.appendChild(eventoDetalle);
    });
  }

  function crearEventoDetalle(evento) {
    const div = document.createElement('div');
    div.className = `evento-detalle ${evento.tipo}`;
    
    if (evento.tipo === 'nota' && evento.color) {
      div.style.borderLeftColor = evento.color;
    }

    let contenido = '';

    if (evento.tipo === 'trabajo') {
      // Determinar el badge del estado
      let estadoBadge = '';
      let estadoClass = '';
      let estadoTexto = '';
      
      if (evento.estado) {
        switch(evento.estado) {
          case 'aprobada':
            estadoClass = 'aprobada';
            estadoTexto = 'Aprobada';
            break;
          case 'enviada':
            estadoClass = 'enviada';
            estadoTexto = 'Enviada';
            break;
          case 'finalizada':
            estadoClass = 'aprobada';
            estadoTexto = 'Finalizada';
            break;
          default:
            estadoClass = evento.estado;
            estadoTexto = evento.estado.charAt(0).toUpperCase() + evento.estado.slice(1);
        }
        estadoBadge = `<span class="pill ${estadoClass}">${estadoTexto}</span>`;
      }
      
      contenido = `
        <div class="evento-detalle-header">
          <h4>🔧 Cotización ${evento.numero}</h4>
          <div style="display: flex; gap: 8px;">
            ${estadoBadge}
            <span class="evento-detalle-tipo trabajo">Trabajo</span>
          </div>
        </div>
        <p><strong>Referencia:</strong> ${evento.referencia}</p>
        <p><strong>Cliente:</strong> ${evento.cliente}</p>
        <p><strong>Lugar:</strong> ${evento.lugar}</p>
        <div class="evento-detalle-footer">
          <span>📅 ${formatearFechaLegible(evento.fecha)}</span>
          <div class="evento-acciones">
            <a href="/cotizaciones/${evento.id}/" class="btn small">Ver Detalles</a>
          </div>
        </div>
      `;
    } else if (evento.tipo === 'mantencion') {
      contenido = `
        <div class="evento-detalle-header">
          <h4>⚙️ ${evento.material}</h4>
          <span class="evento-detalle-tipo mantencion">Mantención</span>
        </div>
        <p><strong>Tipo:</strong> ${evento.tipo_mantenimiento}</p>
        ${evento.descripcion ? `<p>${evento.descripcion}</p>` : ''}
        <div class="evento-detalle-footer">
          <span>📅 ${formatearFechaLegible(evento.fecha)}</span>
          <div class="evento-acciones">
            <button class="btn small" onclick="registrarMantencion(${evento.material_id})">Registrar</button>
          </div>
        </div>
      `;
    } else if (evento.tipo === 'prestamo') {
      // Determinar badge de urgencia
      let urgenciaBadge = '';
      if (evento.urgencia === 'vencido') {
        urgenciaBadge = '<span class="pill rechazada">🚨 VENCIDO</span>';
      } else if (evento.urgencia === 'proximo') {
        urgenciaBadge = '<span class="pill vencida">⚠️ PRÓXIMO</span>';
      } else {
        urgenciaBadge = '<span class="pill enviada">✓ PROGRAMADO</span>';
      }
      
      contenido = `
        <div class="evento-detalle-header">
          <h4>📦 ${evento.material} (${evento.codigo})</h4>
          <div style="display: flex; gap: 8px;">
            ${urgenciaBadge}
            <span class="evento-detalle-tipo" style="background: #8b5cf6; color: white;">Préstamo</span>
          </div>
        </div>
        <p><strong>Prestado a:</strong> ${evento.prestado_a}</p>
        <p><strong>Estado:</strong> ${evento.estado_texto}</p>
        ${evento.observaciones ? `<p><strong>Observaciones:</strong> ${evento.observaciones}</p>` : ''}
        <div class="evento-detalle-footer">
          <span>📅 Devolución: ${formatearFechaLegible(evento.fecha)}</span>
          <div class="evento-acciones">
            <a href="/cotizaciones/prestamos/" class="btn small">Ver Préstamos</a>
          </div>
        </div>
      `;
    } else if (evento.tipo === 'nota') {
      const prioridadClass = evento.prioridad || 'media';
      const prioridadIcono = prioridadClass === 'alta' ? '🔴' : prioridadClass === 'media' ? '🟡' : '🟢';
      
      contenido = `
        <div class="evento-detalle-header">
          <h4>📝 ${evento.titulo}</h4>
          <span class="prioridad-badge ${prioridadClass}">${prioridadIcono} ${prioridadClass.toUpperCase()}</span>
        </div>
        ${evento.descripcion ? `<p>${evento.descripcion}</p>` : ''}
        <div class="evento-detalle-footer">
          <span>📅 ${formatearFechaLegible(evento.fecha)}</span>
          <div class="evento-acciones">
            <button class="btn small secondary" onclick="editarNota(${evento.id})">Editar</button>
            <button class="btn small danger" onclick="eliminarNota(${evento.id})">Eliminar</button>
          </div>
        </div>
      `;
    }

    div.innerHTML = contenido;
    div.addEventListener('click', () => mostrarDetalleEvento(evento));

    return div;
  }

  function mostrarDetalleEvento(evento) {
    const modal = elementos.modalEvento;
    const titulo = document.getElementById('evento-titulo');
    const contenido = document.getElementById('evento-contenido');

    titulo.textContent = evento.titulo;

    let html = '';

    if (evento.tipo === 'trabajo') {
      html = `
        <div class="evento-info-grid">
          <div class="evento-info-item">
            <span class="evento-info-label">Número</span>
            <span class="evento-info-value">Cot. ${evento.numero}</span>
          </div>
          <div class="evento-info-item">
            <span class="evento-info-label">Cliente</span>
            <span class="evento-info-value">${evento.cliente}</span>
          </div>
          <div class="evento-info-item">
            <span class="evento-info-label">Fecha</span>
            <span class="evento-info-value">${formatearFechaLegible(evento.fecha)}</span>
          </div>
          <div class="evento-info-item">
            <span class="evento-info-label">Lugar</span>
            <span class="evento-info-value">${evento.lugar}</span>
          </div>
        </div>
        <div class="evento-info-item">
          <span class="evento-info-label">Referencia</span>
          <span class="evento-info-value">${evento.referencia}</span>
        </div>
        <div class="actions" style="margin-top: 20px;">
          <a href="/cotizaciones/${evento.id}/" class="btn">Ver Cotización Completa</a>
        </div>
      `;
    } else if (evento.tipo === 'mantencion') {
      html = `
        <div class="evento-info-grid">
          <div class="evento-info-item">
            <span class="evento-info-label">Material</span>
            <span class="evento-info-value">${evento.material}</span>
          </div>
          <div class="evento-info-item">
            <span class="evento-info-label">Tipo</span>
            <span class="evento-info-value">${evento.tipo_mantenimiento}</span>
          </div>
          <div class="evento-info-item">
            <span class="evento-info-label">Fecha</span>
            <span class="evento-info-value">${formatearFechaLegible(evento.fecha)}</span>
          </div>
        </div>
        ${evento.descripcion ? `
          <div class="evento-info-item" style="margin-top: 16px;">
            <span class="evento-info-label">Descripción</span>
            <p style="margin-top: 8px;">${evento.descripcion}</p>
          </div>
        ` : ''}
        <div class="actions" style="margin-top: 20px;">
          <button class="btn" onclick="registrarMantencion(${evento.material_id})">Registrar Mantención</button>
        </div>
      `;
    } else if (evento.tipo === 'nota') {
      const prioridadClass = evento.prioridad || 'media';
      const prioridadIcono = prioridadClass === 'alta' ? '🔴' : prioridadClass === 'media' ? '🟡' : '🟢';
      
      html = `
        <div class="evento-info-grid">
          <div class="evento-info-item">
            <span class="evento-info-label">Fecha</span>
            <span class="evento-info-value">${formatearFechaLegible(evento.fecha)}</span>
          </div>
          <div class="evento-info-item">
            <span class="evento-info-label">Prioridad</span>
            <span class="prioridad-badge ${prioridadClass}">${prioridadIcono} ${prioridadClass.toUpperCase()}</span>
          </div>
        </div>
        ${evento.descripcion ? `
          <div class="evento-info-item" style="margin-top: 16px;">
            <span class="evento-info-label">Descripción</span>
            <p style="margin-top: 8px;">${evento.descripcion}</p>
          </div>
        ` : ''}
        <div class="actions" style="margin-top: 20px;">
          <button class="btn secondary" onclick="editarNota(${evento.id})">Editar</button>
          <button class="btn danger" onclick="eliminarNota(${evento.id})">Eliminar</button>
        </div>
      `;
    }

    contenido.innerHTML = html;
    modal.classList.add('show');
  }

  // ============================================
  // GESTIÓN DE NOTAS
  // ============================================

  function abrirModalNota(nota = null) {
    const modal = elementos.modalNota;
    const form = elementos.formNota;
    const titulo = document.getElementById('modal-nota-titulo');

    if (nota) {
      // Editar
      titulo.textContent = 'Editar Nota';
      document.getElementById('nota-id').value = nota.id;
      document.getElementById('nota-titulo').value = nota.titulo;
      document.getElementById('nota-descripcion').value = nota.descripcion || '';
      document.getElementById('nota-fecha').value = nota.fecha;
      document.getElementById('nota-prioridad').value = nota.prioridad || 'media';
      
      // Seleccionar color
      const colorInput = document.querySelector(`input[name="color"][value="${nota.color || '#3b82f6'}"]`);
      if (colorInput) colorInput.checked = true;
    } else {
      // Crear nueva
      titulo.textContent = 'Nueva Nota';
      form.reset();
      document.getElementById('nota-id').value = '';
      
      // Fecha por defecto: día seleccionado o hoy
      const fechaDefecto = diaSeleccionado || new Date();
      document.getElementById('nota-fecha').value = formatearFecha(fechaDefecto);
    }

    modal.classList.add('show');
  }

  function cerrarModalNota() {
    elementos.modalNota.classList.remove('show');
    elementos.formNota.reset();
  }

  function cerrarModalEvento() {
    elementos.modalEvento.classList.remove('show');
  }

  async function guardarNota(e) {
    e.preventDefault();

    const formData = new FormData(elementos.formNota);
    const notaId = formData.get('nota_id');
    const url = notaId 
      ? `/notificaciones/api/nota/${notaId}/editar/`
      : '/notificaciones/api/nota/crear/';

    try {
      const response = await fetch(url, {
        method: 'POST',
        body: formData,
        headers: {
          'X-CSRFToken': getCookie('csrftoken')
        }
      });

      if (!response.ok) throw new Error('Error al guardar nota');

      const data = await response.json();

      if (data.success) {
        cerrarModalNota();
        await cargarEventos();
        mostrarMensaje('Nota guardada correctamente', 'success');
      } else {
        throw new Error(data.error || 'Error desconocido');
      }
    } catch (error) {
      console.error('❌ Error al guardar nota:', error);
      mostrarError('Error al guardar la nota');
    }
  }

  // ============================================
  // FUNCIONES PÚBLICAS (para botones en HTML)
  // ============================================

  window.editarNota = async function(notaId) {
    try {
      const response = await fetch(`/notificaciones/api/nota/${notaId}/`);
      if (!response.ok) throw new Error('Error al obtener nota');
      
      const nota = await response.json();
      cerrarModalEvento();
      abrirModalNota(nota);
    } catch (error) {
      console.error('❌ Error al cargar nota:', error);
      mostrarError('Error al cargar la nota');
    }
  };

  window.eliminarNota = async function(notaId) {
    if (!confirm('¿Estás seguro de eliminar esta nota?')) return;

    try {
      const response = await fetch(`/notificaciones/api/nota/${notaId}/eliminar/`, {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCookie('csrftoken')
        }
      });

      if (!response.ok) throw new Error('Error al eliminar nota');

      cerrarModalEvento();
      await cargarEventos();
      mostrarMensaje('Nota eliminada correctamente', 'success');
    } catch (error) {
      console.error('❌ Error al eliminar nota:', error);
      mostrarError('Error al eliminar la nota');
    }
  };

  window.registrarMantencion = function(materialId) {
    window.location.href = `/cotizaciones/material/${materialId}/registrar-mantenimiento/`;
  };

  // ============================================
  // NAVEGACIÓN DEL CALENDARIO
  // ============================================

  function cambiarMes(delta) {
    mesActual.setMonth(mesActual.getMonth() + delta);
    cargarEventos();
  }

  function irHoy() {
    mesActual = new Date();
    diaSeleccionado = new Date();
    cargarEventos();
    mostrarEventosDia(diaSeleccionado);
  }

  // ============================================
  // UTILIDADES
  // ============================================

  function formatearFecha(fecha) {
    const año = fecha.getFullYear();
    const mes = String(fecha.getMonth() + 1).padStart(2, '0');
    const dia = String(fecha.getDate()).padStart(2, '0');
    return `${año}-${mes}-${dia}`;
  }

  function formatearFechaLegible(fechaStr) {
    const fecha = new Date(fechaStr + 'T00:00:00');
    return fecha.toLocaleDateString('es-ES', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    }).replace(/^\w/, c => c.toUpperCase());
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

  function mostrarMensaje(mensaje, tipo = 'info') {
    // Implementar toast o alert
    alert(mensaje);
  }

  function mostrarError(mensaje) {
    mostrarMensaje(mensaje, 'error');
  }

  // ============================================
  // INICIAR AL CARGAR
  // ============================================

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();