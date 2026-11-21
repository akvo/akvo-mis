import { motion, useReducedMotion } from "framer-motion";
import PropTypes from "prop-types";

// Fade + rise a block into view the first time it scrolls in. `as` picks the
// rendered element (div by default; "li" for list items). Honors
// prefers-reduced-motion by rendering a plain element with no animation.
const EASE = [0.22, 1, 0.36, 1];

const Reveal = ({
  children,
  className = "",
  delay = 0,
  y = 24,
  as = "div",
}) => {
  const reduce = useReducedMotion();

  if (reduce) {
    const Tag = as;
    return <Tag className={className}>{children}</Tag>;
  }

  const MotionTag = motion[as] || motion.div;
  return (
    <MotionTag
      className={className}
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: false, amount: 0.2 }}
      transition={{ duration: 0.6, delay, ease: EASE }}
    >
      {children}
    </MotionTag>
  );
};

Reveal.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string,
  delay: PropTypes.number,
  y: PropTypes.number,
  as: PropTypes.string,
};

export default Reveal;
