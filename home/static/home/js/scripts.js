// ============================================
// SCRIPTS.JS - Landing Page Interactiva
// ============================================

// Función para el carrusel de reseñas
function scrollCarrusel(direction) {
  const carrusel = document.getElementById('carrusel-scroll');
  const scrollAmount = 220; // Ancho de una tarjeta + gap
  
  if (direction === 1) {
    carrusel.scrollBy({ left: scrollAmount, behavior: 'smooth' });
  } else {
    carrusel.scrollBy({ left: -scrollAmount, behavior: 'smooth' });
  }
}

// Auto-scroll del carrusel (opcional)
let autoScrollInterval;

function startAutoScroll() {
  const carrusel = document.getElementById('carrusel-scroll');
  
  autoScrollInterval = setInterval(() => {
    // Si llegamos al final, volver al inicio
    if (carrusel.scrollLeft + carrusel.clientWidth >= carrusel.scrollWidth - 10) {
      carrusel.scrollTo({ left: 0, behavior: 'smooth' });
    } else {
      carrusel.scrollBy({ left: 220, behavior: 'smooth' });
    }
  }, 4000); // Cada 4 segundos
}

function stopAutoScroll() {
  clearInterval(autoScrollInterval);
}

// Iniciar auto-scroll al cargar
document.addEventListener('DOMContentLoaded', function() {
  const carrusel = document.getElementById('carrusel-scroll');
  
  // Iniciar auto-scroll
  startAutoScroll();
  
  // Detener auto-scroll al hacer hover
  carrusel.addEventListener('mouseenter', stopAutoScroll);
  carrusel.addEventListener('mouseleave', startAutoScroll);
  
  // Scroll suave para enlaces internos
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      e.preventDefault();
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        target.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        });
      }
    });
  });
  
  // Animación de entrada para elementos
  const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -100px 0px'
  };
  
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('fade-in');
      }
    });
  }, observerOptions);
  
  // Observar elementos que queremos animar
  document.querySelectorAll('.card, .interactive-banner, .zona-resenas').forEach(el => {
    observer.observe(el);
  });
  
  // Efecto parallax suave en el banner
  const banner = document.querySelector('.interactive-banner');
  if (banner) {
    window.addEventListener('scroll', () => {
      const scrolled = window.pageYOffset;
      const rate = scrolled * 0.3;
      banner.style.backgroundPositionY = `calc(20% + ${rate}px)`;
    });
  }
  
  // Contador animado para el número de clientes
  animateCounter();
});

// Función para animar el contador
function animateCounter() {
  const counter = document.querySelector('.resena-destacada h2');
  if (!counter) return;
  
  const target = 20;
  let current = 0;
  const increment = 1;
  const duration = 2000;
  const steps = target / increment;
  const stepDuration = duration / steps;
  
  const timer = setInterval(() => {
    current += increment;
    counter.textContent = `+${current}`;
    
    if (current >= target) {
      clearInterval(timer);
    }
  }, stepDuration);
}

// Sistema de formulario de contacto (si se agrega)
function enviarFormularioContacto(event) {
  event.preventDefault();
  
  const form = event.target;
  const formData = new FormData(form);
  
  // Aquí iría la lógica de envío del formulario
  alert('¡Gracias por contactarnos! Te responderemos pronto.');
  form.reset();
}

// Validación básica de formularios
function validarFormulario(form) {
  let isValid = true;
  const inputs = form.querySelectorAll('input[required], textarea[required]');
  
  inputs.forEach(input => {
    if (!input.value.trim()) {
      input.classList.add('error');
      isValid = false;
    } else {
      input.classList.remove('error');
    }
  });
  
  return isValid;
}

