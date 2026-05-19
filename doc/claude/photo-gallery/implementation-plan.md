# Photo Gallery — Implementation Plan

## Files to Change

| File | Change |
|---|---|
| `PhotoGallery/photo-gallery.json` | Update URLs + captions; remove unused `featured` flag |
| `src/lib/ui-text.js` | Add 3 gallery text keys to `en` |
| `PhotoGallery/PhotoGallery.jsx` | Full slider + thumbnail strip implementation |
| `PhotoGallery/style.scss` | All gallery styles (was empty) |
| `src/lib/__test__/__snapshots__/ui-text.test.js.snap` | Regenerate after `ui-text.js` change |

**Not modified:** `src/pages/home/style.scss`, `components/index.js`

---

## Task 1 — `PhotoGallery/photo-gallery.json`

Replace placeholder content. No `featured` flag — slider treats all photos equally.

```json
[
  {
    "id": 1,
    "url": "https://images.unsplash.com/photo-1642450909999-7106494ef779?q=80&w=2070&auto=format&fit=crop",
    "caption": "Water resources across Fiji"
  },
  {
    "id": 2,
    "url": "https://images.unsplash.com/photo-1450101499163-c8848c66ca85?q=80&w=2070&auto=format&fit=crop",
    "caption": "Policy and legislation development"
  },
  {
    "id": 3,
    "url": "https://images.unsplash.com/photo-1708807472445-d33589e6b090?q=80&w=1974&auto=format&fit=crop",
    "caption": "Compliance monitoring operations"
  },
  {
    "id": 4,
    "url": "https://plus.unsplash.com/premium_photo-1661964131234-fda88ca041c5?q=80&w=2071&auto=format&fit=crop",
    "caption": "Water Authority of Fiji oversight"
  },
  {
    "id": 5,
    "url": "/assets/technical-advisory.jpg",
    "caption": "Technical and policy advisory"
  }
]
```

All URLs are already used in the project (`ui-text.js` role cards), so they are confirmed to load.

---

## Task 2 — `src/lib/ui-text.js`

Insert after `homeVideoIframeTitle` (line ~811), before `homeKeyRolesTitle`:

```jsx
homeGalleryTitle: "Photo Gallery",
homeGalleryHeadline: (
  <Fragment>
    Images from <span className="accent">the field</span>.
  </Fragment>
),
homeGalleryText:
  "A selection of photos from water and sewerage operations across Fiji.",
```

---

## Task 3 — `PhotoGallery/PhotoGallery.jsx`

Full replacement of the stub. Top of file:

```js
import React, { useState, useCallback, useEffect } from "react";
import "./style.scss";
import photos from "./photo-gallery.json";
```

Component tree:

```
<section className="page-section gallery-section" id="gallery">
  <div className="section-eyebrow reveal">{text.homeGalleryTitle}</div>
  <h2 className="section-title reveal d1">{text.homeGalleryHeadline}</h2>
  <p className="section-caption reveal d2">{text.homeGalleryText}</p>

  <div className="gallery-slider reveal d3">
    <div className="gallery-track" style={{ transform: `translateX(-${activeIndex * 100}%)` }}>
      {photos.map((photo) => (
        <div key={photo.id} className="gallery-slide">
          <img src={photo.url} alt={photo.caption} loading="lazy" />
          <div className="gallery-slide-caption">
            <p>{photo.caption}</p>
          </div>
        </div>
      ))}
    </div>

    <button className="gallery-arrow gallery-arrow--prev" type="button" onClick={prev} aria-label="Previous photo">‹</button>
    <button className="gallery-arrow gallery-arrow--next" type="button" onClick={next} aria-label="Next photo">›</button>

    <div className="gallery-dots">
      {photos.map((photo, index) => (
        <button
          key={photo.id}
          className={`gallery-dot${index === activeIndex ? " gallery-dot--active" : ""}`}
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
        className={`gallery-thumb${index === activeIndex ? " gallery-thumb--active" : ""}`}
        type="button"
        onClick={() => goTo(index)}
        aria-label={`View: ${photo.caption}`}
      >
        <img src={photo.url} alt={photo.caption} loading="lazy" />
      </button>
    ))}
  </div>
</section>
```

State and callbacks:

```js
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
```

ESLint rules to satisfy (`frontend/.eslintrc.json`):
- `curly: error` — every `if`/`else` body must have braces
- `no-undefined: warn` — do not reference `undefined`
- `prefer-arrow-callback: error` — all map/event callbacks must be arrow functions
- `prefer-const: warn` — use `const` for all non-reassigned bindings
- `type="button"` on every non-submit `<button>`

---

## Task 4 — `PhotoGallery/style.scss`

Write from scratch (file is currently empty). Styles are standalone — no `.home-content` wrapper needed because CSS variables cascade from the ancestor in the DOM.

### Base styles

