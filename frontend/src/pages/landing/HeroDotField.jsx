import { useEffect, useRef } from "react";
import colors from "../../lib/theme";

// Pointer-reactive dot field for the hero. Every dot is drawn on a single
// canvas (per-dot math in a requestAnimationFrame loop) so hundreds stay smooth
// where hundreds of DOM nodes would not. Dots near the pointer brighten and
// grow; the rest breathe faintly. Alpha stays low so it never beats the
// headline's contrast. Renders a static grid under prefers-reduced-motion and
// pauses the loop while the hero is scrolled off-screen.
const SPACING = 30; // px between dots
const BASE_R = 1.1; // resting radius
const MAX_R = 3.2; // radius right under the pointer
const INFLUENCE = 140; // px the pointer reaches
const BASE_ALPHA = 0.1;
const MAX_ALPHA = 0.55;

const prefersReduced = () =>
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const HeroDotField = () => {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const parent = canvas && canvas.parentElement;
    if (!canvas || !parent) {
      return () => {};
    }
    const ctx = canvas.getContext("2d");
    // jsdom (and any environment without 2d canvas) returns null here; bail
    // rather than crash on ctx.setTransform during tests or on old devices.
    if (!ctx) {
      return () => {};
    }
    const reduce = prefersReduced();
    const pointer = { x: 0, y: 0, active: false };
    let width = 0;
    let height = 0;
    let raf = 0;
    let visible = true;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const rect = parent.getBoundingClientRect();
      width = rect.width;
      height = rect.height;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = (t) => {
      ctx.clearRect(0, 0, width, height);
      const breathe = reduce ? 0 : Math.sin(t / 1600) * 0.03;
      for (let y = SPACING / 2; y < height; y += SPACING) {
        for (let x = SPACING / 2; x < width; x += SPACING) {
          let r = BASE_R;
          let a = BASE_ALPHA + breathe;
          if (pointer.active) {
            const dx = x - pointer.x;
            const dy = y - pointer.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < INFLUENCE) {
              const f = 1 - dist / INFLUENCE;
              r = BASE_R + (MAX_R - BASE_R) * f;
              a = BASE_ALPHA + (MAX_ALPHA - BASE_ALPHA) * f;
            }
          }
          ctx.beginPath();
          ctx.fillStyle = `rgba(${colors.dotRgb}, ${a})`;
          ctx.arc(x, y, r, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      if (!reduce && visible) {
        raf = window.requestAnimationFrame(draw);
      } else {
        raf = 0;
      }
    };

    const onMove = (e) => {
      const rect = canvas.getBoundingClientRect();
      pointer.x = e.clientX - rect.left;
      pointer.y = e.clientY - rect.top;
      pointer.active = true;
    };
    const onLeave = () => {
      pointer.active = false;
    };

    resize();
    draw(0);
    window.addEventListener("resize", resize);

    const io = new IntersectionObserver(
      (entries) => {
        visible = entries[0].isIntersecting;
        if (visible && !reduce && !raf) {
          raf = window.requestAnimationFrame(draw);
        }
      },
      { threshold: 0 }
    );
    io.observe(parent);

    if (!reduce) {
      parent.addEventListener("pointermove", onMove);
      parent.addEventListener("pointerleave", onLeave);
    }

    return () => {
      window.removeEventListener("resize", resize);
      parent.removeEventListener("pointermove", onMove);
      parent.removeEventListener("pointerleave", onLeave);
      io.disconnect();
      if (raf) {
        window.cancelAnimationFrame(raf);
      }
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 h-full w-full"
    />
  );
};

export default HeroDotField;
