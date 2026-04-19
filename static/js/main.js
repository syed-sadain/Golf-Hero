/* ================================================================
   GOLFHERO — MAIN JAVASCRIPT
   Animations, interactions, and utilities
   ================================================================ */

// ── Mobile Nav Toggle ──────────────────────────────────────────
function toggleNav() {
  const links = document.querySelector('.nav-links');
  links.classList.toggle('open');
}

// Close nav on outside click
document.addEventListener('click', (e) => {
  const nav = document.querySelector('.glass-nav');
  const links = document.querySelector('.nav-links');
  if (links && links.classList.contains('open') && !nav.contains(e.target)) {
    links.classList.remove('open');
  }
});

// ── Auto-dismiss flash messages ────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const flashes = document.querySelectorAll('.flash');
  flashes.forEach(flash => {
    setTimeout(() => {
      flash.style.transition = 'opacity .4s ease, transform .4s ease';
      flash.style.opacity = '0';
      flash.style.transform = 'translateX(100%)';
      setTimeout(() => flash.remove(), 400);
    }, 4500);
  });
});

// ── Intersection Observer: Fade-up on scroll ───────────────────
document.addEventListener('DOMContentLoaded', () => {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.animationPlayState = 'running';
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  document.querySelectorAll('.fade-up').forEach(el => {
    el.style.animationPlayState = 'paused';
    observer.observe(el);
  });
});

// ── Animated counter for stats ─────────────────────────────────
function animateCounter(el, target, prefix = '', suffix = '', duration = 1500) {
  const start = 0;
  const startTime = performance.now();
  const isFloat = target % 1 !== 0;

  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    // Ease out cubic
    const eased = 1 - Math.pow(1 - progress, 3);
    const current = start + (target - start) * eased;
    el.textContent = prefix + (isFloat ? current.toFixed(2) : Math.floor(current)) + suffix;
    if (progress < 1) requestAnimationFrame(update);
  }
  requestAnimationFrame(update);
}

document.addEventListener('DOMContentLoaded', () => {
  const countObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const el = entry.target;
        const raw = el.textContent.replace(/[^0-9.]/g, '');
        const target = parseFloat(raw);
        if (!isNaN(target) && target > 0) {
          animateCounter(el, target);
        }
        countObserver.unobserve(el);
      }
    });
  }, { threshold: 0.3 });

  document.querySelectorAll('.stat-num').forEach(el => {
    countObserver.observe(el);
  });
});

// ── Prize bar animation ────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const barObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.querySelectorAll('.prize-bar-fill').forEach(fill => {
          const w = fill.style.width;
          fill.style.width = '0';
          setTimeout(() => { fill.style.width = w; }, 100);
        });
        barObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.3 });

  document.querySelectorAll('.prize-bar').forEach(el => barObserver.observe(el));
});

// ── Draw ball pop-in stagger ───────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.draw-ball').forEach((ball, i) => {
    ball.style.animationDelay = `${i * 0.1}s`;
  });
});

// ── Glassmorphism hover tilt effect ───────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const cards = document.querySelectorAll('.glass.stat-card, .glass.step-card, .glass.charity-card');
  cards.forEach(card => {
    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const centerX = rect.width / 2;
      const centerY = rect.height / 2;
      const rotateX = ((y - centerY) / centerY) * -5;
      const rotateY = ((x - centerX) / centerX) * 5;
      card.style.transform = `perspective(800px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-4px)`;
      card.style.transition = 'transform 0.1s ease';
    });
    card.addEventListener('mouseleave', () => {
      card.style.transform = 'perspective(800px) rotateX(0) rotateY(0) translateY(0)';
      card.style.transition = 'transform 0.4s ease';
    });
  });
});

// ── Score range slider live label ─────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const sliders = document.querySelectorAll('input[type="range"]');
  sliders.forEach(slider => {
    const valueDisplay = document.getElementById(slider.id + '-val') ||
                        document.querySelector(`[data-for="${slider.id}"]`);
    if (valueDisplay) {
      slider.addEventListener('input', () => {
        valueDisplay.textContent = slider.value;
      });
    }
  });
});

// ── Navbar scroll opacity ──────────────────────────────────────
window.addEventListener('scroll', () => {
  const nav = document.querySelector('.glass-nav');
  if (nav) {
    if (window.scrollY > 50) {
      nav.style.background = 'rgba(15,12,41,0.92)';
    } else {
      nav.style.background = 'rgba(15,12,41,0.75)';
    }
  }
});

// ── Plan card selection ────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const planCards = document.querySelectorAll('.plan-card');
  planCards.forEach(card => {
    card.addEventListener('click', () => {
      planCards.forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
      const radio = card.querySelector('input[type="radio"]');
      if (radio) radio.checked = true;
    });
    // Mark initially selected
    const radio = card.querySelector('input[type="radio"]');
    if (radio && radio.checked) card.classList.add('selected');
  });
});

// ── Confirm dangerous actions ──────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', (e) => {
      if (!confirm(el.dataset.confirm)) {
        e.preventDefault();
        e.stopPropagation();
      }
    });
  });
});

// ── Tooltip on draw balls ──────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.draw-ball').forEach(ball => {
    ball.setAttribute('title', `Number: ${ball.textContent.trim()}`);
  });
});

// ── Score input validation feedback ───────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const scoreInput = document.querySelector('input[name="score"]');
  if (scoreInput) {
    scoreInput.addEventListener('input', () => {
      const val = parseInt(scoreInput.value);
      if (val < 1 || val > 45) {
        scoreInput.style.borderColor = 'rgba(255,68,68,.6)';
        scoreInput.style.boxShadow = '0 0 0 3px rgba(255,68,68,.15)';
      } else {
        scoreInput.style.borderColor = 'var(--accent-3)';
        scoreInput.style.boxShadow = '0 0 0 3px rgba(0,255,163,.15)';
      }
    });
  }
});

// ── Admin: Draw number preview ─────────────────────────────────
const drawTypeSelect = document.querySelector('select[name="draw_type"]');
if (drawTypeSelect) {
  drawTypeSelect.addEventListener('change', () => {
    const badge = document.querySelector('.draw-type-badge');
    if (badge) {
      badge.textContent = drawTypeSelect.value === 'algorithm' ? '⚡ Weighted Algorithm' : '🎲 Pure Random';
    }
  });
}

// ── Smooth scroll for anchor links ────────────────────────────
document.querySelectorAll('a[href^="#"]').forEach(link => {
  link.addEventListener('click', (e) => {
    const target = document.querySelector(link.getAttribute('href'));
    if (target) {
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
});

// ── Page load animation ────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.body.style.opacity = '0';
  document.body.style.transition = 'opacity 0.3s ease';
  requestAnimationFrame(() => {
    document.body.style.opacity = '1';
  });
});

// ── Keyboard: close modals with Escape ────────────────────────
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-backdrop').forEach(m => {
      m.style.display = 'none';
    });
  }
});

// ── Close modal on backdrop click ─────────────────────────────
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('modal-backdrop')) {
    e.target.style.display = 'none';
  }
});

console.log('%c⛳ GolfHero', 'font-size:24px;font-weight:bold;background:linear-gradient(90deg,#00d4ff,#7b2ff7);-webkit-background-clip:text;color:transparent;');
console.log('%cPlay. Give. Win.', 'font-size:12px;color:#666;');
