# Background videos

`index.html` is a plain static file — no build step, no framework. Two areas use looping background `<video>` tiles, both sharing the same markup/CSS pattern via the `.bg-video` class:

1. **Contact-sheet strip** (hero, `.contact-sheet > .strip > .frame`) — 8 tiles, 150×100px.
2. **Work thumbnails** (`#work` section, `.work-grid > .work-card > .work-thumb`) — 6 tiles, 120px tall.

All 14 `<video class="bg-video">` tags currently point at the same placeholder test clip.

## How to swap a video

Find the tile in `index.html` and change only its `src`:

```html
<video class="bg-video" src="https://supabasestudio.agcreationmkt.cloud/storage/v1/object/public/portifolio-opt/Wedding_short_2.mp4" autoplay loop muted playsinline preload="metadata"></video>
```

No CSS or JS changes are needed per swap — just replace the URL. Keep clips short and looping cleanly; `object-fit:cover` will crop (not stretch) any aspect ratio to fill the tile.

## Supabase bucket

Files live in the public `portifolio-opt` bucket:

```
https://supabasestudio.agcreationmkt.cloud/storage/v1/object/public/portifolio-opt/<filename>.mp4
```

This is a public, unauthenticated URL — only upload files meant to be publicly visible.

## Required attributes (and why)

| Attribute | Why |
|---|---|
| `autoplay` | Starts playback without user interaction. |
| `muted` | Required by Chrome/Firefox/Safari — unmuted autoplay is blocked everywhere. |
| `loop` | Native looping, no JS needed. |
| `playsinline` | Stops iOS Safari from forcing fullscreen playback. |
| `preload="metadata"` | Fetches just enough to start quickly without fully downloading all instances upfront (there are 14 on one page). |

## CSS contract (`.bg-video`)

```css
.bg-video{
  position:absolute; inset:0;
  width:100%; height:100%;
  object-fit:cover;
  z-index:0;
}
```

Any container using `.bg-video` must have `position:relative; overflow:hidden` (already set on `.frame` and `.work-thumb`), and any text/label content inside it needs `position:relative; z-index:1` to stay visible above the video. The existing `f1`–`f6` gradient classes stay on the container as a fallback color, visible behind the video and if a clip fails to load.

To add this pattern to a new tile elsewhere: give the container `position:relative; overflow:hidden`, drop a `.bg-video` `<video>` in as the first child, and make sure any sibling content has `position:relative; z-index:1`.

## Play/pause enhancement (optional)

A small script at the end of `<body>` uses `IntersectionObserver` to pause videos once they scroll out of view and resume them when back in view — a performance optimization, not a requirement. If JavaScript is disabled or unsupported, every video still autoplays and loops normally via its native attributes; removing the `<script>` block entirely does not break playback.

## Reduced motion

```css
@media (prefers-reduced-motion: reduce){
  .bg-video{ display:none; }
}
```

Users with reduced-motion preferences see the `f1`–`f6` gradient colors instead of moving video.

## Performance note

14 concurrent video elements on one page is a lot of simultaneous requests/decoders. Once real footage replaces the placeholder, use short, compressed, web-optimized clips (small file size, low resolution appropriate to tile size) to keep the page light.
