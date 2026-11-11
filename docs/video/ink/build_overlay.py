"""Build standalone docs/video/ink/overlay.js with inlined Patrick Hand font.
Role E: INK chat for ReturnLens hackathon.
Includes:
- Soft light background halo (white at 88% opacity, 6px padding) so notes never obscure UI underneath
- Intelligent free-space measurement avoiding overlapping UI text elements
- Hand-drawn wobbly SVG strokes (dashoffset animated 0.6s)
- Visible cursor and click ripple
"""

from __future__ import annotations

import base64
from pathlib import Path

INK_DIR = Path(__file__).resolve().parent
FONT_PATH = INK_DIR / "PatrickHand-Regular.ttf"
OUTPUT_JS = INK_DIR / "overlay.js"

JS_TEMPLATE = r"""/**
 * ReturnLens Video Recording Overlay: Visible Cursor & Hand-drawn Ink Annotations
 * Wave 14 (Role E / INK chat).
 *
 * Provides:
 * 1. High-contrast visible mouse cursor (arrow SVG) following Playwright mousemove events.
 * 2. Animated click ripples on mousedown/click.
 * 3. Hand-drawn wobbly SVG ink annotations (circles, arrows, notes) in Patrick Hand font.
 * 4. Automatic positioning in free/empty space + soft light background halo (white 88% opacity)
 *    so notes never obscure underlying UI text.
 * 5. Constraint of at most two annotations on screen at once, 2-4s duration.
 */
(function () {
  const fontB64 = "__FONT_BASE64__";

  function initOverlay() {
    if (window.__RETURNLENS_INK_INITIALIZED__) {
      return;
    }
    const root = document.documentElement || document.body;
    if (!root) {
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initOverlay);
      } else {
        window.requestAnimationFrame(initOverlay);
      }
      return;
    }
    window.__RETURNLENS_INK_INITIALIZED__ = true;

    // 1. Inlined Font Face & Styles
    try {
      const font = new FontFace('Patrick Hand', `url(data:font/ttf;base64,${fontB64})`);
      font.load().then(loaded => {
        document.fonts.add(loaded);
      }).catch(err => console.warn('[ReturnLensInk] FontFace load warning:', err));
    } catch (e) {}

    const styleEl = document.createElement('style');
    styleEl.id = 'returnlens-ink-styles';
    styleEl.textContent = `
      @font-face {
        font-family: 'Patrick Hand';
        src: url('data:font/ttf;base64,${fontB64}') format('truetype');
        font-weight: normal;
        font-style: normal;
        font-display: swap;
      }

      #playwright-cursor-container,
      #ink-overlay-svg,
      #ink-notes-layer {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        margin: 0 !important;
        padding: 0 !important;
        border: none !important;
        zoom: 1 !important;
        transform: none !important;
        pointer-events: none !important;
        overflow: visible !important;
      }

      #playwright-cursor-container {
        z-index: 2147483647 !important;
      }

      #playwright-cursor {
        position: absolute;
        top: 0;
        left: 0;
        width: 28px;
        height: 28px;
        pointer-events: none;
        transform: translate3d(-100px, -100px, 0);
        will-change: transform;
        filter: drop-shadow(0 2px 5px rgba(0, 0, 0, 0.55));
        transition: opacity 0.2s ease;
      }

      .playwright-click-ripple {
        position: absolute;
        border-radius: 50%;
        pointer-events: none;
        box-sizing: border-box;
        border: 3px solid #2563eb;
        background: rgba(59, 130, 246, 0.28);
        transform: translate(-50%, -50%) scale(0.2);
        animation: playwright-ripple-anim 0.45s cubic-bezier(0.1, 0.8, 0.3, 1) forwards;
      }

      @keyframes playwright-ripple-anim {
        0% {
          opacity: 0.95;
          transform: translate(-50%, -50%) scale(0.2);
        }
        100% {
          opacity: 0;
          transform: translate(-50%, -50%) scale(1.8);
        }
      }

      #ink-overlay-svg {
        z-index: 2147483640 !important;
      }

      #ink-notes-layer {
        z-index: 2147483641 !important;
      }

      .ink-group {
        transition: opacity 0.35s ease-out;
      }

      .ink-group.ink-fading {
        opacity: 0 !important;
      }

      /* Soft light background halo (white at 88% opacity, 6px padding) */
      .ink-note-bubble {
        position: absolute;
        font-family: 'Patrick Hand', cursive, sans-serif;
        font-size: 25px;
        line-height: 1.15;
        font-weight: 600;
        color: #e11d48;
        white-space: nowrap;
        pointer-events: none;
        background: rgba(255, 255, 255, 0.88);
        padding: 3px 8px;
        border-radius: 6px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
        border: 1px solid rgba(225, 29, 72, 0.25);
        text-shadow:
          -1px -1px 0 #ffffff,
           1px -1px 0 #ffffff,
          -1px  1px 0 #ffffff,
           1px  1px 0 #ffffff;
        animation: ink-note-pop-anim 0.35s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
        will-change: transform, opacity;
      }

      @keyframes ink-note-pop-anim {
        0% {
          opacity: 0.85;
          transform: scale(0.85) rotate(-1.5deg);
        }
        100% {
          opacity: 1;
          transform: scale(1) rotate(-1.5deg);
        }
      }
    `;
    document.head.appendChild(styleEl);

    // 2. Setup Cursor Elements (attached to documentElement)
    const cursorContainer = document.createElement('div');
    cursorContainer.id = 'playwright-cursor-container';

    const cursorEl = document.createElement('div');
    cursorEl.id = 'playwright-cursor';
    cursorEl.innerHTML = `
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M4 2L20 14.5L12.5 15L9.5 21.5L6.5 20L9.5 14L4 2Z" fill="#111827" stroke="#FFFFFF" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
      </svg>
    `;
    cursorContainer.appendChild(cursorEl);
    root.appendChild(cursorContainer);

    function updateCursor(x, y) {
      cursorEl.style.transform = `translate3d(${x - 4}px, ${y - 2}px, 0)`;
    }

    function spawnRipple(x, y) {
      const ripple = document.createElement('div');
      ripple.className = 'playwright-click-ripple';
      ripple.style.left = `${x}px`;
      ripple.style.top = `${y}px`;
      ripple.style.width = '38px';
      ripple.style.height = '38px';
      cursorContainer.appendChild(ripple);
      setTimeout(() => {
        if (ripple.parentNode) {
          ripple.parentNode.removeChild(ripple);
        }
      }, 450);
    }

    window.addEventListener('mousemove', (e) => {
      updateCursor(e.clientX, e.clientY);
    }, { passive: true, capture: true });

    window.addEventListener('mousedown', (e) => {
      spawnRipple(e.clientX, e.clientY);
    }, { passive: true, capture: true });

    // 3. Setup Ink SVG Overlay & Notes Container (attached to documentElement)
    const svgOverlay = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svgOverlay.id = 'ink-overlay-svg';
    svgOverlay.setAttribute('width', window.innerWidth.toString());
    svgOverlay.setAttribute('height', window.innerHeight.toString());
    svgOverlay.setAttribute('viewBox', `0 0 ${window.innerWidth} ${window.innerHeight}`);
    root.appendChild(svgOverlay);

    const notesLayer = document.createElement('div');
    notesLayer.id = 'ink-notes-layer';
    root.appendChild(notesLayer);

    window.addEventListener('resize', () => {
      svgOverlay.setAttribute('width', window.innerWidth.toString());
      svgOverlay.setAttribute('height', window.innerHeight.toString());
      svgOverlay.setAttribute('viewBox', `0 0 ${window.innerWidth} ${window.innerHeight}`);
    });

    // Active annotations queue (max 2 at once)
    const activeAnnotations = [];

    function registerAnnotation(annotation) {
      while (activeAnnotations.length >= 2) {
        const oldest = activeAnnotations.shift();
        oldest.removeImmediate();
      }
      activeAnnotations.push(annotation);
    }

    function clamp(val, min, max) {
      return Math.min(max, Math.max(min, val));
    }

    function resolveTarget(target) {
      if (!target) return null;
      if (typeof target === 'object' && target !== null && 'x' in target && 'y' in target) {
        const w = target.width || target.w || 10;
        const h = target.height || target.h || 10;
        return {
          left: target.x,
          top: target.y,
          width: w,
          height: h,
          right: target.x + w,
          bottom: target.y + h,
        };
      }
      if (target instanceof Element) {
        const r = target.getBoundingClientRect();
        return {
          left: r.left,
          top: r.top,
          width: r.width,
          height: r.height,
          right: r.right,
          bottom: r.bottom,
        };
      }
      if (typeof target === 'string') {
        try {
          const el = document.querySelector(target);
          if (el) {
            const r = el.getBoundingClientRect();
            return { left: r.left, top: r.top, width: r.width, height: r.height, right: r.right, bottom: r.bottom };
          }
        } catch (e) {}

        const textMatch = target.match(/:has-text\(['"](.+?)['"]\)/) || target.match(/text=(.+)/);
        const needle = textMatch ? textMatch[1].replace(/^["']|["']$/g, '') : target;
        
        const all = Array.from(document.querySelectorAll('*'));
        let best = null;
        for (const el of all) {
          if (el.textContent && el.textContent.includes(needle)) {
            const rect = el.getBoundingClientRect();
            if (rect.width > 0 && rect.height > 0) {
              best = el;
            }
          }
        }
        if (best) {
          const r = best.getBoundingClientRect();
          return { left: r.left, top: r.top, width: r.width, height: r.height, right: r.right, bottom: r.bottom };
        }
      }
      return null;
    }

    /**
     * Checks if a candidate rectangle overlaps other UI text elements
     */
    function calculateOverlapScore(box) {
      let score = 0;
      const elements = document.querySelectorAll('button, strong, span, p, h1, h2, h3, select, input, .inbox-item, .card');
      for (let i = 0; i < elements.length; i++) {
        const el = elements[i];
        if (!el.textContent || el.textContent.trim().length === 0) continue;
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) continue;

        // Check intersection between box and r
        const overlapX = Math.max(0, Math.min(box.x + box.w, r.right) - Math.max(box.x, r.left));
        const overlapY = Math.max(0, Math.min(box.y + box.h, r.bottom) - Math.max(box.y, r.top));
        if (overlapX > 0 && overlapY > 0) {
          score += (overlapX * overlapY);
        }
      }
      return score;
    }

    /**
     * Finds the best placement side that has maximum empty space
     */
    function findBestPlacement(rect, estWidth, estHeight, preferredSide) {
      const sides = preferredSide ? [preferredSide, 'top', 'bottom', 'left', 'right'] : ['top', 'bottom', 'left', 'right'];
      // Unique sides in order
      const uniqueSides = Array.from(new Set(sides));
      let bestSide = uniqueSides[0];
      let minScore = Infinity;

      for (const side of uniqueSides) {
        let x, y;
        if (side === 'top') {
          x = clamp(rect.left + rect.width / 2 - estWidth / 2, 20, window.innerWidth - estWidth - 24);
          y = rect.top - estHeight - 16;
        } else if (side === 'bottom') {
          x = clamp(rect.left + rect.width / 2 - estWidth / 2, 20, window.innerWidth - estWidth - 24);
          y = rect.bottom + 16;
        } else if (side === 'left') {
          x = clamp(rect.left - estWidth - 30, 20, window.innerWidth - estWidth - 24);
          y = rect.top + rect.height / 2 - estHeight / 2;
        } else {
          x = clamp(rect.right + 30, 20, window.innerWidth - estWidth - 24);
          y = rect.top + rect.height / 2 - estHeight / 2;
        }

        // Check screen bounds penalty
        let boundsPenalty = 0;
        if (y < 10 || y + estHeight > window.innerHeight - 10) boundsPenalty += 100000;
        if (x < 10 || x + estWidth > window.innerWidth - 10) boundsPenalty += 100000;

        const score = calculateOverlapScore({ x, y, w: estWidth, h: estHeight }) + boundsPenalty;
        if (score < minScore) {
          minScore = score;
          bestSide = side;
        }
      }
      return bestSide;
    }

    /**
     * Generates a wobbly hand-drawn circle/oval path around (cx, cy)
     */
    function createWobblyCirclePath(cx, cy, rx, ry) {
      const numPoints = 8;
      const points = [];
      const baseAngle = -Math.PI / 2;

      for (let i = 0; i <= numPoints + 2; i++) {
        const angle = baseAngle + (i / numPoints) * 2 * Math.PI;
        const wobbleR = (Math.sin(i * 2.3) * 2.5 + Math.cos(i * 1.7) * 2.0);
        const curRx = rx + wobbleR;
        const curRy = ry + wobbleR * 0.9;
        const spiral = (i > numPoints) ? (i - numPoints) * 2.2 : 0;
        points.push({
          x: cx + (curRx + spiral) * Math.cos(angle),
          y: cy + (curRy + spiral) * Math.sin(angle)
        });
      }

      let d = `M ${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)}`;
      for (let i = 0; i < points.length - 1; i++) {
        const p0 = points[Math.max(0, i - 1)];
        const p1 = points[i];
        const p2 = points[i + 1];
        const p3 = points[Math.min(points.length - 1, i + 2)];

        const cp1x = p1.x + (p2.x - p0.x) / 6;
        const cp1y = p1.y + (p2.y - p0.y) / 6;
        const cp2x = p2.x - (p3.x - p1.x) / 6;
        const cp2y = p2.y - (p3.y - p1.y) / 6;

        d += ` C ${cp1x.toFixed(1)} ${cp1y.toFixed(1)}, ${cp2x.toFixed(1)} ${cp2y.toFixed(1)}, ${p2.x.toFixed(1)} ${p2.y.toFixed(1)}`;
      }
      return d;
    }

    /**
     * Generates a hand-drawn curving arrow with wobbly shaft and two barb lines
     */
    function createCurvedArrowPath(sx, sy, tx, ty) {
      const dx = tx - sx;
      const dy = ty - sy;
      const dist = Math.hypot(dx, dy);
      if (dist < 10) return `M ${sx} ${sy} L ${tx} ${ty}`;

      const mx = (sx + tx) / 2;
      const my = (sy + ty) / 2;
      const perpX = -dy / dist;
      const perpY = dx / dist;
      const curvature = Math.min(28, Math.max(12, dist * 0.15));

      const cpx = mx + perpX * curvature;
      const cpy = my + perpY * curvature;

      const tipAngle = Math.atan2(ty - cpy, tx - cpx);
      const headLen = 16;
      const barb1X = tx - headLen * Math.cos(tipAngle - 0.42);
      const barb1Y = ty - headLen * Math.sin(tipAngle - 0.42);
      const barb2X = tx - headLen * Math.cos(tipAngle + 0.42);
      const barb2Y = ty - headLen * Math.sin(tipAngle + 0.42);

      return `M ${sx.toFixed(1)} ${sy.toFixed(1)} Q ${cpx.toFixed(1)} ${cpy.toFixed(1)} ${tx.toFixed(1)} ${ty.toFixed(1)} ` +
             `M ${tx.toFixed(1)} ${ty.toFixed(1)} L ${barb1X.toFixed(1)} ${barb1Y.toFixed(1)} ` +
             `M ${tx.toFixed(1)} ${ty.toFixed(1)} L ${barb2X.toFixed(1)} ${barb2Y.toFixed(1)}`;
    }

    // 4. ReturnLensInk Public API
    window.ReturnLensInk = {
      circle: function (target, text, options) {
        options = options || {};
        const rect = resolveTarget(target);
        if (!rect) {
          console.warn('[ReturnLensInk] Target not found for circle:', target);
          return null;
        }

        const color = options.color || '#e11d48';
        const padX = options.padX || options.pad || 12;
        const padY = options.padY || options.pad || 8;
        const strokeWidth = options.strokeWidth || 3.5;
        const duration = options.duration || 3000;

        const cx = rect.left + rect.width / 2;
        const cy = rect.top + rect.height / 2;
        const rx = (rect.width / 2) + padX;
        const ry = (rect.height / 2) + padY;

        const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        group.className.baseVal = 'ink-group';

        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', createWobblyCirclePath(cx, cy, rx, ry));
        path.setAttribute('stroke', color);
        path.setAttribute('stroke-width', strokeWidth.toString());
        path.setAttribute('fill', 'none');
        path.setAttribute('stroke-linecap', 'round');
        path.setAttribute('stroke-linejoin', 'round');
        group.appendChild(path);
        svgOverlay.appendChild(group);

        const pathLength = path.getTotalLength() || 400;
        path.style.strokeDasharray = `${pathLength}`;
        path.style.strokeDashoffset = `${pathLength}`;
        path.getBoundingClientRect(); // trigger reflow
        path.style.transition = 'stroke-dashoffset 0.6s cubic-bezier(0.25, 1, 0.5, 1)';
        path.style.strokeDashoffset = '0';

        let noteEl = null;
        if (text) {
          noteEl = document.createElement('div');
          noteEl.className = 'ink-note-bubble';
          noteEl.style.color = color;
          noteEl.textContent = text;
          notesLayer.appendChild(noteEl);

          const estWidth = Math.max(110, text.length * 14 + 16);
          const estHeight = 36;
          const side = findBestPlacement(rect, estWidth, estHeight, options.side || (rect.top > 65 ? 'top' : 'bottom'));

          if (side === 'top') {
            const left = clamp(cx - estWidth / 2, 20, window.innerWidth - estWidth - 24);
            noteEl.style.left = `${left}px`;
            noteEl.style.top = `${Math.max(10, rect.top - ry - estHeight - 6)}px`;
          } else if (side === 'bottom') {
            const left = clamp(cx - estWidth / 2, 20, window.innerWidth - estWidth - 24);
            noteEl.style.left = `${left}px`;
            noteEl.style.top = `${rect.bottom + ry + 10}px`;
          } else if (side === 'right') {
            const left = clamp(rect.right + rx + 16, 20, window.innerWidth - estWidth - 24);
            noteEl.style.left = `${left}px`;
            noteEl.style.top = `${cy - estHeight / 2}px`;
          } else {
            const left = clamp(rect.left - rx - estWidth - 16, 20, window.innerWidth - estWidth - 24);
            noteEl.style.left = `${left}px`;
            noteEl.style.top = `${cy - estHeight / 2}px`;
          }
        }

        const handle = {
          fadeOutAndRemove: function () {
            group.classList.add('ink-fading');
            if (noteEl) noteEl.style.opacity = '0';
            setTimeout(() => {
              if (group.parentNode) group.parentNode.removeChild(group);
              if (noteEl && noteEl.parentNode) noteEl.parentNode.removeChild(noteEl);
            }, 380);
          },
          removeImmediate: function () {
            if (group.parentNode) group.parentNode.removeChild(group);
            if (noteEl && noteEl.parentNode) noteEl.parentNode.removeChild(noteEl);
          }
        };

        registerAnnotation(handle);
        setTimeout(() => {
          handle.fadeOutAndRemove();
        }, duration);

        return handle;
      },

      arrow: function (target, text, options) {
        options = options || {};
        const rect = resolveTarget(target);
        if (!rect) {
          console.warn('[ReturnLensInk] Target not found for arrow:', target);
          return null;
        }

        const color = options.color || '#e11d48';
        const strokeWidth = options.strokeWidth || 3.0;
        const duration = options.duration || 3000;

        const estWidth = Math.max(110, text.length * 14 + 16);
        const estHeight = 36;
        const side = findBestPlacement(rect, estWidth, estHeight, options.fromSide || options.side || 'auto');

        const noteEl = document.createElement('div');
        noteEl.className = 'ink-note-bubble';
        noteEl.style.color = color;
        noteEl.textContent = text;
        notesLayer.appendChild(noteEl);

        let sx, sy, tx, ty;

        if (side === 'right') {
          const noteX = clamp(rect.right + 65, 20, window.innerWidth - estWidth - 24);
          const noteY = rect.top + rect.height / 2 - estHeight / 2;
          noteEl.style.left = `${noteX}px`;
          noteEl.style.top = `${noteY}px`;
          sx = noteX - 8;
          sy = noteY + estHeight / 2;
          tx = rect.right + 8;
          ty = rect.top + rect.height / 2;
        } else if (side === 'left') {
          const noteX = clamp(rect.left - estWidth - 45, 20, window.innerWidth - estWidth - 24);
          const noteY = rect.top + rect.height / 2 - estHeight / 2;
          noteEl.style.left = `${noteX}px`;
          noteEl.style.top = `${noteY}px`;
          sx = noteX + estWidth + 8;
          sy = noteY + estHeight / 2;
          tx = rect.left - 8;
          ty = rect.top + rect.height / 2;
        } else if (side === 'top') {
          const noteX = clamp(rect.left + rect.width / 2 - estWidth / 2, 20, window.innerWidth - estWidth - 24);
          const noteY = Math.max(10, rect.top - estHeight - 24);
          noteEl.style.left = `${noteX}px`;
          noteEl.style.top = `${noteY}px`;
          sx = noteX + estWidth / 2;
          sy = noteY + estHeight + 4;
          tx = rect.left + rect.width / 2;
          ty = rect.top - 8;
        } else {
          // bottom
          const noteX = clamp(rect.left + rect.width / 2 - estWidth / 2, 20, window.innerWidth - estWidth - 24);
          const noteY = rect.bottom + 28;
          noteEl.style.left = `${noteX}px`;
          noteEl.style.top = `${noteY}px`;
          sx = noteX + estWidth / 2;
          sy = noteY - 6;
          tx = rect.left + rect.width / 2;
          ty = rect.bottom + 8;
        }

        const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        group.className.baseVal = 'ink-group';

        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', createCurvedArrowPath(sx, sy, tx, ty));
        path.setAttribute('stroke', color);
        path.setAttribute('stroke-width', strokeWidth.toString());
        path.setAttribute('fill', 'none');
        path.setAttribute('stroke-linecap', 'round');
        path.setAttribute('stroke-linejoin', 'round');
        group.appendChild(path);
        svgOverlay.appendChild(group);

        const pathLength = path.getTotalLength() || 300;
        path.style.strokeDasharray = `${pathLength}`;
        path.style.strokeDashoffset = `${pathLength}`;
        path.getBoundingClientRect();
        path.style.transition = 'stroke-dashoffset 0.6s cubic-bezier(0.25, 1, 0.5, 1)';
        path.style.strokeDashoffset = '0';

        const handle = {
          fadeOutAndRemove: function () {
            group.classList.add('ink-fading');
            noteEl.style.opacity = '0';
            setTimeout(() => {
              if (group.parentNode) group.parentNode.removeChild(group);
              if (noteEl && noteEl.parentNode) noteEl.parentNode.removeChild(noteEl);
            }, 380);
          },
          removeImmediate: function () {
            if (group.parentNode) group.parentNode.removeChild(group);
            if (noteEl && noteEl.parentNode) noteEl.parentNode.removeChild(noteEl);
          }
        };

        registerAnnotation(handle);
        setTimeout(() => {
          handle.fadeOutAndRemove();
        }, duration);

        return handle;
      },

      clear: function () {
        while (activeAnnotations.length > 0) {
          const item = activeAnnotations.shift();
          item.removeImmediate();
        }
      },

      setCursor: function (x, y) {
        updateCursor(x, y);
      },

      clickRipple: function (x, y) {
        spawnRipple(x, y);
      }
    };

    console.log('[ReturnLensInk] Cursor and Ink Overlay loaded successfully.');
  }

  initOverlay();
})();
"""

def build_overlay_js():
    print(f"Reading font from {FONT_PATH}...")
    font_bytes = FONT_PATH.read_bytes()
    b64_str = base64.b64encode(font_bytes).decode("ascii")
    print(f"Font inlined: {len(font_bytes)} bytes -> {len(b64_str)} base64 chars")

    output_code = JS_TEMPLATE.replace("__FONT_BASE64__", b64_str)
    OUTPUT_JS.write_text(output_code, encoding="utf-8")
    print(f"Built {OUTPUT_JS} ({len(output_code)} characters)")

if __name__ == "__main__":
    build_overlay_js()
