# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Single-file static portfolio site for Alex Gomes — a creative director/media producer targeting church and ministry roles. There is no framework, no build step, and no package manager. Everything lives in `index.html`.

## Development

Open directly in a browser:
```
open index.html
```

Or serve with any static server to test video autoplay (some browsers block `file://` autoplay):
```
python3 -m http.server 8080
npx serve .
```

No build, lint, or test commands exist.

## Architecture

All HTML, CSS, and JavaScript are inline in a single `index.html`. Structure:
- **CSS custom properties** at `:root` define the full color palette (`--paper`, `--ink`, `--sanctuary`, `--gold`, `--red`).
- **Fonts**: Fraunces (serif headings), Inter (body), IBM Plex Mono (eyebrow labels, tags, code-style text) — loaded from Google Fonts.
- **Sections** in order: `nav` → `header.hero` → `#about` → `#work` → `#skills` → `.avail` strip → `#contact` → `footer`.

## Background video pattern

Both the hero contact-sheet strip (`.frame` tiles, 150×100px) and the work grid thumbnails (`.work-thumb`, 120px tall) use the same `.bg-video` pattern:

```html
<video class="bg-video" src="<supabase-url>" autoplay loop muted playsinline preload="metadata"></video>
```

To swap a video, change only the `src`. No CSS or JS changes needed. All videos are hosted in the public Supabase bucket:
```
https://supabasestudio.agcreationmkt.cloud/storage/v1/object/public/portifolio-opt/<filename>.mp4
```

Any container using `.bg-video` must have `position:relative; overflow:hidden`. Sibling content needs `position:relative; z-index:1` to appear above the video. The `f1`–`f6` gradient classes on containers act as loading/fallback colors.

A small `IntersectionObserver` script at the bottom of `<body>` pauses off-screen videos — removing it does not break playback. `@media (prefers-reduced-motion: reduce)` hides all `.bg-video` elements and shows gradient fallbacks instead.

## Assets

- `assets/Alex Rodrigues Gomes - curriculo.pdf` — resume PDF (note: the nav's "Download resume" button currently links to `#`, not this file).