import { motion, useReducedMotion } from "framer-motion";
import PropTypes from "prop-types";

// Word-by-word reveal: words rise + fade in, staggered, as the heading scrolls
// into view — and replay when it leaves and re-enters (viewport once: false), so
// it animates both on scroll down and scroll up. At rest every word sits at full
// opacity, so the heading keeps its brand colour (the effect never leaves it
// washed out). Honors prefers-reduced-motion.
const EASE = [0.22, 1, 0.36, 1];

const container = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.05 } },
};

const wordVariants = {
  hidden: { opacity: 0, y: "0.45em" },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: EASE } },
};

const ScrollRevealText = ({ text, className = "", as = "h2" }) => {
  const reduce = useReducedMotion();
  const words = text.split(" ");

  if (reduce) {
    const Tag = as;
    return <Tag className={className}>{text}</Tag>;
  }

  const MotionTag = motion[as] || motion.h2;
  return (
    <MotionTag
      className={className}
      aria-label={text}
      variants={container}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: false, amount: 0.4 }}
    >
      {words.map((word, i) => (
        <motion.span
          key={`${word}-${i}`}
          aria-hidden="true"
          variants={wordVariants}
          style={{ display: "inline-block", marginRight: "0.25em" }}
        >
          {word}
        </motion.span>
      ))}
    </MotionTag>
  );
};

ScrollRevealText.propTypes = {
  text: PropTypes.string.isRequired,
  className: PropTypes.string,
  as: PropTypes.string,
};

export default ScrollRevealText;
