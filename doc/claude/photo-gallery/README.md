# Photo Gallery — Landing Page

**Status**: Implemented.
**Branch**: `feature/218-add-photo-galleries-to-landing-page-change-address`

---

## Goal

Add a configurable photo gallery section to the landing page (`Home.jsx`), positioned between the Video section and the Roles section. The component is self-contained in its own folder.

---

## Folder Structure

```
src/pages/home/components/PhotoGallery/
├── PhotoGallery.jsx      ← component (slider + thumbnails + autoplay)
├── photo-gallery.json    ← photo config (URLs + captions)
└── style.scss            ← component-scoped styles
```

`components/index.js` already exports from `./PhotoGallery/PhotoGallery` — no change needed there.

---

## Layout — Slider + Thumbnail Strip

```
‹  [              Main Photo (16:7 aspect)              ]  ›

Desktop / Tablet:
  [ thumb 1 (active) | thumb 2 | thumb 3 | thumb 4 | thumb 5 → scrollable ]

Mobile (≤ 640px):
                    ●  ○  ○  ○  ○
```

### Interactions

| Interaction | Behaviour |
|---|---|
| **← / → arrow buttons** | Advance slides |
| **Thumbnail click** | Jump directly to that slide |
| **Dot click** (mobile) | Same as thumbnail click |
| **Keyboard** `ArrowLeft` / `ArrowRight` | Navigate slides |
| **Mouse wheel on thumb strip** | Scroll thumbnails horizontally |
| **Autoplay** | Advances every 5 s |
| **Hover over slider** | Pauses autoplay |
| **Tab switch** | Pauses autoplay via `visibilitychange` |
| **Active thumbnail** | Teal ring + full opacity; auto-scrolls into view |
| **Slide transition** | `translateX` on `.gallery-track` via inline style |

---

## Responsive Breakpoints

| Viewport | Thumbnails | Dots | Thumb width | Slide aspect |
|---|---|---|---|---|
| > 1080px (desktop) | visible, scrollable | hidden | 140px fixed | 16 / 7 |
| 901–1080px | visible, scrollable | hidden | 110px fixed | 16 / 7 |
| 641–900px (tablet) | visible, scrollable | hidden | 80px fixed | 16 / 7 |
| ≤ 640px (mobile) | **hidden** | **visible** | — | 4 / 3 |

Thumbnail strip uses `overflow-x: auto` + `scroll-snap-type: x mandatory` + hidden scrollbar + `min-width: 0`. Thumbnails have fixed width (`flex: 0 0 auto; width: Npx`) so they never shrink regardless of photo count.

### Responsiveness fix

The `.page-section` rule in `home/style.scss` sets `max-width: 1200px; margin: 0 auto`. Inside the flex column of `.home-content`, the `margin: 0 auto` overrides `align-self: stretch`, causing the section to size to its intrinsic content width. The `.gallery-slider`'s `aspect-ratio` creates a circular size dependency that resolves to `max-width` (1200px), making the section 1200px wide even on a 768px viewport.

Fix: `@media (max-width: 1200px) { .gallery-section { max-width: 100% } }` overrides the `max-width` at all sub-1200px viewports. `width: 100%` on `.gallery-slider` breaks the aspect-ratio circular dependency.

---

## Autoplay

- Interval: 5 000 ms
- Pauses when the user hovers over the slider (`onMouseEnter` / `onMouseLeave`)
- Pauses when the browser tab loses focus (`visibilitychange`)
- Resumes automatically when hover ends or tab regains focus

---

## Hook Architecture

All event handlers are named `useCallback` functions. Effects contain only registration / cleanup or a single call — no logic inline.

| Callback | Deps | Purpose |
|---|---|---|
| `prev` | `[]` | Go to previous slide |
| `next` | `[]` | Go to next slide |
| `goTo` | `[]` | Jump to index |
| `handleKey` | `[prev, next]` | Keyboard navigation |
| `handleWheel` | `[]` | Wheel → horizontal thumb scroll |
| `handleVisibility` | `[]` | Pause autoplay on tab switch |
| `scrollActiveThumb` | `[activeIndex]` | Scroll active thumb into view |

| Effect | Deps | Purpose |
|---|---|---|
| Autoplay | `[paused, next]` | `setInterval` / `clearInterval` |
| Document listeners | `[handleKey, handleVisibility]` | `keydown` + `visibilitychange` |
| Thumb wheel | `[handleWheel]` | Non-passive `wheel` on thumb strip |
| Thumb scroll | `[scrollActiveThumb]` | Scroll active thumb into view |

---

## Scope

| In scope | Out of scope |
|---|---|
| `PhotoGallery/PhotoGallery.jsx` — full slider implementation | Backend photo upload / CMS |
| `PhotoGallery/photo-gallery.json` — update URLs + captions | i18n (gallery config is not translated) |
| `PhotoGallery/style.scss` — all gallery styles | Main `home/style.scss` (untouched) |
| `src/lib/ui-text.js` — 3 new section heading keys | Address change (separate issue) |
| Snapshot regeneration | |

---

## Design Decisions

| Decision | Value | Rationale |
|---|---|---|
| Config location | `PhotoGallery/photo-gallery.json` | Co-located with component |
| Style location | `PhotoGallery/style.scss` | Component-scoped; imported via `import "./style.scss"` |
| Main `home/style.scss` | **Not modified** | All gallery styles live in the component folder |
| CSS variable scope | Styles wrapped in `.home-content {}` | Raises specificity to `(0,2,0)` to beat `.home-content button { background: none }` reset |
| Responsive max-width | `@media (max-width: 1200px)` override | Sass doesn't support `min()` with mixed units (`vw` + `px`) |
| `featured` field | Removed from JSON | Slider treats all photos equally |
| Section theme | Light (`var(--page)`) | Sits between video (light) and roles (dark) |
| Text keys | `homeGalleryTitle`, `homeGalleryHeadline`, `homeGalleryText` | Consistent with every other section |
| Transition | `translateX` on `.gallery-track` via inline style | Works for arrow nav and direct thumbnail jumps equally |
| Keyboard listener | `useEffect` on component mount | Scoped, no global state |
| Mobile nav | Dots (not thumbnails) | Thumbnails too small at mobile widths |
| Autoplay | 5 s interval, pause on hover + tab switch | Standard carousel behaviour |
| Hook pattern | All handlers as `useCallback`, effects as registration only | Keeps dependency arrays honest and logic testable in isolation |

---

## Documents

| Document | Purpose |
|---|---|
| [implementation-plan.md](./implementation-plan.md) | Sequenced task breakdown with final code |