```scss
.gallery-section {
  background: var(--page);
  color: var(--page-ink);
}

.gallery-slider {
  margin-top: 56px;
  position: relative;
  overflow: hidden;
  border-radius: 20px;
  border: 1px solid var(--rule);
  aspect-ratio: 16 / 7;
  box-shadow: 0 20px 60px -20px oklch(0 0 0 / 0.2);
}

.gallery-track {
  display: flex;
  height: 100%;
  transition: transform 0.5s cubic-bezier(0.2, 0.7, 0.2, 1);
}

.gallery-slide {
  position: relative;
  min-width: 100%;
  height: 100%;

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
}

.gallery-slide-caption {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 32px 32px 24px;
  background: linear-gradient(180deg, transparent 0%, oklch(0 0 0 / 0.6) 100%);

  p {
    margin: 0;
    color: white;
    font-size: 15px;
    font-weight: 500;
    letter-spacing: 0.01em;
  }
}

.gallery-arrow {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: oklch(1 0 0 / 0.12);
  border: 1px solid oklch(1 0 0 / 0.25);
  backdrop-filter: blur(8px);
  color: white;
  font-size: 28px;
  display: grid;
  place-items: center;
  cursor: pointer;
  transition: background 0.2s, transform 0.2s;
  z-index: 2;
  line-height: 1;

  &:hover {
    background: oklch(1 0 0 / 0.22);
    transform: translateY(-50%) scale(1.05);
  }

  &--prev { left: 16px; }
  &--next { right: 16px; }
}

/* Dots — hidden on desktop/tablet, shown on mobile via @media */
.gallery-dots {
  position: absolute;
  bottom: 14px;
  left: 50%;
  transform: translateX(-50%);
  display: none;
  gap: 8px;
  z-index: 2;
}

.gallery-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: oklch(1 0 0 / 0.4);
  border: none;
  padding: 0;
  cursor: pointer;
  transition: background 0.2s, transform 0.2s;

  &--active {
    background: var(--teal);
    transform: scale(1.3);
  }
}

/* Thumbnail strip — scrollable, hidden on mobile via @media */
.gallery-thumbs {
  margin-top: 16px;
  display: flex;
  gap: 12px;
  overflow-x: auto;
  scroll-snap-type: x mandatory;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;

  &::-webkit-scrollbar { display: none; }
}

.gallery-thumb {
  flex: 0 0 auto;
  width: 140px;
  scroll-snap-align: start;
  aspect-ratio: 4 / 3;
  border-radius: 10px;
  overflow: hidden;
  border: 2px solid transparent;
  padding: 0;
  cursor: pointer;
  opacity: 0.6;
  transition: border-color 0.2s, transform 0.2s, opacity 0.2s;

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    transition: transform 0.3s;
  }

  &:hover {
    opacity: 0.85;
    transform: translateY(-2px);

    img { transform: scale(1.05); }
  }

  &--active {
    border-color: var(--teal);
    opacity: 1;
    box-shadow: 0 0 0 2px oklch(0.78 0.11 195 / 0.25);
  }
}
```

### Responsive overrides (append to same file)

```scss
@media (max-width: 1080px) {
  .gallery-slider { border-radius: 16px; }
  .gallery-thumb { width: 110px; }
}

@media (max-width: 900px) {
  /* Tablet — still shows thumbnails, scrollable at reduced size */
  .gallery-slider { border-radius: 14px; }
  .gallery-thumbs { gap: 8px; }
  .gallery-thumb { width: 80px; border-radius: 8px; }
}

@media (max-width: 640px) {
  /* Mobile — hide thumbnails, show dots */
  .gallery-slider { aspect-ratio: 4 / 3; border-radius: 12px; }
  .gallery-thumbs { display: none; }
  .gallery-dots { display: flex; }
  .gallery-arrow { width: 36px; height: 36px; font-size: 22px; }
  .gallery-arrow--prev { left: 10px; }
  .gallery-arrow--next { right: 10px; }
}
```

---

## Task 5 — Snapshot update

```bash
./dc.sh exec -T frontend npx react-scripts test \
  --testPathPattern="ui-text" \
  --updateSnapshot \
  --watchAll=false
```

---

## Task 6 — Lint check

```bash
./dc.sh exec -T frontend npx eslint src/pages/home/components/PhotoGallery/PhotoGallery.jsx
```

---

## Verification checklist

- [ ] Gallery section appears between Video and Roles sections
- [ ] Arrows advance and wrap correctly
- [ ] Thumbnail click jumps to correct slide
- [ ] Active thumbnail has teal ring
- [ ] Keyboard ← / → works
- [ ] Mobile (≤ 640px): thumbnails hidden, dots visible
- [ ] Tablet (641–900px): thumbnails visible at reduced size
- [ ] Desktop (> 900px): thumbnails full size
- [ ] `reveal` animations fire on scroll
- [ ] Snapshot test passes
- [ ] ESLint clean
