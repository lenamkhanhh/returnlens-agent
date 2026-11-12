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
        font-size: 30px;
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
      let el = null;
      let left = 0, top = 0, width = 10, height = 10;

      if (typeof target === 'object' && target !== null && 'x' in target && 'y' in target) {
        left = target.x;
        top = target.y;
        width = target.width || target.w || 10;
        height = target.height || target.h || 10;
        try {
          el = document.elementFromPoint(left + width / 2, top + height / 2);
        } catch (e) {}
      } else if (target instanceof Element) {
        el = target;
        const r = target.getBoundingClientRect();
        left = r.left; top = r.top; width = r.width; height = r.height;
      } else if (typeof target === 'string') {
        try {
          el = document.querySelector(target);
          if (el) {
            const r = el.getBoundingClientRect();
            left = r.left; top = r.top; width = r.width; height = r.height;
          }
        } catch (e) {}

        if (!el) {
          const textMatch = target.match(/:has-text\(['"](.+?)['"]\)/) || target.match(/text=(.+)/);
          const needle = textMatch ? textMatch[1].replace(/^["']|["']$/g, '') : target;
          const all = Array.from(document.querySelectorAll('*'));
          let best = null;
          for (const cand of all) {
            if (cand.textContent && cand.textContent.includes(needle)) {
              const r = cand.getBoundingClientRect();
              if (r.width > 0 && r.height > 0) {
                best = cand;
              }
            }
          }
          if (best) {
            el = best;
            const r = best.getBoundingClientRect();
            left = r.left; top = r.top; width = r.width; height = r.height;
          }
        }
      }

      // Safeguard against broad containers (.modal-card, #autonomy-bar, .inbox-list)
      if (el && width > 550 && height > 320) {
        // If modal, find inner alert/result/pre/badge
        const sub = el.querySelector('.sandbox-result, .alert, .badge, .modal-title, pre, h3');
        if (sub) {
          const sr = sub.getBoundingClientRect();
          if (sr.width > 0 && sr.height > 0) {
            el = sub;
            left = sr.left; top = sr.top; width = sr.width; height = sr.height;
          }
        } else {
          width = Math.min(width, 420);
          height = Math.min(height, 120);
        }
      } else if (el && width > 900) {
        // e.g. AutonomyBar spanning 1920px
        const sub = el.querySelector('.badge, code, strong, span');
        if (sub) {
          const sr = sub.getBoundingClientRect();
          if (sr.width > 0 && sr.height > 0) {
            el = sub;
            left = sr.left; top = sr.top; width = sr.width; height = sr.height;
          }
        } else {
          width = Math.min(width, 360);
        }
      }

      return {
        left,
        top,
        width,
        height,
        right: left + width,
        bottom: top + height,
        cx: left + width / 2,
        cy: top + height / 2,
        el
      };
    }

    function getOppositeSide(side) {
      if (side === 'left') return 'right';
      if (side === 'right') return 'left';
      if (side === 'top') return 'bottom';
      return 'top';
    }

    /**
     * Checks if a candidate note box overlaps any text node, modal, or control
     * using document.elementsFromPoint and caretRangeFromPoint.
     * Rule: Never over text, never over a modal.
     */
    function checkNoteBoxCollision(box, targetEl) {
      if (box.x < 12 || box.x + box.w > window.innerWidth - 12) return 1000000;
      if (box.y < 12 || box.y + box.h > window.innerHeight - 12) return 1000000;

      let score = 0;

      // 1. Modal collision: "never over a modal"
      const targetInsideModal = targetEl && targetEl.closest && targetEl.closest('.modal-card, .modal, dialog, [role="dialog"]');
      const modals = document.querySelectorAll('.modal-card, .modal, dialog, [role="dialog"]');
      for (let i = 0; i < modals.length; i++) {
        const m = modals[i];
        if (!targetInsideModal || m !== targetInsideModal) {
          const mr = m.getBoundingClientRect();
          if (mr.width > 0 && mr.height > 0) {
            const ox = Math.max(0, Math.min(box.x + box.w, mr.right) - Math.max(box.x, mr.left));
            const oy = Math.max(0, Math.min(box.y + box.h, mr.bottom) - Math.max(box.y, mr.top));
            if (ox > 0 && oy > 0) {
              score += 500000; // Strict: note cannot sit over a modal from outside
            }
          }
        }
      }

      // 2. Check rendered text nodes using elementsFromPoint across a 15-point grid
      const xs = [box.x + 8, box.x + box.w * 0.25, box.x + box.w * 0.5, box.x + box.w * 0.75, box.x + box.w - 8];
      const ys = [box.y + 6, box.y + box.h * 0.5, box.y + box.h - 6];

      for (let xi = 0; xi < xs.length; xi++) {
        for (let yi = 0; yi < ys.length; yi++) {
          const px = xs[xi];
          const py = ys[yi];
          if (px < 0 || px >= window.innerWidth || py < 0 || py >= window.innerHeight) continue;

          // Direct caret / rendered text check if supported
          if (document.caretRangeFromPoint) {
            try {
              const range = document.caretRangeFromPoint(px, py);
              if (range && range.startContainer && range.startContainer.nodeType === Node.TEXT_NODE) {
                const tVal = range.startContainer.nodeValue;
                if (tVal && tVal.trim().length > 0) {
                  if (!targetEl || !targetEl.contains(range.startContainer)) {
                    score += 40000; // Overlapping direct text node
                  }
                }
              }
            } catch (e) {}
          }

          const stack = document.elementsFromPoint(px, py) || [];
          for (let ei = 0; ei < stack.length; ei++) {
            const el = stack[ei];
            if (!el || el.id === 'playwright-cursor-container' || el.id === 'ink-overlay-svg' ||
                el.id === 'ink-notes-layer' || el.closest('#ink-notes-layer')) {
              continue;
            }
            if (targetEl && (el === targetEl || targetEl.contains(el))) {
              continue;
            }

            const tag = el.tagName ? el.tagName.toLowerCase() : '';
            const isTextOrControl = ['button', 'input', 'select', 'textarea', 'label', 'a',
                                     'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'th', 'td', 'p', 'pre', 'code'].includes(tag) ||
                                     (el.className && typeof el.className === 'string' &&
                                      /badge|chip|bubble|title|header|card-title|item-title/i.test(el.className));

            if (isTextOrControl) {
              score += 15000;
            }

            if (el.childNodes && el.childNodes.length > 0) {
              for (let ci = 0; ci < el.childNodes.length; ci++) {
                const cn = el.childNodes[ci];
                if (cn.nodeType === Node.TEXT_NODE && cn.nodeValue && cn.nodeValue.trim().length > 0) {
                  score += 8000;
                  break;
                }
              }
            }
          }
        }
      }

      // 3. Overlap with visible text bounding rects across page
      const textElements = document.querySelectorAll('button, select, input, label, h1, h2, h3, h4, p, span.badge, span.chip, .chat-bubble, .inbox-item-title, .proposal-header, .stat-value, .stat-label, .triad-title');
      for (let i = 0; i < textElements.length; i++) {
        const tel = textElements[i];
        if (!tel.textContent || tel.textContent.trim().length === 0) continue;
        if (targetEl && (tel === targetEl || targetEl.contains(tel))) continue;

        const tr = tel.getBoundingClientRect();
        if (tr.width === 0 || tr.height === 0) continue;

        const overlapX = Math.max(0, Math.min(box.x + box.w, tr.right) - Math.max(box.x, tr.left));
        const overlapY = Math.max(0, Math.min(box.y + box.h, tr.bottom) - Math.max(box.y, tr.top));
        if (overlapX > 0 && overlapY > 0) {
          score += (overlapX * overlapY * 15);
        }
      }

      return score;
    }

    /**
     * Finds the best placement side in empty space with a short arrow (<= 160px).
     * If preferred side overlaps any text or modal, tests the opposite side, then remaining sides.
     */
    function findBestPlacement(targetInfo, estWidth, estHeight, preferredSide, maxArrowDist) {
      maxArrowDist = maxArrowDist || 160;
      const targetRect = targetInfo;
      const targetEl = targetInfo.el;

      const only = preferredSide && preferredSide.indexOf('only-') === 0;
      const pref = only ? preferredSide.slice(5) : (preferredSide && preferredSide !== 'auto' ? preferredSide : 'right');
      const opposite = getOppositeSide(pref);
      const sides = only ? [pref] : [pref, opposite, 'right', 'left', 'bottom', 'top'];
      const uniqueSides = Array.from(new Set(sides));

      let bestPlacement = null;
      let minScore = Infinity;

      for (const side of uniqueSides) {
        let noteX, noteY;
        const gap = (side === 'top' || side === 'bottom') ? 20 : 26;

        if (side === 'right') {
          noteX = targetRect.right + gap;
          noteY = targetRect.top + targetRect.height / 2 - estHeight / 2;
        } else if (side === 'left') {
          noteX = targetRect.left - estWidth - gap;
          noteY = targetRect.top + targetRect.height / 2 - estHeight / 2;
        } else if (side === 'top') {
          noteX = targetRect.left + targetRect.width / 2 - estWidth / 2;
          noteY = targetRect.top - estHeight - gap;
        } else {
          // bottom
          noteX = targetRect.left + targetRect.width / 2 - estWidth / 2;
          noteY = targetRect.bottom + gap;
        }

        noteX = clamp(noteX, 16, window.innerWidth - estWidth - 16);
        noteY = clamp(noteY, 16, window.innerHeight - estHeight - 150);

        // Arrow endpoints
        let sx, sy, tx, ty;
        if (side === 'right') {
          sx = noteX - 4;
          sy = noteY + estHeight / 2;
          tx = targetRect.right + 4;
          ty = targetRect.top + targetRect.height / 2;
        } else if (side === 'left') {
          sx = noteX + estWidth + 4;
          sy = noteY + estHeight / 2;
          tx = targetRect.left - 4;
          ty = targetRect.top + targetRect.height / 2;
        } else if (side === 'top') {
          sx = noteX + estWidth / 2;
          sy = noteY + estHeight + 4;
          tx = targetRect.left + targetRect.width / 2;
          ty = targetRect.top - 4;
        } else {
          // bottom
          sx = noteX + estWidth / 2;
          sy = noteY - 4;
          tx = targetRect.left + targetRect.width / 2;
          ty = targetRect.bottom + 4;
        }

        // Clamp arrow length <= 160 px
        const arrowDist = Math.hypot(tx - sx, ty - sy);
        if (arrowDist > maxArrowDist) {
          const factor = (maxArrowDist - 12) / arrowDist;
          noteX = clamp(tx + (sx - tx) * factor, 16, window.innerWidth - estWidth - 16);
          noteY = clamp(ty + (sy - ty) * factor, 16, window.innerHeight - estHeight - 150);
          if (side === 'right') {
            sx = noteX - 4;
          } else if (side === 'left') {
            sx = noteX + estWidth + 4;
          } else if (side === 'top') {
            sy = noteY + estHeight + 4;
          } else {
            sy = noteY - 4;
          }
        }

        const box = { x: noteX, y: noteY, w: estWidth, h: estHeight };
        const score = checkNoteBoxCollision(box, targetEl);

        if (score < minScore) {
          minScore = score;
          bestPlacement = {
            side,
            noteX,
            noteY,
            sx,
            sy,
            tx,
            ty,
            score
          };
          if (score === 0 && side === pref) {
            break; // optimal placement matching preference
          }
        }
      }

      return bestPlacement || {
        side: 'bottom',
        noteX: targetRect.left,
        noteY: targetRect.bottom + 20,
        sx: targetRect.left + estWidth / 2,
        sy: targetRect.bottom + 16,
        tx: targetRect.left + targetRect.width / 2,
        ty: targetRect.bottom + 4,
        score: 999
      };
    }

    /**
     * Generates a wobbly hand-drawn circle/oval path hugging (cx, cy)
     */
    function createWobblyCirclePath(cx, cy, rx, ry) {
      // Hand-drawn rounded rectangle that encloses the whole target box,
      // with a small overshoot at the end like a pen stroke.
      const r = Math.min(ry, 16);
      const L = cx - rx, R = cx + rx, T = cy - ry, B = cy + ry;
      const j = (k) => (Math.sin(k * 2.7) * 1.4 + Math.cos(k * 1.3) * 0.9);
      let d = `M ${(L + r + 6).toFixed(1)} ${(T + j(1)).toFixed(1)}`;
      d += ` Q ${((L + R) / 2).toFixed(1)} ${(T - 2 + j(2)).toFixed(1)}, ${(R - r).toFixed(1)} ${(T + j(3)).toFixed(1)}`;
      d += ` Q ${(R + 1).toFixed(1)} ${(T - 1).toFixed(1)}, ${(R + j(4)).toFixed(1)} ${(T + r).toFixed(1)}`;
      d += ` Q ${(R + 2 + j(5)).toFixed(1)} ${cy.toFixed(1)}, ${(R + j(6)).toFixed(1)} ${(B - r).toFixed(1)}`;
      d += ` Q ${(R + 1).toFixed(1)} ${(B + 1).toFixed(1)}, ${(R - r).toFixed(1)} ${(B + j(7)).toFixed(1)}`;
      d += ` Q ${((L + R) / 2).toFixed(1)} ${(B + 2 + j(8)).toFixed(1)}, ${(L + r).toFixed(1)} ${(B + j(9)).toFixed(1)}`;
      d += ` Q ${(L - 1).toFixed(1)} ${(B + 1).toFixed(1)}, ${(L + j(10)).toFixed(1)} ${(B - r).toFixed(1)}`;
      d += ` Q ${(L - 2 + j(11)).toFixed(1)} ${cy.toFixed(1)}, ${(L + j(12)).toFixed(1)} ${(T + r).toFixed(1)}`;
      d += ` Q ${(L - 1).toFixed(1)} ${(T - 3).toFixed(1)}, ${(L + r + 22).toFixed(1)} ${(T - 4).toFixed(1)}`;
      return d;
    }

    /**
     * Generates a hand-drawn curving arrow with wobbly shaft and two barb lines
     */
    function createCurvedArrowPath(sx, sy, tx, ty) {
      const dx = tx - sx;
      const dy = ty - sy;
      const dist = Math.hypot(dx, dy);
      if (dist < 8) return `M ${sx} ${sy} L ${tx} ${ty}`;

      const mx = (sx + tx) / 2;
      const my = (sy + ty) / 2;
      const perpX = -dy / dist;
      const perpY = dx / dist;
      const curvature = Math.min(22, Math.max(8, dist * 0.14));

      const cpx = mx + perpX * curvature;
      const cpy = my + perpY * curvature;

      const tipAngle = Math.atan2(ty - cpy, tx - cpx);
      const headLen = 14;
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
        // Padding <= 12 px, diameter <= target + 24 px
        const padX = Math.min(14, Math.max(8, options.padX !== undefined ? options.padX : (options.pad !== undefined ? options.pad : 12)));
        const padY = Math.min(12, Math.max(6, options.padY !== undefined ? options.padY : (options.pad !== undefined ? options.pad : 8)));
        const strokeWidth = options.strokeWidth || 4.2;
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

        let noteEl = null;
        let arrowPath = null;

        if (text) {
          noteEl = document.createElement('div');
          noteEl.className = 'ink-note-bubble';
          noteEl.style.color = color;
          noteEl.textContent = text;
          notesLayer.appendChild(noteEl);

          const estWidth = Math.max(120, text.length * 15 + 28);
          const estHeight = 44;
          const placement = findBestPlacement(rect, estWidth, estHeight, options.side || 'auto', 160);

          noteEl.style.left = `${placement.noteX}px`;
          noteEl.style.top = `${placement.noteY}px`;

          // Connect note to circle with a short curved arrow
          arrowPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
          arrowPath.setAttribute('d', createCurvedArrowPath(placement.sx, placement.sy, placement.tx, placement.ty));
          arrowPath.setAttribute('stroke', color);
          arrowPath.setAttribute('stroke-width', (strokeWidth * 0.85).toString());
          arrowPath.setAttribute('fill', 'none');
          arrowPath.setAttribute('stroke-linecap', 'round');
          arrowPath.setAttribute('stroke-linejoin', 'round');
          group.appendChild(arrowPath);
        }

        svgOverlay.appendChild(group);

        const pathLength = path.getTotalLength() || 400;
        path.style.strokeDasharray = `${pathLength}`;
        path.style.strokeDashoffset = `${pathLength}`;
        path.getBoundingClientRect();
        path.style.transition = 'stroke-dashoffset 0.35s cubic-bezier(0.25, 1, 0.5, 1)';
        path.style.strokeDashoffset = '0';

        if (arrowPath) {
          const aLen = arrowPath.getTotalLength() || 200;
          arrowPath.style.strokeDasharray = `${aLen}`;
          arrowPath.style.strokeDashoffset = `${aLen}`;
          arrowPath.style.transition = 'stroke-dashoffset 0.45s cubic-bezier(0.25, 1, 0.5, 1) 0.1s';
          arrowPath.style.strokeDashoffset = '0';
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
        const strokeWidth = options.strokeWidth || 4.0;
        const duration = options.duration || 3000;

        const noteEl = document.createElement('div');
        noteEl.className = 'ink-note-bubble';
        noteEl.style.color = color;
        noteEl.textContent = text;
        notesLayer.appendChild(noteEl);

        const estWidth = Math.max(120, text.length * 15 + 28);
        const estHeight = 44;
        const placement = findBestPlacement(rect, estWidth, estHeight, options.fromSide || options.side || 'auto', 160);

        noteEl.style.left = `${placement.noteX}px`;
        noteEl.style.top = `${placement.noteY}px`;

        const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        group.className.baseVal = 'ink-group';

        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', createCurvedArrowPath(placement.sx, placement.sy, placement.tx, placement.ty));
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
        path.style.transition = 'stroke-dashoffset 0.35s cubic-bezier(0.25, 1, 0.5, 1)';
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
          item.fadeOutAndRemove();
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
