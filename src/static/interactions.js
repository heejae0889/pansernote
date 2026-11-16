(() => {
  'use strict';

  const header = document.querySelector('.site-header');
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let scheduled = false;
  function updateScroll() {
    const distance = document.documentElement.scrollHeight - window.innerHeight;
    const progress = distance > 0 ? Math.min(1, Math.max(0, window.scrollY / distance)) : 0;
    header.style.setProperty('--scroll-progress', progress);
    header.classList.toggle('is-scrolled', window.scrollY > 16);
    scheduled = false;
  }
  window.addEventListener('scroll', () => {
    if (!scheduled) {
      scheduled = true;
      window.requestAnimationFrame(updateScroll);
    }
  }, { passive: true });
  window.addEventListener('resize', updateScroll);
  window.addEventListener('load', updateScroll);
  window.addEventListener('pageshow', updateScroll);
  document.addEventListener('toggle', updateScroll, true);
  if ('ResizeObserver' in window) new ResizeObserver(updateScroll).observe(document.body);
  updateScroll();

  if ('IntersectionObserver' in window) {
    const cards = document.querySelectorAll('.features li, .guidelines, .image-grid figure, .text-card, .summary-card');
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        entry.target.classList.remove('scroll-pending');
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.08 });
    cards.forEach((card, index) => {
      card.style.setProperty('--reveal-delay', `${(index % 3) * 70}ms`);
      if (!motion.matches) card.classList.add('scroll-pending');
      observer.observe(card);
    });
    motion.addEventListener('change', () => {
      if (motion.matches) cards.forEach(card => card.classList.remove('scroll-pending'));
    });
    document.addEventListener('focusin', event => {
      event.target.closest('.scroll-pending')?.classList.remove('scroll-pending');
    });
  }

  const zone = document.querySelector('.file-zone');
  const input = document.getElementById('image');
  let dragDepth = 0;
  zone.addEventListener('dragenter', event => {
    event.preventDefault();
    dragDepth += 1;
    zone.classList.add('is-dragging');
  });
  zone.addEventListener('dragover', event => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'copy';
  });
  zone.addEventListener('dragleave', () => {
    dragDepth = Math.max(0, dragDepth - 1);
    if (!dragDepth) zone.classList.remove('is-dragging');
  });
  zone.addEventListener('drop', event => {
    event.preventDefault();
    dragDepth = 0;
    zone.classList.remove('is-dragging');
    const files = Array.from(event.dataTransfer.files);
    if (!files.length || files.some(file => !/\.(jpe?g|png)$/i.test(file.name))) return;
    const transfer = new DataTransfer();
    files.forEach(file => transfer.items.add(file));
    input.files = transfer.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));
  });
})();
