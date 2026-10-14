/* Premier Mobile Detailing — runtime layer for the static (Astro) site.
   Everything that used to be DOM-patched at load by enhance.js is now baked into
   the HTML; this file only carries behaviour: attribution capture, the mobile
   drawer, FAQ accordion, pointer effects, scroll reveal + count-up, the about-page
   splash/hover, and the lazy Leaflet map. Every browser API is guarded. */

/* First-touch advertising attribution — capture gclid / UTMs ONCE on the page the
   visitor first lands on, persist to localStorage, gap-fill only, never overwrite.
   The booking form reads this and sends it to the CRM. Kept byte-for-byte in
   behaviour with the previous enhance.js so GHL keeps receiving the same fields. */
(function () {
  try {
    var KEY = 'premier_attribution';
    var FIELDS = ['utm_source','utm_medium','utm_campaign','utm_content','utm_term','gclid','gbraid','wbraid','fbclid','msclkid'];
    var rec = {}, i;
    for (i = 0; i < FIELDS.length; i++) rec[FIELDS[i]] = '';
    rec.first_landing_page = '';
    try {
      var raw = window.localStorage.getItem(KEY);
      if (raw) {
        var parsed = JSON.parse(raw);
        for (i = 0; i < FIELDS.length; i++) { if (typeof parsed[FIELDS[i]] === 'string') rec[FIELDS[i]] = parsed[FIELDS[i]]; }
        if (typeof parsed.first_landing_page === 'string') rec.first_landing_page = parsed.first_landing_page;
      }
    } catch (e) {}
    try {
      var params = new URLSearchParams(window.location.search);
      for (i = 0; i < FIELDS.length; i++) { if (rec[FIELDS[i]]) continue; var v = params.get(FIELDS[i]); if (v) rec[FIELDS[i]] = v; }
    } catch (e) {}
    if (!rec.first_landing_page) { try { rec.first_landing_page = window.location.href; } catch (e) {} }
    try { window.localStorage.setItem(KEY, JSON.stringify(rec)); } catch (e) {}
  } catch (e) {}
})();

