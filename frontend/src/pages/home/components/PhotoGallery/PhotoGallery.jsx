import React, { useState, useCallback, useEffect } from "react";
import "./style.scss";
import photos from "./photo-gallery.json";

const PhotoGallery = ({ text }) => {
  const [activeIndex, setActiveIndex] = useState(0);

  const prev = useCallback(() => {
    setActiveIndex((i) => (i > 0 ? i - 1 : photos.length - 1));
  }, []);

  const next = useCallback(() => {
    setActiveIndex((i) => (i < photos.length - 1 ? i + 1 : 0));
  }, []);

  const goTo = useCallback((index) => {
    setActiveIndex(index);
  }, []);

  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === "ArrowLeft") {
        prev();
      } else if (e.key === "ArrowRight") {
        next();
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("keydown", handleKey);
    };
  }, [prev, next]);

  return (
    <section className="page-section gallery-section" id="gallery">
      <div className="section-eyebrow reveal">{text.homeGalleryTitle}</div>
      <h2 className="section-title reveal d1">{text.homeGalleryHeadline}</h2>
      <p className="section-caption reveal d2">{text.homeGalleryText}</p>

      <div className="gallery-slider reveal d3">
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
          &#8249;
        </button>
        <button
          className="gallery-arrow gallery-arrow--next"
          type="button"
          onClick={next}
          aria-label="Next photo"
        >
          &#8250;
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

      <div className="gallery-thumbs reveal d4">
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
