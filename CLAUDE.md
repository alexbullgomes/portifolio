# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Workflow Phases

Follow strict planning → implementation → validation phases. Present a plan and wait for approval before implementing. After implementation, validate (run tests/build) and report results before moving to the next stage.

## Project overview

Static portfolio site for Alex Gomes — a creative director/media producer targeting church and ministry roles. There is no framework and no package manager.

Two parts:
- **`index.html`** — the portfolio itself. Still a single self-contained file with all CSS and JS inline.
- **`blog/`** — the Living Devotional blog. Companion posts for the YouTube channel `@living-devotional`. These pages are *generated* by `tools/build_blog.py` and committed as plain static HTML.

The generator is an authoring convenience, not a deploy requirement: everything it emits is static HTML that opens fine over `file://`. Nothing is compiled at serve time.

Live domain: `https://portfolio.agcreationmkt.cloud` (set as `DOMAIN` at the top of `tools/build_blog.py` — canonical, Open Graph and sitemap URLs all derive from it).

## Development

Open directly in a browser:
```
open index.html
```

Or serve with any static server — required for the blog, since its pages use root-relative paths (`/blog/assets/blog.css`) that do not resolve over `file://`:
```
python3 -m http.server 8080
npx serve .
```

No lint or test commands exist.

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

## Living Devotional blog

One post per YouTube episode. Content lives in `tools/posts/<slug>.json`; the HTML is generated.

```
tools/build_blog.py                  the generator (Python 3 stdlib only)
tools/templates/{post,hub,method}.html   skeletons with {{TOKEN}} placeholders
tools/posts/<slug>.json              content source of truth — one per post
blog/assets/blog.css                 hand-maintained styles (NOT generated)
```

**Adding a post:**

```bash
# 1. scaffold from a video-factory roteiro (pulls title, passage, scene narration as DRAFT)
python3 tools/build_blog.py --new <slug> --youtube <video-id> \
    --roteiro ../video-factory/roteiros/<slug>.json

# 2. rewrite every DRAFT field in Alex's first-person voice, then remove "draft": true

# 3. regenerate everything
python3 tools/build_blog.py
```

The generator writes post pages, `blog/index.html`, `sitemap.xml`, `robots.txt`, `llms.txt`, and the section inside `index.html` between the `<!-- BLOG:START -->` / `<!-- BLOG:END -->` markers. It is idempotent — rerunning with no source changes leaves the git tree clean. **Do not hand-edit generated HTML**; edit the post JSON or the templates and rebuild.

**The generator never writes prose.** It assembles boilerplate — `<head>`, JSON-LD, thumbnails, cross-links. The human copy is authored by hand so the voice stays Alex's.

**SEO contract** (why the structure is the way it is, don't strip it):
- Each post emits `BlogPosting` + `VideoObject` + `FAQPage` + `BreadcrumbList` in one JSON-LD `@graph`. `VideoObject` is what makes the page eligible for Google's video rich result — it's the main path back to the channel.
- `<h2>` sections open with a self-contained, quotable answer before elaborating; AI answer engines extract passages, not pages. The `.quick-answer` box near the top is the featured-snippet and citation target.
- `robots.txt` deliberately **allows** GPTBot / ClaudeBot / PerplexityBot / Google-Extended. The goal is being cited, not blocked.
- The YouTube embed is a click-to-load facade. Never replace it with a bare `<iframe>` — that adds ~700 KB and wrecks LCP.

**Duplicated CSS:** the `.post-grid` / `.post-card` / `.thumb` rules exist in *both* `blog/assets/blog.css` and the inline `<style>` in `index.html`, so each file stays self-contained. Change the thumbnail treatment in both places.

Thumbnails come straight from YouTube (`i.ytimg.com/vi/<id>/maxresdefault.jpg`, falling back to `hqdefault` via `onerror`) and are forced into the site palette with a CSS grayscale + sanctuary/gold multiply gradient + grain overlay. No image files to manage.

## Assets

- `assets/Alex Rodrigues Gomes - curriculo.pdf` — resume PDF (note: the nav's "Download resume" button currently links to `#`, not this file).

## Git Conventions

Never create nested git repositories. Verify you are in the correct repo root before init or commit. Ask before creating PRs and confirm branch state first.

## Scope Confirmation

Before building integrations or complex features (e.g., API integrations), confirm the intended final approach/scope with the user to avoid building work that gets discarded.

## Agent Loops

Do not repeatedly schedule wakeups or wait in loops on sub-agents. If blocked waiting on an agent, surface status to the user rather than looping.