(function () {
  if (window.__pmdSite) return; window.__pmdSite = true;
  var RM = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var PATH = (location.pathname.replace(/\/+$/, '') || '/');

  function ready(fn) { if (document.readyState !== 'loading') fn(); else document.addEventListener('DOMContentLoaded', fn); }

  // ---- mobile drawer (markup is in the page; we only open/close it) ----
  ready(function () {
    var burger = document.getElementById('pmd-mburger'), d = document.getElementById('pmd-mdrawer');
    if (!burger || !d) return;
    function open() {
      d.removeAttribute('hidden');
      try { document.documentElement.style.overflow = 'hidden'; } catch (e) {}
      requestAnimationFrame(function () { d.classList.add('open'); });
    }
    function close() {
      d.classList.remove('open');
      try { document.documentElement.style.overflow = ''; } catch (e) {}
      setTimeout(function () { d.setAttribute('hidden', ''); }, 320);
    }
    burger.addEventListener('click', function (e) { e.preventDefault(); e.stopPropagation(); open(); });
    d.addEventListener('click', function (e) {
      if (e.target.closest('a') || e.target.classList.contains('pmd-md-backdrop') || e.target.classList.contains('pmd-md-close')) close();
    });
  });

  // ---- homepage FAQ accordion ----
  ready(function () {
    var wrap = document.querySelector('.pmd-faq'); if (!wrap) return;
    [].forEach.call(wrap.querySelectorAll('.pmd-faq-item'), function (it) {
      var q = it.querySelector('.pmd-faq-q'); if (!q) return;
      q.addEventListener('click', function () {
        var isOpen = it.classList.contains('open');
        [].forEach.call(wrap.querySelectorAll('.pmd-faq-item.open'), function (o) { o.classList.remove('open'); o.querySelector('.pmd-faq-a').style.maxHeight = null; });
        if (!isOpen) { it.classList.add('open'); var a = it.querySelector('.pmd-faq-a'); a.style.maxHeight = a.scrollHeight + 'px'; }
      });
    });
  });

  // ---- about page: logo splash intro + hero photo hover swap ----
  if (PATH === '/about') {
    (function splash() {
      if (document.getElementById('pmd-splash')) return;
      var ov = document.createElement('div'); ov.id = 'pmd-splash';
      ov.style.cssText = 'position:fixed;inset:0;z-index:99999;background:#080B16;display:flex;align-items:center;justify-content:center;overflow:hidden';
      var mesh = document.createElement('div');
      mesh.style.cssText = "position:absolute;inset:0;background:url('/assets/images/carbon-mesh.png') repeat;background-size:27px 48px;opacity:.4";
      var glow = document.createElement('div');
      glow.style.cssText = 'position:absolute;inset:0;background:radial-gradient(720px 520px at 50% 45%, rgba(37,99,235,.30), transparent 62%)';
      var img = document.createElement('img'); img.src = '/assets/images/45ead650-192d-44cb-8c3f-0ae51ecbbc4b.webp'; img.alt = 'Premier Mobile Detailing';
      img.style.cssText = 'width:min(60vw,440px);height:auto;position:relative;filter:drop-shadow(0 12px 44px rgba(0,0,0,.6))';
      ov.appendChild(mesh); ov.appendChild(glow); ov.appendChild(img);
      (document.body || document.documentElement).appendChild(ov);
      if (RM || !img.animate) { setTimeout(function () { ov.remove(); }, 500); return; }
      img.animate([{ opacity: 0, transform: 'scale(.82)' }, { opacity: 1, transform: 'scale(1)' }], { duration: 760, easing: 'cubic-bezier(.22,1,.36,1)', fill: 'both' });
      var shine = document.createElement('div');
      shine.style.cssText = 'position:absolute;top:0;bottom:0;width:38%;left:-50%;background:linear-gradient(100deg,transparent,rgba(255,255,255,.4),transparent);transform:skewX(-18deg)';
      ov.appendChild(shine);
      shine.animate([{ left: '-50%' }, { left: '125%' }], { duration: 1100, delay: 360, easing: 'cubic-bezier(.22,1,.36,1)', fill: 'both' });
      setTimeout(function () {
        var a = ov.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 560, easing: 'ease', fill: 'both' });
        a.onfinish = function () { ov.remove(); };
      }, 1500);
    })();
    ready(function () {
      var ov = document.querySelector('.pmd-about-swap'); if (!ov) return;
      var box = ov.parentElement;
      box.addEventListener('mouseenter', function () { ov.style.opacity = '0'; });
      box.addEventListener('mouseleave', function () { ov.style.opacity = '1'; });
    });
  }

  var SPOT = 'a.group > div, .rounded-2xl.bg-card, .bg-primary\\/10.border-primary';
  var MAG = 'a.bg-primary, button.bg-primary, a.bg-white, button.bg-white';

  // ---- cursor spotlight on cards ----
  document.addEventListener('pointermove', function (e) {
    if (RM || !e.target.closest) return;
    var el = e.target.closest(SPOT);
    if (!el) return;
    var r = el.getBoundingClientRect();
    el.style.setProperty('--mx', ((e.clientX - r.left) / r.width * 100).toFixed(1) + '%');
    el.style.setProperty('--my', ((e.clientY - r.top) / r.height * 100).toFixed(1) + '%');
  }, { passive: true });

  // ---- magnetic primary buttons ----
  document.addEventListener('pointermove', function (e) {
    if (RM || !e.target.closest) return;
    var b = e.target.closest(MAG);
    if (!b) return;
    var r = b.getBoundingClientRect();
    var dx = (e.clientX - (r.left + r.width / 2)) / (r.width / 2);
    var dy = (e.clientY - (r.top + r.height / 2)) / (r.height / 2);
    b.style.setProperty('--tx', (dx * 5).toFixed(1) + 'px');
    b.style.setProperty('--ty', (dy * 5).toFixed(1) + 'px');
  }, { passive: true });
  document.addEventListener('pointerout', function (e) {
    var b = e.target.closest && e.target.closest(MAG);
    if (b) { b.style.removeProperty('--tx'); b.style.removeProperty('--ty'); }
  }, { passive: true });

  // ---- scroll reveal + count-up (same targets as before, plus the old framer containers) ----
  ready(function () {
    var root = document.getElementById('root') || document.body;
    if (RM || !('IntersectionObserver' in window)) return;
    var vh = innerHeight;

    var targets = [], seen = new Set();
    root.querySelectorAll('section').forEach(function (sec) {
      var h = sec.querySelector('h2');
      if (h && h.parentElement) targets.push(h.parentElement);
      sec.querySelectorAll('.grid > *, a.group').forEach(function (c) { targets.push(c); });
    });
    targets = targets.filter(function (t) { if (!t || seen.has(t)) return false; seen.add(t); return true; });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.remove('rz'); en.target.classList.add('rz-in'); io.unobserve(en.target); }
      });
    }, { threshold: 0.08, rootMargin: '0px 0px -6% 0px' });
    targets.forEach(function (t, i) {
      var top = t.getBoundingClientRect().top;
      if (top < vh * 0.92) { t.classList.add('rz-in'); return; }
      t.classList.add('rz');
      t.style.transitionDelay = ((i % 6) * 65) + 'ms';
      io.observe(t);
    });

    // containers that framer-motion used to fade/slide in on view
    var io3 = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add('rv-in'); io3.unobserve(en.target); } });
    }, { threshold: 0.05 });
    root.querySelectorAll('[data-reveal]').forEach(function (t) {
      if (t.getBoundingClientRect().top < vh * 0.92) return;
      t.classList.add('rv'); io3.observe(t);
    });

    var nums = [];
    root.querySelectorAll('.text-4xl, .text-5xl').forEach(function (d) {
      if (d.children.length === 0 && /^[0-9][0-9.,]*\+?$/.test(d.textContent.trim())) nums.push(d);
    });
    var io2 = new IntersectionObserver(function (es) {
      es.forEach(function (en) { if (en.isIntersecting) { countUp(en.target); io2.unobserve(en.target); } });
    }, { threshold: 0.6 });
    nums.forEach(function (n) { io2.observe(n); });
  });

  function countUp(el) {
    var raw = el.textContent.trim();
    var plus = /\+$/.test(raw), dec = /\./.test(raw);
    var target = parseFloat(raw.replace(/[+,]/g, ''));
    if (isNaN(target)) return;
    var dur = 1300, start = null;
    (function step(ts) {
      if (!start) start = ts;
      var p = Math.min((ts - start) / dur, 1), e = 1 - Math.pow(1 - p, 3), v = target * e;
      el.textContent = (dec ? v.toFixed(1) : Math.round(v).toLocaleString('en-US')) + (plus ? '+' : '');
      if (p < 1) requestAnimationFrame(step); else el.textContent = raw;
    })(performance.now());
  }

  // ---- Serving-area map: Leaflet + OSM tiles, loaded only when scrolled near ----
  ready(function () {
    var boxes = document.querySelectorAll('[data-pmd-map]'); if (!boxes.length) return;
    var CENTER = [-38.0582578, 145.4357306];
    var POPUP = '<div style="color: #0f172a; min-width: 200px; font-family: system-ui, -apple-system, sans-serif; padding: 2px 0;">' +
      '<h3 style="margin: 0 0 4px 0; font-size: 16px; font-weight: 700; line-height: 1.2;">Premier Mobile Detailing</h3>' +
      '<div style="display: flex; align-items: center; gap: 4px; margin-bottom: 8px;"><span style="font-weight: 600; font-size: 13px; color: #333;">4.9</span>' +
      '<div style="display: flex; color: #f59e0b; font-size: 14px; letter-spacing: -1px;">★★★★★</div><span style="color: #64748b; font-size: 12px;">(53)</span></div>' +
      '<p style="margin: 0 0 12px 0; font-size: 13px; color: #475569; line-height: 1.4;">Ceramic Coating &amp; Paint Correction<br>Officer, VIC</p>' +
      '<a href="https://www.google.com/maps/search/?api=1&query=Premier+Mobile+Detailing+Officer+VIC" target="_blank" rel="noopener noreferrer" style="display: block; text-align: center; background: #3b82f6; color: white; text-decoration: none; padding: 8px 12px; border-radius: 6px; font-size: 13px; font-weight: 600;">View on Google</a></div>';
    var loading = null;
    function loadLeaflet(cb) {
      if (window.L) return cb();
      if (loading) return loading.push(cb);
      loading = [cb];
      var css = document.createElement('link'); css.rel = 'stylesheet'; css.href = '/assets/map.css'; document.head.appendChild(css);
      var js = document.createElement('script'); js.src = '/assets/vendor/leaflet.js';
      js.onload = function () { loading.forEach(function (f) { f(); }); loading = null; };
      document.head.appendChild(js);
    }
    function mount(el) {
      loadLeaflet(function () {
        var box = document.createElement('div'); box.className = 'pmd-map-box';
        el.insertBefore(box, el.firstChild);
        L.Icon.Default.imagePath = '/assets/vendor/images/';
        // [name, slug, lat, lng] per suburb page (homepage + hub); the suburb page passes its own point as data-focus
        var areas = [];
        try { var src = el.getAttribute('data-areas'); var n = src && document.querySelector(src); areas = n ? JSON.parse(n.textContent) : []; } catch (_) { areas = []; }
        var focus = (el.getAttribute('data-focus') || '').split(',');
        var m = L.map(box, { center: CENTER, zoom: 13, scrollWheelZoom: false });
        // OSM raster tiles darkened in CSS (CARTO's basemaps now need an API key)
        L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors', maxZoom: 19
        }).addTo(m);
        var home = L.marker(CENTER).addTo(m).bindPopup(POPUP, { minWidth: 220 });
        var pts = [CENTER], accent = '#3b82f6';
        areas.forEach(function (a) {
          var c = L.circleMarker([a[2], a[3]], { radius: 5, color: accent, weight: 2, fillColor: accent, fillOpacity: .55 }).addTo(m);
          c.bindTooltip(a[0], { className: 'pmd-area-tip', direction: 'top', offset: [0, -6] });
          c.on('click', function () { window.location.href = '/mobile-detailing/' + a[1]; });
          pts.push([a[2], a[3]]);
        });
        if (focus.length >= 3 && !isNaN(parseFloat(focus[0]))) {
          var f = [parseFloat(focus[0]), parseFloat(focus[1])];
          L.circleMarker(f, { radius: 9, color: accent, weight: 3, fillColor: accent, fillOpacity: .35 }).addTo(m)
            .bindTooltip('We service ' + focus.slice(2).join(','), { className: 'pmd-area-tip pmd-area-tip-focus', direction: 'top', permanent: true, offset: [0, -10] });
          pts.push(f);
        }
        if (pts.length > 1) m.fitBounds(L.latLngBounds(pts), { padding: [28, 28], maxZoom: 12 }); else home.openPopup();
      });
    }
    if (!('IntersectionObserver' in window)) { boxes.forEach(mount); return; }
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (en) { if (en.isIntersecting) { io.unobserve(en.target); mount(en.target); } });
    }, { rootMargin: '400px 0px' });
    boxes.forEach(function (b) { io.observe(b); });
  });

  // ---- Hero video: fade the reel in at 50% once it is really playing; keep the still for reduced-motion / data-saver ----
  ready(function () {
    var hero = document.getElementById('static-hero'); if (!hero) return;
    var v = hero.querySelector('video.pmd-hero-video'); if (!v) return;
    var rm = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var save = navigator.connection && navigator.connection.saveData;
    if (rm || save) { try { v.pause(); } catch (_) {} v.removeAttribute('autoplay'); v.preload = 'none'; return; }
    v.muted = true; v.defaultMuted = true; v.playsInline = true;
    v.addEventListener('playing', function () { hero.classList.add('pmd-hero-live'); });
    var p = v.play(); if (p && p.catch) p.catch(function () {});
  });

  // ---- Gallery strip: three copies of the card set so the drift never hits a scroll clamp; drag to browse ----
  ready(function () {
    var rm = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    document.querySelectorAll('[data-pmd-strip] .pmd-strip-row').forEach(function (row) {
      var track = row.querySelector('.pmd-strip-track'); if (!track) return;
      var cards = Array.prototype.slice.call(track.children); if (cards.length < 2) return;
      for (var pass = 0; pass < 2; pass++) cards.forEach(function (c) {
        var k = c.cloneNode(true); k.setAttribute('aria-hidden', 'true');
        k.querySelectorAll('img').forEach(function (im) { im.alt = ''; });
        track.appendChild(k);
      });
      var dir = parseInt(row.getAttribute('data-dir'), 10) || 1, speed = 0.9;
      var seg = 0, seeded = false, dragging = false, startX = 0, startScroll = 0, moved = 0, visible = true;
      function measure() { seg = track.scrollWidth / 3; }
      measure();
      track.querySelectorAll('img').forEach(function (im) { im.addEventListener('load', measure); });
      window.addEventListener('resize', measure);
      if ('IntersectionObserver' in window) new IntersectionObserver(function (es) { visible = es[0].isIntersecting; }).observe(row);
      function wrap() { if (seg <= 0) return; if (row.scrollLeft >= 2 * seg) row.scrollLeft -= seg; else if (row.scrollLeft < seg) row.scrollLeft += seg; }
      (function frame() {
        if (seg > 0 && !seeded) { row.scrollLeft = seg; seeded = true; }
        if (visible && !dragging && !rm && seg > 0) { row.scrollLeft += speed * dir; wrap(); }
        requestAnimationFrame(frame);
      })();
      row.addEventListener('pointerdown', function (e) {
        dragging = true; moved = 0; startX = e.clientX; startScroll = row.scrollLeft;
        row.classList.add('dragging'); try { row.setPointerCapture(e.pointerId); } catch (_) {}
      });
      row.addEventListener('pointermove', function (e) {
        if (!dragging) return; var dx = e.clientX - startX; moved = Math.max(moved, Math.abs(dx));
        row.scrollLeft = startScroll - dx; wrap();
      });
      function end(e) { if (!dragging) return; dragging = false; row.classList.remove('dragging'); try { row.releasePointerCapture(e.pointerId); } catch (_) {} }
      row.addEventListener('pointerup', end); row.addEventListener('pointercancel', end);
      row.addEventListener('click', function (e) { if (moved > 6) e.preventDefault(); });
    });
  });

  // ---- Before/after sliders ----
  // First view: sweep from all-"before" to mostly-"after" (staggered per card), settle at 50%, then breathe gently
  // and pulse the knob until someone touches it. Desktop: the divider follows the mouse on hover; everyone: drag,
  // arrow keys, Home/End. Reduced motion: no sweep or breathing, just the controls.
  ready(function () {
    var rm = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var frames = document.querySelectorAll('[data-pmd-ba] .pmd-ba-frame'); if (!frames.length) return;
    function ease(t) { return t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }
    frames.forEach(function (frame, idx) {
      var REST = 50, pos = rm ? REST : 100, anim = null, idle0 = 0;
      var touched = false, down = false, hover = false, inView = false, revealed = false;
      function set(p) { pos = Math.max(0, Math.min(100, p)); frame.style.setProperty('--pos', pos + '%'); frame.setAttribute('aria-valuenow', Math.round(pos)); }
      function stop() { if (anim) { cancelAnimationFrame(anim); anim = null; } }
      function tween(to, dur, done) {
        var from = pos, t0 = performance.now(); stop();
        (function step(ts) {
          var k = Math.min((ts - t0) / dur, 1); set(from + (to - from) * ease(k));
          if (k < 1) anim = requestAnimationFrame(step); else { anim = null; if (done) done(); }
        })(t0);
      }
      function breathe(ts) {
        if (touched || !inView || hover || down) { anim = null; return; }
        if (!idle0) idle0 = ts;
        set(REST + Math.sin((ts - idle0) / 1300) * 5);
        anim = requestAnimationFrame(breathe);
      }
      function startBreathing() { if (rm || touched || anim) return; idle0 = 0; anim = requestAnimationFrame(breathe); }
      function touch() { if (touched) return; touched = true; frame.classList.add('pmd-ba-touched'); stop(); }
      function reveal() {
        if (revealed) return; revealed = true;
        if (rm) return;
        setTimeout(function () { if (touched || !inView) { if (!touched) set(REST); return; } tween(34, 1500, function () { tween(REST, 900, startBreathing); }); }, 200 * idx);
      }
      set(pos);
      if ('IntersectionObserver' in window) {
        new IntersectionObserver(function (es) {
          es.forEach(function (e) {
            inView = e.isIntersecting;
            if (inView) { if (!revealed) reveal(); else startBreathing(); }
            else if (!down) { stop(); if (revealed && !touched) set(REST); }
          });
        }, { threshold: .35 }).observe(frame);
      } else { inView = true; reveal(); }
      function fromEvent(e) { var r = frame.getBoundingClientRect(); set(((e.clientX - r.left) / r.width) * 100); }
      frame.addEventListener('pointerdown', function (e) { touch(); down = true; try { frame.setPointerCapture(e.pointerId); } catch (_) {} fromEvent(e); e.preventDefault(); });
      frame.addEventListener('pointermove', function (e) {
        if (down) { fromEvent(e); return; }
        if (e.pointerType === 'mouse') { hover = true; touch(); fromEvent(e); }
      });
      function up(e) { down = false; try { frame.releasePointerCapture(e.pointerId); } catch (_) {} }
      frame.addEventListener('pointerup', up); frame.addEventListener('pointercancel', up);
      frame.addEventListener('pointerleave', function (e) { if (e.pointerType === 'mouse' && !down) { hover = false; tween(REST, 700); } });
      frame.addEventListener('keydown', function (e) {
        var k = e.key; if (k !== 'ArrowLeft' && k !== 'ArrowRight' && k !== 'Home' && k !== 'End') return;
        touch(); set(k === 'ArrowLeft' ? pos - 4 : k === 'ArrowRight' ? pos + 4 : k === 'Home' ? 0 : 100); e.preventDefault();
      });
    });
  });
})();
