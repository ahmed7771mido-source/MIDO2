// ========== Theme Toggle ==========
(function() {
  const themeToggle = document.getElementById('themeToggle');
  const htmlElement = document.documentElement;
  
  // Load saved theme or default to light
  const savedTheme = localStorage.getItem('theme') || 'light';
  htmlElement.setAttribute('data-theme', savedTheme);
  
  if (themeToggle) {
    updateThemeIcon(savedTheme);
    
    themeToggle.addEventListener('click', function() {
      const currentTheme = htmlElement.getAttribute('data-theme');
      const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
      
      htmlElement.setAttribute('data-theme', newTheme);
      localStorage.setItem('theme', newTheme);
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

// ========== Burger Menu ==========
(function() {
  const burger = document.getElementById('burger');
  const nav = document.getElementById('nav');
  
  if (burger && nav) {
    burger.onclick = function() {
      nav.classList.toggle('open');
      
      // Animate burger icon
      const isOpen = nav.classList.contains('open');
      burger.textContent = isOpen ? '✕' : '☰';
    };
  }
})();

// ========== Product Options (Size/Color) ==========
(function() {
  document.querySelectorAll('.chips').forEach(function(box) {
    const target = document.getElementById(box.dataset.target);
    
    box.querySelectorAll('button').forEach(function(btn) {
      btn.onclick = function() {
        box.querySelectorAll('button').forEach(x => x.classList.remove('on'));
        btn.classList.add('on');
        if (target) target.value = btn.textContent.trim();
      };
    });
  });
})();

// ========== Product Gallery ==========
(function() {
  const mainImg = document.getElementById('mainimg');
  
  document.querySelectorAll('.th img').forEach(function(thumb) {
    thumb.onclick = function() {
      if (mainImg) {
        mainImg.style.opacity = '0';
        setTimeout(() => {
          mainImg.src = thumb.dataset.full;
          mainImg.style.opacity = '1';
        }, 200);
      }
    };
  });
})();

// ========== Delivery Fee Calculator ==========
(function() {
  const govSelect = document.getElementById('gov');
  const sumDiv = document.getElementById('sum');
  
  if (!govSelect || !sumDiv) return;
  
  const subtotal = parseInt(sumDiv.dataset.sub, 10) || 0;
  
  function formatNumber(n) {
    return n.toLocaleString('en-US');
  }
  
  function updateTotal() {
    let fee = parseInt(govSelect.dataset.default, 10) || 0;
    
    if (govSelect.tagName === 'SELECT') {
      const selectedOption = govSelect.options[govSelect.selectedIndex];
      if (selectedOption && selectedOption.dataset.fee) {
        fee = parseInt(selectedOption.dataset.fee, 10);
      }
    }
    
    const feeElement = document.getElementById('feeval');
    const totalElement = document.getElementById('totval');
    
    if (feeElement) feeElement.textContent = formatNumber(fee);
    if (totalElement) totalElement.textContent = formatNumber(subtotal + fee);
  }
  
  govSelect.addEventListener('change', updateTotal);
  updateTotal();
})();

// ========== Smooth Scroll for Anchor Links ==========
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', function(e) {
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

// ========== Add Animation on Scroll ==========
(function() {
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('fade-in');
      }
    });
  }, { threshold: 0.1 });
  
  document.querySelectorAll('.pc, .cl, .rv, .box').forEach(el => {
    observer.observe(el);
  });
})();

// ========== Cart Count Animation ==========
(function() {
  const cartButton = document.querySelector('.cartb');
  if (cartButton) {
    cartButton.addEventListener('click', function(e) {
      this.style.transform = 'scale(0.95)';
      setTimeout(() => {
        this.style.transform = '';
      }, 150);
    });
  }
})();
