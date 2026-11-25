import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import HeroDemo from "./HeroDemo";
import HeroMobile from "./HeroMobile";

// 3D flip card for the hero: front is the mobile app (HeroMobile), back is the
// interactive dashboard (HeroDemo). It auto-flips front -> back -> front on a
// loop, and pauses while hovered so the dashboard stays usable. Each face is
// backface-hidden; the back is pre-rotated 180deg so it reads correctly (not
// mirrored) once the card turns. Under prefers-reduced-motion it skips the flip
// and just shows the dashboard.
const FRONT_MS = 4800; // mobile scene on screen
const BACK_MS = 5200; // dashboard on screen
// Each face must carry its OWN rotateY so backface-visibility hides it once the
// card turns past 90deg — without the explicit rotateY(0) on the front, the
// browser keeps painting the front's backface and the phone shows up mirrored.
const FRONT_FACE = {
  backfaceVisibility: "hidden",
  WebkitBackfaceVisibility: "hidden",
  transform: "rotateY(0deg)",
};
const BACK_FACE = {
  backfaceVisibility: "hidden",
  WebkitBackfaceVisibility: "hidden",
  transform: "rotateY(180deg)",
};

const HeroShowcase = ({ demo }) => {
  const reduce = useReducedMotion();
  const [flipped, setFlipped] = useState(false);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (reduce || paused) {
      return () => {};
    }
    const ms = flipped ? BACK_MS : FRONT_MS;
    const timer = setTimeout(() => setFlipped((f) => !f), ms);
    return () => clearTimeout(timer);
  }, [flipped, paused, reduce]);

  if (reduce) {
    return <HeroDemo demo={demo} />;
  }

  return (
    <div
      className="relative w-full"
      style={{ perspective: 1600 }}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      {/* Manual flip so visitors don't wait for the auto timer. */}
      <button
        type="button"
        onClick={() => setFlipped((f) => !f)}
        aria-label={demo.flipLabel}
        className="absolute right-3 bottom-3 z-20 flex h-9 w-9 items-center justify-center rounded-full border border-white/25 bg-black/40 text-white/90 backdrop-blur-sm transition-colors hover:bg-black/60"
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M4 9a8 8 0 0 1 13.7-3.3L20 8M20 3v5h-5M20 15a8 8 0 0 1-13.7 3.3L4 16M4 21v-5h5"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      <motion.div
        className="relative"
        style={{ transformStyle: "preserve-3d" }}
        animate={{ rotateY: flipped ? 180 : 0 }}
        transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
      >
        {/* Back (dashboard): in flow, sets the card height; pre-rotated 180. */}
        <div style={BACK_FACE}>
          <HeroDemo demo={demo} />
        </div>
        {/* Front (mobile): overlays the same box. */}
        <div className="absolute inset-0" style={FRONT_FACE}>
          <HeroMobile alt={demo.mobileAlt} />
        </div>
      </motion.div>
    </div>
  );
};

HeroShowcase.propTypes = {
  demo: HeroDemo.propTypes.demo,
};

export default HeroShowcase;
