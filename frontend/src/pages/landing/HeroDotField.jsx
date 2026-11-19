import { useEffect, useRef } from "react";
import PropTypes from "prop-types";

// Dot field drawn on a single canvas (per-dot math in a requestAnimationFrame
// loop) so hundreds stay smooth where hundreds of DOM nodes would not. With
// `interactive` (default) dots near the pointer brighten and grow; with
// `interactive={false}` they animate on their own as a slow radial ripple from
// the centre (used as an autonomous brand-coloured backdrop). Alpha stays low
// so it never beats the foreground; static under prefers-reduced-motion, and the
// loop pauses while off-screen.
const SPACING = 30; // px between dots
const BASE_R = 1.1; // resting radius
const MAX_R = 3.2; // radius right under the pointer
const INFLUENCE = 140; // px the pointer reaches
const BASE_ALPHA = 0.1;
const MAX_ALPHA = 0.55;
const DOT_RGB = "130, 180, 255"; // light blue on the deep-blue hero

const prefersReduced = () =>
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const HeroDotField = ({ interactive = true }) => {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const parent = canvas && canvas.parentElement;
    if (!canvas || !parent) {
      return () => {};
    }
    const ctx = canvas.getContext("2d");
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
      const cx = width / 2;
      const cy = height / 2;
      for (let y = SPACING / 2; y < height; y += SPACING) {
        for (let x = SPACING / 2; x < width; x += SPACING) {
          let r = BASE_R;
          let a = BASE_ALPHA + breathe;
          if (interactive && pointer.active) {
            const dx = x - pointer.x;
            const dy = y - pointer.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < INFLUENCE) {
              const f = 1 - dist / INFLUENCE;
              r = BASE_R + (MAX_R - BASE_R) * f;
              a = BASE_ALPHA + (MAX_ALPHA - BASE_ALPHA) * f;
            }
          } else if (!interactive) {
            // Autonomous: a slow ripple travelling out from the centre, so the
            // grid lives on its own without a pointer to chase.
            const dx = x - cx;
            const dy = y - cy;
            const dist = Math.sqrt(dx * dx + dy * dy);
            const wave = 0.5 + 0.5 * Math.sin(dist * 0.018 - t * 0.0022);
            r = BASE_R + (MAX_R - BASE_R) * wave * 0.65;
            a = BASE_ALPHA + (MAX_ALPHA - BASE_ALPHA) * wave * 0.45;
          }
          ctx.beginPath();
          ctx.fillStyle = `rgba(${DOT_RGB}, ${a})`;
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

    if (interactive && !reduce) {
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
  }, [interactive]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 h-full w-full"
    />
  );
};

HeroDotField.propTypes = {
  interactive: PropTypes.bool,
};

export default HeroDotField;