// Sistema de notificaciones toast (opcional)
function mostrarNotificacion(mensaje, tipo = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast toast-${tipo}`;
  toast.innerHTML = `
    <div class="toast-icon">
      ${tipo === 'success' ? '✓' : tipo === 'error' ? '✕' : 'ℹ'}
    </div>
    <div class="toast-content">
      <p class="toast-message">${mensaje}</p>
    </div>
    <button class="toast-close" onclick="this.parentElement.remove()">✕</button>
  `;
  
  document.body.appendChild(toast);
  
  // Auto-remover después de 5 segundos
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 5000);
}

// Lazy loading de imágenes
function lazyLoadImages() {
  const images = document.querySelectorAll('img[data-src]');
  
  const imageObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const img = entry.target;
        img.src = img.dataset.src;
        img.removeAttribute('data-src');
        observer.unobserve(img);
      }
    });
  });
  
  images.forEach(img => imageObserver.observe(img));
}

// Inicializar lazy loading
document.addEventListener('DOMContentLoaded', lazyLoadImages);

// Prevenir comportamiento por defecto en enlaces vacíos
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('a[href="#"]').forEach(link => {
    link.addEventListener('click', function(e) {
      if (this.getAttribute('href') === '#') {
        e.preventDefault();
      }
    });
  });
});

// Sistema de búsqueda en tiempo real (si se agrega barra de búsqueda)
let searchTimeout;
function buscarServicios(query) {
  clearTimeout(searchTimeout);
  
  searchTimeout = setTimeout(() => {
    const servicios = document.querySelectorAll('.card');
    const searchLower = query.toLowerCase();
    
    servicios.forEach(servicio => {
      const titulo = servicio.querySelector('.card-title').textContent.toLowerCase();
      const descripcion = servicio.querySelector('.card-text').textContent.toLowerCase();
      
      if (titulo.includes(searchLower) || descripcion.includes(searchLower)) {
        servicio.style.display = '';
      } else {
        servicio.style.display = 'none';
      }
    });
  }, 300);
}

// Modo oscuro toggle (opcional)
function toggleDarkMode() {
  document.body.classList.toggle('dark-mode');
  localStorage.setItem('darkMode', document.body.classList.contains('dark-mode'));
}

// Cargar preferencia de modo oscuro
document.addEventListener('DOMContentLoaded', function() {
  if (localStorage.getItem('darkMode') === 'true') {
    document.body.classList.add('dark-mode');
  }
});

// Sistema de favoritos (localStorage)
function toggleFavorito(servicioId) {
  let favoritos = JSON.parse(localStorage.getItem('favoritos') || '[]');
  
  const index = favoritos.indexOf(servicioId);
  if (index === -1) {
    favoritos.push(servicioId);
    mostrarNotificacion('Servicio agregado a favoritos', 'success');
  } else {
    favoritos.splice(index, 1);
    mostrarNotificacion('Servicio removido de favoritos', 'info');
  }
  
  localStorage.setItem('favoritos', JSON.stringify(favoritos));
  actualizarIconosFavoritos();
}

function actualizarIconosFavoritos() {
  const favoritos = JSON.parse(localStorage.getItem('favoritos') || '[]');
  // Actualizar UI según favoritos guardados
}

// Compartir en redes sociales
function compartirEnRedes(red, url, texto) {
  let shareUrl;
  
  switch(red) {
    case 'facebook':
      shareUrl = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`;
      break;
    case 'twitter':
      shareUrl = `https://twitter.com/intent/tweet?url=${encodeURIComponent(url)}&text=${encodeURIComponent(texto)}`;
      break;
    case 'whatsapp':
      shareUrl = `https://wa.me/?text=${encodeURIComponent(texto + ' ' + url)}`;
      break;
    case 'linkedin':
      shareUrl = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`;
      break;
  }
  
  if (shareUrl) {
    window.open(shareUrl, '_blank', 'width=600,height=400');
  }
}

// Sistema de rating (estrellas)
function setRating(stars) {
  const starElements = document.querySelectorAll('.rating-star');
  starElements.forEach((star, index) => {
    if (index < stars) {
      star.classList.add('active');
    } else {
      star.classList.remove('active');
    }
  });
}

// Copiar al portapapeles
function copiarAlPortapapeles(texto) {
  navigator.clipboard.writeText(texto).then(() => {
    mostrarNotificacion('¡Copiado al portapapeles!', 'success');
  }).catch(() => {
    mostrarNotificacion('Error al copiar', 'error');
  });
}

// Detectar dispositivo móvil
function esMobile() {
  return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
}

// Ajustes específicos para móvil
if (esMobile()) {
  document.body.classList.add('mobile-device');
}

// Performance: Debounce function
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// Performance: Throttle function
function throttle(func, limit) {
  let inThrottle;
  return function() {
    const args = arguments;
    const context = this;
    if (!inThrottle) {
      func.apply(context, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}

// Optimizar scroll events
const optimizedScroll = throttle(() => {
  // Código para eventos de scroll
}, 100);

window.addEventListener('scroll', optimizedScroll);

// Analytics tracking (si se integra Google Analytics)
function trackEvent(category, action, label) {
  if (typeof gtag !== 'undefined') {
    gtag('event', action, {
      'event_category': category,
      'event_label': label
    });
  }
}

// Track clicks en servicios
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.btn-primary').forEach(btn => {
    btn.addEventListener('click', function() {
      const serviceName = this.closest('.card').querySelector('.card-title').textContent;
      trackEvent('Servicios', 'Click_Solicitar', serviceName);
    });
  });
});

console.log('🚀 Scripts cargados correctamente');