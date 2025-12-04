// Función para el carrusel de reseñas
function scrollCarrusel(direction) {
    const container = document.getElementById('carrusel-scroll');
    const scrollAmount = 220; 
    container.scrollBy({
        left: direction * scrollAmount,
        behavior: 'smooth'
    });
}

// Smooth scroll para links del navbar
document.addEventListener('DOMContentLoaded', function() {
    const navLinks = document.querySelectorAll('a[href^="#"]');
    
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
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
    
    // Auto-scroll infinito para reseñas (opcional)
    const carruselContainer = document.getElementById('carrusel-scroll');
    let isScrolling = false;
    
    function autoScroll() {
        if (!isScrolling && carruselContainer) {
            const maxScroll = carruselContainer.scrollWidth - carruselContainer.clientWidth;
            
            if (carruselContainer.scrollLeft >= maxScroll - 10) {
                carruselContainer.scrollTo({ left: 0, behavior: 'smooth' });
            } else {
                carruselContainer.scrollBy({ left: 220, behavior: 'smooth' });
            }
        }
    }
    
    // Auto-scroll cada 4 segundos
    setInterval(autoScroll, 4000);
    
    // Pausar auto-scroll cuando el usuario interactúa
    carruselContainer?.addEventListener('mouseenter', () => { isScrolling = true; });
    carruselContainer?.addEventListener('mouseleave', () => { isScrolling = false; });
});