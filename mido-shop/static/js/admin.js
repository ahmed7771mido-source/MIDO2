// ========== Theme Toggle ==========
(function () {
  const themeToggle = document.getElementById('themeToggle');
  const htmlElement = document.documentElement;

  // Load saved theme or default to light
  const savedTheme = localStorage.getItem('adminTheme') || 'light';
  htmlElement.setAttribute('data-theme', savedTheme);

  if (themeToggle) {
    updateThemeIcon(savedTheme);

    themeToggle.addEventListener('click', function () {
      const currentTheme = htmlElement.getAttribute('data-theme');
      const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

      htmlElement.setAttribute('data-theme', newTheme);
      localStorage.setItem('adminTheme', newTheme);
      updateThemeIcon(newTheme);

      // Add animation
      themeToggle.style.transform = 'rotate(360deg)';
      setTimeout(() => {
        themeToggle.style.transform = '';
      }, 300);
    });
  }

  function updateThemeIcon(theme) {
    if (themeToggle) {
      themeToggle.textContent = theme === 'dark' ? '☀️' : '🌙';
    }
  }
})();

// ========== Order Polling (Real-time Updates) ==========
(function () {
  const body = document.body;
  let lastOrderId = parseInt(body.dataset.last || '0', 10);
  const toast = document.getElementById('toast');
  const notificationBadge = document.getElementById('nb');
  const baseTitle = document.title;

  function pollOrders() {
    const pollUrl = body.dataset.poll;
    if (!pollUrl) return;

    fetch(pollUrl + '?after=' + lastOrderId, { credentials: 'same-origin' })
      .then(response => response.ok ? response.json() : null)
      .then(data => {
        if (!data) return;

        // Update notification badge
        if (notificationBadge) {
          notificationBadge.textContent = data.unseen;
          notificationBadge.hidden = !data.unseen;
        }

        // Update page title
        const titlePrefix = data.unseen ? `(${data.unseen}) ` : '';
        document.title = titlePrefix + baseTitle.replace(/^\(\d+\) /, '');

        // Show toast for new orders
        if (data.orders.length && toast) {
          const latestOrder = data.orders[data.orders.length - 1];
          toast.innerHTML = `
            <strong>طلب جديد #${latestOrder.id}</strong><br>
            من ${escapeHtml(latestOrder.name)} · ${latestOrder.total} ج ·
            <a href="${body.dataset.orders}/${latestOrder.id}">افتح الطلب</a>
          `;
          toast.hidden = false;

          // Add entrance animation
          toast.style.animation = 'fadeIn 0.5s ease-out';

          setTimeout(() => {
            toast.hidden = true;
          }, 12000);
        }

        lastOrderId = data.latest;
      })
      .catch(err => console.error('Poll error:', err));
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Poll every 15 seconds
  setInterval(pollOrders, 15000);

  // Poll immediately on page load
  pollOrders();
})();

// ========== Add Animation to Cards ==========
(function () {
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.animation = 'fadeIn 0.6s ease-out';
      }
    });
  }, { threshold: 0.1 });

  document.querySelectorAll('.card, .kpi').forEach(el => {
    observer.observe(el);
  });
})();

// ========== Confirm Dialogs Enhancement ==========
document.querySelectorAll('form[onsubmit*="confirm"]').forEach(form => {
  const originalOnSubmit = form.onsubmit;
  form.onsubmit = function (e) {
    const result = originalOnSubmit ? originalOnSubmit.call(this, e) : true;
    if (!result) {
      e.preventDefault();
    }
    return result;
  };
});

// ========== Button Click Animation ==========
document.querySelectorAll('.btn, .act-btn').forEach(button => {
  button.addEventListener('click', function () {
    if (!this.disabled) {
      this.style.transform = 'scale(0.95)';
      setTimeout(() => {
        this.style.transform = '';
      }, 150);
    }
  });
});

// ========== Auto-hide Flash Messages ==========
(function () {
  const flashMessages = document.querySelectorAll('.flash.ok');
  flashMessages.forEach(flash => {
    setTimeout(() => {
      flash.style.transition = 'opacity 0.5s ease';
      flash.style.opacity = '0';
      setTimeout(() => {
        flash.remove();
      }, 500);
    }, 5000);
  });
})();

// ========== Image Preview Enhancement ==========
document.querySelectorAll('.tn, .im img').forEach(img => {
  img.addEventListener('click', function () {
    const modal = document.createElement('div');
    modal.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.9);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 10000;
      cursor: pointer;
      animation: fadeIn 0.3s ease-out;
    `;

    const modalImg = document.createElement('img');
    modalImg.src = this.src;
    modalImg.style.cssText = `
      max-width: 90%;
      max-height: 90%;
      border-radius: 12px;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
    `;

    modal.appendChild(modalImg);
    modal.addEventListener('click', () => modal.remove());
    document.body.appendChild(modal);
  });
});

// ========== Table Row Highlight ==========
document.querySelectorAll('table tr').forEach(row => {
  if (!row.querySelector('th')) {
    row.addEventListener('mouseenter', function () {
      this.style.transition = 'all 0.2s ease';
    });
  }
});

// ========== Smooth Scroll ==========
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', function (e) {
    const href = this.getAttribute('href');
    if (href !== '#') {
      e.preventDefault();
      const target = document.querySelector(href);
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }
  });
});
