# Photo Gallery — Implementation Plan

## Files Changed

| File | Change |
|---|---|
| `PhotoGallery/photo-gallery.json` | Updated URLs + captions; removed unused `featured` flag |
| `src/lib/ui-text.js` | Added 3 gallery text keys to `en` |
| `PhotoGallery/PhotoGallery.jsx` | Full slider + thumbnail + autoplay implementation |
| `PhotoGallery/style.scss` | All gallery styles + responsive fixes |
| `src/lib/__test__/__snapshots__/ui-text.test.js.snap` | Regenerated after `ui-text.js` change |

**Not modified:** `src/pages/home/style.scss`, `components/index.js`

---

## Task 1 — `PhotoGallery/photo-gallery.json`

Replace placeholder content. No `featured` flag — slider treats all photos equally.

```json
[
  { "id": 1, "url": "...", "caption": "Water resources across Fiji" },
  { "id": 2, "url": "...", "caption": "Policy and legislation development" },
  ...
]
```

---

## Task 2 — `src/lib/ui-text.js`

Insert after `homeVideoIframeTitle`, before `homeKeyRolesTitle`:

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

### Imports

```js
import React, { useState, useCallback, useEffect, useRef } from "react";
import "./style.scss";
import photos from "./photo-gallery.json";
```

### State & refs

```js
const [activeIndex, setActiveIndex] = useState(0);
const [paused, setPaused] = useState(false);
const thumbsRef = useRef(null);
```

### Callbacks — all navigation and event handlers defined as `useCallback`

```js
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
    if (e.key === "ArrowLeft") { prev(); }
    else if (e.key === "ArrowRight") { next(); }
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
  const el = thumbsRef.current;
  if (!el) { return; }
  const activeThumb = el.children[activeIndex];
  if (activeThumb) {
    activeThumb.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "smooth" });
  }
}, [activeIndex]);
```

### Effects — registration / cleanup only, no inline logic

```js
// Autoplay — pauses on hover and when tab is hidden
useEffect(() => {
  if (paused) { return () => {}; }
  const id = setInterval(next, 5000);
  return () => { clearInterval(id); };
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
  if (!el) { return () => {}; }
  el.addEventListener("wheel", handleWheel, { passive: false });
  return () => { el.removeEventListener("wheel", handleWheel); };
}, [handleWheel]);

// Keep active thumbnail visible as slides change
useEffect(() => {
  scrollActiveThumb();
}, [scrollActiveThumb]);
```

### JSX structure

```
<section className="page-section gallery-section" id="gallery">
  <div className="section-eyebrow reveal">{text.homeGalleryTitle}</div>
  <h2 className="section-title reveal d1">{text.homeGalleryHeadline}</h2>
  <p className="section-caption reveal d2">{text.homeGalleryText}</p>

  <div
    className="gallery-slider reveal d3"
    onMouseEnter={() => setPaused(true)}
    onMouseLeave={() => setPaused(false)}
  >
    <div className="gallery-track" style={{ transform: `translateX(-${activeIndex * 100}%)` }}>
      {photos.map((photo) => (
        <div key={photo.id} className="gallery-slide">
          <img src={photo.url} alt={photo.caption} loading="lazy" />
          <div className="gallery-slide-caption"><p>{photo.caption}</p></div>
        </div>
      ))}
    </div>

    <button className="gallery-arrow gallery-arrow--prev" ...>← SVG chevron</button>
    <button className="gallery-arrow gallery-arrow--next" ...>→ SVG chevron</button>

    <div className="gallery-dots">
      {photos.map((photo, index) => (
        <button className={`gallery-dot${index === activeIndex ? " gallery-dot--active" : ""}`} ... />
      ))}
    </div>
  </div>

  <div className="gallery-thumbs reveal d4" ref={thumbsRef}>
    {photos.map((photo, index) => (
      <button className={`gallery-thumb${index === activeIndex ? " gallery-thumb--active" : ""}`} ...>
        <img src={photo.url} alt={photo.caption} loading="lazy" />
      </button>
    ))}
  </div>
</section>
```

### ESLint rules satisfied

- `curly: error` — every `if`/`else` body has braces
- `no-undefined: warn` — no `undefined` references
- `prefer-arrow-callback: error` — all callbacks are arrow functions
- `prefer-const: warn` — all bindings use `const`
- `type="button"` on every non-submit `<button>`

---

## Task 4 — `PhotoGallery/style.scss`

All styles wrapped in `.home-content {}` to reach specificity `(0,2,0)` and beat the `.home-content button { background: none; font: inherit }` reset in `home/style.scss`.

### Key rules

```scss
.home-content {
  .gallery-section {
    background: var(--page);
    color: var(--page-ink);
  }

  .gallery-slider {
    width: 100%;          /* breaks aspect-ratio circular size dependency */
    aspect-ratio: 16 / 7;
    overflow: hidden;
    ...
  }

  .gallery-thumbs {
    display: flex;
    overflow-x: auto;
    scroll-snap-type: x mandatory;
    scrollbar-width: none;
    min-width: 0;         /* prevents thumb strip from inflating section width */
    ...
  }

  /* Dots hidden on desktop, shown on mobile */
  .gallery-dots { display: none; }

  /* Thumbnails hidden on mobile, dots shown */
  @media (max-width: 640px) {
    .gallery-thumbs { display: none; }
    .gallery-dots   { display: flex; }
  }

  /* Responsive max-width fix:
     margin: 0 auto on .page-section overrides flex stretch, causing
     the section to size to its intrinsic content width. With aspect-ratio
     on the slider, this resolves to max-width (1200px) on any viewport.
     Overriding max-width to 100% below 1200px fixes the layout.
     Note: Sass does not support min() with mixed units (vw + px). */
  @media (max-width: 1200px) {
    .gallery-section { max-width: 100%; }
  }
}
```

### Responsive breakpoints

| Breakpoint | Changes |
|---|---|
| `≤ 1200px` | `gallery-section: max-width: 100%` (responsive fix) |
| `≤ 1080px` | slider radius 16px, thumb 110px |
| `≤ 900px` | slider radius 14px, thumbs gap 8px, thumb 80px |
| `≤ 640px` | slider aspect 4/3, thumbs hidden, dots shown, arrows 48px |

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

- [x] Gallery section appears between Video and Roles sections
- [x] Arrows advance and wrap correctly
- [x] Thumbnail click jumps to correct slide
- [x] Active thumbnail has teal ring
- [x] Active thumbnail auto-scrolls into view when slide changes
- [x] Keyboard ← / → works
- [x] Mouse wheel over thumbnail strip scrolls horizontally
- [x] Autoplay advances every 5 s
- [x] Hover over slider pauses autoplay
- [x] Tab switch pauses autoplay (visibilitychange)
- [x] Mobile (≤ 640px): thumbnails hidden, dots visible
- [x] Tablet (641–900px): thumbnails visible at reduced size, section fills viewport
- [x] Desktop (> 900px): thumbnails full size
- [x] `reveal` animations fire on scroll
- [x] Snapshot test passes
- [x] ESLint clean
