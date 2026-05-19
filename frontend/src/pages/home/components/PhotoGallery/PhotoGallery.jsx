import React, { useState, useCallback, useEffect, useRef } from "react";
import "./style.scss";
import photos from "./photo-gallery.json";

const PhotoGallery = ({ text }) => {
  const [activeIndex, setActiveIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const thumbsRef = useRef(null);
  const didMountRef = useRef(false);

  const prev = useCallback(() => {
    setActiveIndex((i) => (i > 0 ? i - 1 : photos.length - 1));
  }, []);

  const next = useCallback(() => {
    setActiveIndex((i) => (i < photos.length - 1 ? i + 1 : 0));
  }, []);

  const goTo = useCallback((index) => {
    setActiveIndex(index);
  }, []);

  const handleKey = useCallback(
    (e) => {
      if (e.key === "ArrowLeft") {
        prev();
      } else if (e.key === "ArrowRight") {
        next();
      }
    },
    [prev, next]
  );

  const handleWheel = useCallback((e) => {
    e.preventDefault();
    if (thumbsRef.current) {
      thumbsRef.current.scrollLeft += e.deltaY;
    }
  }, []);

  const handleVisibility = useCallback(() => {
    setPaused(document.hidden);
  }, []);

  const scrollActiveThumb = useCallback(() => {
    if (!didMountRef.current) {
      didMountRef.current = true;
      return;
    }
    const el = thumbsRef.current;
    if (!el) {
      return;
    }
    const activeThumb = el.children[activeIndex];
    if (activeThumb) {
      activeThumb.scrollIntoView({
        block: "nearest",
        inline: "nearest",
        behavior: "smooth",
      });
    }
  }, [activeIndex]);

  // Autoplay — pauses on hover and when tab is hidden
  useEffect(() => {
    if (paused) {
      return () => {};
    }
    const id = setInterval(next, 5000);
    return () => {
      clearInterval(id);
    };
  }, [paused, next]);

  // Keyboard nav + tab-visibility pause — both target document
  useEffect(() => {
    document.addEventListener("keydown", handleKey);
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      document.removeEventListener("keydown", handleKey);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [handleKey, handleVisibility]);

  // Convert vertical wheel to horizontal scroll on the thumb strip
  useEffect(() => {
    const el = thumbsRef.current;
    if (!el) {
      return () => {};
    }
    el.addEventListener("wheel", handleWheel, { passive: false });
    return () => {
      el.removeEventListener("wheel", handleWheel);
    };
  }, [handleWheel]);

  // Keep active thumbnail visible as slides change (skip on initial render)
  useEffect(() => {
    scrollActiveThumb();
  }, [scrollActiveThumb]);

  return (
    <section className="page-section gallery-section" id="gallery">
      <div className="section-eyebrow reveal">{text.homeGalleryTitle}</div>
      <h2 className="section-title reveal d1">{text.homeGalleryHeadline}</h2>
      <p className="section-caption reveal d2">{text.homeGalleryText}</p>

      <div
        className="gallery-slider reveal d3"
        onMouseEnter={() => setPaused(true)}
        onMouseLeave={() => setPaused(false)}
      >
        <div
          className="gallery-track"
          style={{ transform: `translateX(-${activeIndex * 100}%)` }}
        >
          {photos.map((photo) => (
            <div key={photo.id} className="gallery-slide">
              <img src={photo.url} alt={photo.caption} loading="lazy" />
              <div className="gallery-slide-caption">
                <p>{photo.caption}</p>
              </div>
            </div>
          ))}
        </div>

        <button
          className="gallery-arrow gallery-arrow--prev"
          type="button"
          onClick={prev}
          aria-label="Previous photo"
        >
          <svg
            width="32"
            height="32"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>
        <button
          className="gallery-arrow gallery-arrow--next"
          type="button"
          onClick={next}
          aria-label="Next photo"
        >
          <svg
            width="32"
            height="32"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </button>

        <div className="gallery-dots">
          {photos.map((photo, index) => (
            <button
              key={photo.id}
              className={`gallery-dot${
                index === activeIndex ? " gallery-dot--active" : ""
              }`}
              type="button"
              onClick={() => goTo(index)}
              aria-label={`Go to photo ${index + 1}`}
            />
          ))}
        </div>
      </div>

      <div className="gallery-thumbs reveal d4" ref={thumbsRef}>
        {photos.map((photo, index) => (
          <button
            key={photo.id}
            className={`gallery-thumb${
              index === activeIndex ? " gallery-thumb--active" : ""
            }`}
            type="button"
            onClick={() => goTo(index)}
            aria-label={`View: ${photo.caption}`}
          >
            <img src={photo.url} alt={photo.caption} loading="lazy" />
          </button>
        ))}
      </div>
    </section>
  );
};

export default PhotoGallery;
