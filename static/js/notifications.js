function getCSRFToken() {
  const cookies = document.cookie.split(';');
  for (let cookie of cookies) {
    const [name, value] = cookie.trim().split('=');
    if (name === 'csrftoken') return value;
  }
  return '';
}

const notificationBell = document.getElementById('notification-bell');
const notificationDropdown = document.getElementById('notification-dropdown');
const notificationBadge = document.getElementById('notification-badge');
const notificationList = document.getElementById('notification-list');

// Toggle dropdown
notificationBell?.addEventListener('click', function(e) {
  e.stopPropagation();
  const isVisible = notificationDropdown.style.display === 'block';
  notificationDropdown.style.display = isVisible ? 'none' : 'block';
  if (!isVisible) cargarNotificaciones();
});

// Cerrar al hacer click fuera
document.addEventListener('click', function() {
  if (notificationDropdown) notificationDropdown.style.display = 'none';
});

notificationDropdown?.addEventListener('click', function(e) {
  e.stopPropagation();
});

// Cargar notificaciones
async function cargarNotificaciones() {
  try {
    const response = await fetch('/notificaciones/api/lista/?limit=5');
    const data = await response.json();
    
    if (data.success) {
      actualizarBadge(data.unread_count);
      mostrarNotificaciones(data.notificaciones);
    }
  } catch (error) {
    console.error('Error:', error);
  }
}

function actualizarBadge(count) {
  if (count > 0) {
    notificationBadge.textContent = count;
    notificationBadge.style.display = 'inline-block';
  } else {
    notificationBadge.style.display = 'none';
  }
}

function mostrarNotificaciones(notificaciones) {
  if (notificaciones.length === 0) {
    notificationList.innerHTML = `
      <div class="notification-empty">
        <div class="notification-empty-icon">🔔</div>
        <p>No tienes notificaciones</p>
      </div>
    `;
    return;
  }
  
  notificationList.innerHTML = notificaciones.map(n => `
    <a href="${n.url || '#'}" class="notification-item ${n.leida ? '' : 'unread'}"
       onclick="marcarLeida(event, ${n.id}, '${n.url || ''}')">
      <div class="notification-type-icon ${n.tipo}">
        ${n.tipo === 'info' ? 'ℹ️' : n.tipo === 'success' ? '✅' : n.tipo === 'warning' ? '⚠️' : '❌'}
      </div>
      <div class="notification-content">
        <div class="notification-title">${n.titulo}</div>
        <div class="notification-message">${n.mensaje}</div>
        <div class="notification-time">🕐 ${n.tiempo_relativo || 'Hace un momento'}</div>
      </div>
    </a>
  `).join('');
}

async function marcarLeida(event, notifId, url) {
  event.preventDefault();
  
  try {
    await fetch(`/notificaciones/api/marcar-leida/${notifId}/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCSRFToken() }
    });
    
    if (url) window.location.href = url;
    else cargarNotificaciones();
  } catch (error) {
    console.error('Error:', error);
  }
}

// Marcar todas como leídas
document.getElementById('mark-all-read')?.addEventListener('click', async function(e) {
  e.preventDefault();
  
  try {
    await fetch('/notificaciones/api/marcar-todas-leidas/', {
      method: 'POST',
      headers: { 'X-CSRFToken': getCSRFToken() }
    });
    cargarNotificaciones();
  } catch (error) {
    console.error('Error:', error);
  }
});

// Cargar al inicio
cargarNotificaciones();
setInterval(cargarNotificaciones, 60000); // Cada minuto
