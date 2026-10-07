(function () {
  'use strict';

  const toggle = document.querySelector('[data-menu-toggle]');
  const nav = document.querySelector('[data-nav]');
  const header = document.querySelector('[data-header]');
  const menuLabel = document.querySelector('[data-menu-label]');

  if (toggle && nav) {
    const setNav = function (open) {
      nav.classList.toggle('is-open', open);
      toggle.setAttribute('aria-expanded', String(open));
      if (menuLabel) menuLabel.textContent = open ? 'Close navigation' : 'Open navigation';
    };
    const closeNav = function () { setNav(false); };

    toggle.addEventListener('click', function () {
      setNav(toggle.getAttribute('aria-expanded') !== 'true');
    });

    // One delegated listener handles current and future navigation links.
    nav.addEventListener('click', function (event) {
      if (event.target instanceof Element && event.target.closest('a')) {
        closeNav();
      }
    });

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && toggle.getAttribute('aria-expanded') === 'true') {
        closeNav();
        toggle.focus();
      }
    });
    document.addEventListener('click', function (event) {
      if (header && !header.contains(event.target)) closeNav();
    });
    document.addEventListener('focusin', function (event) {
      if (header && !header.contains(event.target)) closeNav();
    });
    const mobile = window.matchMedia('(max-width: 1050px)');
    if (mobile.addEventListener) mobile.addEventListener('change', closeNav);
    // Collapse only after the controls work; no-JS navigation stays usable.
    document.documentElement.classList.add('nav-ready');
  }

  const items = document.querySelectorAll(
    '.reveal, .section-topline, .systems-heading, .page-hero-grid > *, ' +
    '.contact-grid > *, .sponsor-band-grid > *, .handoff-grid > *, .hero-stats > div'
  );
  let observer;
  const showItems = function () {
    if (observer) observer.disconnect();
    items.forEach(function (item) {
      item.classList.remove('is-pending');
      item.classList.add('is-visible');
    });
  };
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');

  if (!items.length || motion.matches) {
    showItems();
    return;
  }

  if (!('IntersectionObserver' in window)) {
    showItems();
    return;
  }

  const reveal = function (item) {
    item.classList.remove('is-pending');
    item.classList.add('is-visible');
    if (observer) observer.unobserve(item);
  };
  try {
    observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) reveal(entry.target);
      });
    }, { rootMargin: '0px 0px -32px 0px', threshold: 0.01 });

    items.forEach(function (item) {
      item.classList.add('reveal');
      // Never delay above-the-fold content or hide a restored scroll position.
      if (item.getBoundingClientRect().top < window.innerHeight - 32) {
        reveal(item);
        return;
      }
      const siblings = Array.from(item.parentElement.children);
      if (item.parentElement.matches('.member-grid, .system-grid, .reason-grid, .gallery-grid')) {
        item.style.setProperty('--reveal-delay', String((siblings.indexOf(item) % 3) * 70) + 'ms');
      }
      item.classList.add('is-pending');
      observer.observe(item);
    });
  } catch (error) {
    // A failed observer must never strand hidden content.
    showItems();
    return;
  }

  // Keyboard and deep-link navigation should not wait for an animation.
  const revealTarget = function (target) {
    items.forEach(function (item) {
      if (item.contains(target) || target.contains(item)) reveal(item);
    });
  };
  const revealHash = function () {
    try {
      const target = document.getElementById(decodeURIComponent(window.location.hash.slice(1)));
      if (target) revealTarget(target);
    } catch (error) { /* Ignore malformed fragments. */ }
  };
  document.addEventListener('focusin', function (event) { revealTarget(event.target); });
  window.addEventListener('hashchange', revealHash);
  window.addEventListener('pageshow', function (event) { if (event.persisted) showItems(); });
  window.addEventListener('beforeprint', showItems);
  if (motion.addEventListener) motion.addEventListener('change', function (event) {
    if (event.matches) showItems();
  });
  revealHash();
})();
