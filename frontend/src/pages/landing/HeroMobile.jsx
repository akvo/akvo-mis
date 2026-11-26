import PropTypes from "prop-types";
import { motion, useReducedMotion } from "framer-motion";

// Front face of the hero flip card: the AIMS mobile app in a phone frame,
// playing the "offline sync" walkthrough GIF. The frame sits at a 3D tilt and
// gently rocks + floats so it feels alive (a product-shot angle rather than a
// flat screenshot). Under prefers-reduced-motion it holds a static tilt and
// shows the final still frame instead of the GIF.
const SPRITE = "/assets/sprites";

const HeroMobile = ({ alt }) => {
  const reduce = useReducedMotion();
  const src = reduce
    ? `${SPRITE}/mobile-sync-7.png`
    : `${SPRITE}/mobile-sync.gif`;

  const float = reduce
    ? { rotateY: -12, rotateX: 5 }
    : { rotateY: [-16, -8, -16], rotateX: [6, 3, 6], y: [0, -12, 0] };
  const floatTx = reduce
    ? { duration: 0 }
    : { duration: 7, repeat: Infinity, ease: "easeInOut" };

  return (
    <div
      className="absolute inset-0 flex items-center justify-center bg-brand-deep"
      style={{ perspective: 1100 }}
    >
      <div
        aria-hidden="true"
        className="absolute h-[70%] w-[70%] rounded-full bg-brand-bright/20 blur-3xl"
      />
      <motion.div
        className="relative h-[94%] aspect-[390/844] overflow-hidden rounded-[2rem] border-[6px] border-brand-frame bg-black shadow-2xl shadow-black/50"
        initial={reduce ? false : { rotateY: -16, rotateX: 6, y: 0 }}
        animate={float}
        transition={floatTx}
      >
        <img src={src} alt={alt} className="h-full w-full object-cover" />
      </motion.div>
    </div>
  );
};

HeroMobile.propTypes = {
  alt: PropTypes.string,
};

HeroMobile.defaultProps = {
  alt: "",
};

export default HeroMobile;
