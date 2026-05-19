# Photo Gallery — Landing Page

**Status**: Plan approved, ready to implement.
**Branch**: `feature/218-add-photo-galleries-to-landing-page-change-address`

---

## Goal

Add a configurable photo gallery section to the landing page (`Home.jsx`), positioned between the Video section and the Roles section. The component is self-contained in its own folder.

---

## Folder Structure

```
src/pages/home/components/PhotoGallery/
├── PhotoGallery.jsx      ← component (slider + thumbnails)
├── photo-gallery.json    ← photo config (URLs + captions)
└── style.scss            ← component-scoped styles
```

`components/index.js` already exports from `./PhotoGallery/PhotoGallery` — no change needed there.

---

## Layout — Slider + Thumbnail Strip

```
‹  [              Main Photo (16:7 aspect)              ]  ›

Desktop / Tablet:
  [ thumb 1 (active) | thumb 2 | thumb 3 | thumb 4 | thumb 5 ]

Mobile (≤ 640px):
                    ●  ○  ○  ○  ○
```

### Interactions
- **← / → arrow buttons** overlaid on main slide edges — advance slides
- **Thumbnail click** — jump directly to that slide
- **Dot click** (mobile) — same as thumbnail click
- **Keyboard** — `ArrowLeft` / `ArrowRight` keys navigate slides
- **Active thumbnail** — teal ring (`--teal` CSS var) + full opacity
- **Transition** — `translateX` on `.gallery-track` via inline style

---

## Responsive Breakpoints

| Viewport | Thumbnails | Dots | Thumb width | Slide aspect |
|---|---|---|---|---|
| > 1080px (desktop) | visible, scrollable | hidden | 140px fixed | 16 / 7 |
| 901–1080px | visible, scrollable | hidden | 110px fixed | 16 / 7 |
| 641–900px (tablet) | visible, scrollable | hidden | 80px fixed | 16 / 7 |
| ≤ 640px (mobile) | **hidden** | **visible** | — | 4 / 3 |

Thumbnail strip uses `overflow-x: auto` + `scroll-snap-type: x mandatory` + hidden scrollbar. Thumbnails have fixed width (`flex: 0 0 auto; width: Npx`) so they never shrink regardless of photo count.

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
| Config location | `PhotoGallery/photo-gallery.json` | Co-located with component; import is `"./photo-gallery.json"` |
| Style location | `PhotoGallery/style.scss` | Component-scoped; imported via `import "./style.scss"` in JSX |
| Main `home/style.scss` | **Not modified** | All gallery styles live in the component folder |
| CSS variable scope | Standalone rules (no `.home-content` wrapper needed) | Variables cascade from ancestor `.home-content` in the DOM |
| `featured` field | Removed from JSON | Slider treats all photos equally |
| Section theme | Light (`var(--page)`) | Sits between video (light) and roles (dark) |
| Text keys | `homeGalleryTitle`, `homeGalleryHeadline`, `homeGalleryText` | Consistent with every other section |
| Transition | `translateX` on `.gallery-track` via inline style | Works for arrow nav and direct thumbnail jumps equally |
| Keyboard listener | `useEffect` on component mount | Scoped, no global state |
| Mobile nav | Dots (not thumbnails) | Thumbnails too small at mobile widths |

---

## Documents

| Document | Purpose |
|---|---|
| [implementation-plan.md](./implementation-plan.md) | Sequenced, checklisted task breakdown ready to execute |
