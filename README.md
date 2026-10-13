# Premier Mobile Detailing — website

Static **Astro** site for premiermobiledetailing.com.au, deployed on **Vercel**
(push `main` → live in ~1 minute). It replaced the Chrome-rendered React
snapshot + `enhance.js` mirror on 24 Sep 2026; every page now ships as plain HTML
that is identical to what a visitor sees — no client-side bundle, no post-load DOM
patching, no prices in the HTML that a script then hides.

## Commands

```bash
npm install
npm run dev        # http://localhost:4321
npm run build      # -> dist/ (one folder per route, dist/<route>/index.html)
npm run preview
```

## Where things live

```
src/layouts/Base.astro          <head> (GTM, favicons, meta/OG/JSON-LD), header + footer variants, drawer, site.js
src/components/Header.astro     nav: variant "home" (the homepage nav) or "page" (every other page)
src/components/Footer.astro     footer: "home" | "suburb" | "compact" | "big" (big takes CTA props)
src/components/MobileDrawer.astro
src/pages/<route>.astro         one file per URL: metadata in frontmatter, body from a partial
src/content-html/<route>.html   the page body (HTML). Edit this to change a page's content.
src/pages/mobile-detailing/[suburb].astro   the 54 suburb pages, from one template + data
src/content-html/mobile-detailing/_template.html   suburb body with @@NAME@@ / @@INTRO@@ / @@FOCUS@@ / @@NEARBY@@
src/data/suburbs.json           per-suburb name, intro, focus line, nearby links, meta + JSON-LD
src/pages/sitemap.xml.ts        builds sitemap.xml from the pages that exist (priorities in src/data)
public/assets/index-BzKcK88v.css  the compiled site CSS (Tailwind build + the pmd-* rules)
public/assets/site.js           runtime behaviour: attribution capture, drawer, FAQ, reveal, about splash, map
public/assets/images, fonts     all media, served from this host (no third-party CDN)
public/assets/vendor/leaflet.*  the Serving-area map (loaded only when scrolled near)
vercel.json                     framework=astro, cleanUrls, no trailing slash, redirects (www, /enquiry, old PPF URLs)
tools/                          how this site was derived from the old mirror (bake → generate → parity → shots)
```

## Editing a page

1. Find the URL's partial in `src/content-html/` and edit the HTML.
2. Title / description / canonical / OG / JSON-LD are in the matching `src/pages/*.astro` frontmatter.
3. `npm run build` and check the page in `dist/`.

A page body may contain `<script>`/`<style>` (booking wizard, TDS viewer, ceramic
carousel) — they are plain HTML and run as-is. Keep `{` and `}` out of `.astro`
templates (Astro treats them as expressions); partials are injected raw so they are safe.

## Adding a suburb page

Add a record to `src/data/suburbs.json` (copy an existing one). The page and
its sitemap entry appear on the next build.

## Tracking and the lead funnel — do not break

- GTM `GTM-W8HNHP9H` loads from `Base.astro` on every page. All vendor tags fire from GTM.
- `site.js` writes first-touch attribution (`gclid`, `gbraid`, `wbraid`, UTMs, `first_landing_page`)
  to `localStorage.premier_attribution`, gap-fill only. The booking form reads it.
- `/booking` POSTs JSON to **`/api/lead`** (`api/lead.js`, a Vercel function that forwards to the GHL inbound
  webhook server-side so ad blockers cannot drop the lead), falls back to the webhook directly, and only then redirects to `/thank-you`,
  which pushes `dataLayer` event `generate_lead` (the Google Ads conversion trigger). `/thank-you` is `noindex`.
- Every "Book Now / Start Your Quote / Get in Touch" CTA is a real `<a href="/booking">`.

## How it was migrated (tools/)

`bake.py` rendered every page of the old mirror in headless Chromium with its React
bundle and `enhance.js` running (third parties blocked) and saved the final DOM.
`generate.py` split those DOMs into layout/header/footer/content, stripped runtime
residue (toast containers, framer-motion hidden states, reveal classes, old CDN
URLs), converted CTA buttons to links, and wrote this source tree; it verifies
every suburb page rebuilds from the template. `parity.py` proves each built page
carries the same text, links, images, meta and JSON-LD as its bake. `shots.py`
screenshots the build and scores it against the bake's screenshots.

## Homepage features added 13 Oct 2026 (hero video, gallery strip, before/after, map, hub)

All hand-written CSS/JS lives in `public/assets/site.css` + `site.js` (bump `?v=` in `Base.astro` when they change).

- **Hero video** (`src/pages/index.astro`, the `before` string): `public/assets/video/hero-reel.{webm,mp4}` is the
  BYD ceramic reel (instagram.com/reel/DR6n1PIEdgO, 720x1280, 18 s, muted, loop). The still `<picture>` stays as first
  paint; `site.js` fades the still out and the video in at **50 %** only once the `playing` event fires, and leaves the
  still alone for `prefers-reduced-motion` / `saveData`.
- **Gallery strip** (`#gallery`, homepage + every suburb page): 12 diagonal cards from `public/assets/work/*.webp`
  (720x960, cut from the originals in `assets/images`). `site.js` clones the set twice so the drift loops seamlessly;
  drag to browse; pauses off-screen and under reduced motion. The markup is generated once by a one-off script, so edit
  both partials (`index.html` and `mobile-detailing/_template.html`) together.
- **Before / after** (`#results`): 4 real Premier pairs (`assets/work/ba-*-{before,after}.webp`, 900x900) cut from the
  composites in the shared drive `08. Asset Library/Before-After`. Pointer drag + arrow keys, `role="slider"`.
- **Service-area map**: Leaflet + OSM raster tiles darkened in CSS (CARTO basemaps now require an API key).
  `[data-pmd-map][data-areas="#pmd-areas-data"]` draws every suburb in the inline JSON as a clickable dot (homepage +
  hub); `[data-focus="lat,lng,Name"]` marks the current suburb (suburb pages, from `@@LAT@@/@@LNG@@`).
- **`/mobile-detailing` hub** (`src/pages/mobile-detailing/index.astro` + `content-html/mobile-detailing/_hub.html`):
  map, directory of all 54 pages grouped by council, BreadcrumbList + ItemList + LocalBusiness(areaServed) JSON-LD.
  Linked from the header "Areas", the drawer, all footers and the homepage directory.
- `src/data/suburbs.json` now carries `lat`, `lng`, `region` (Nominatim, 13 Oct 2026). The `nearby` links were
  re-pointed to pages that exist: 96 of the 265 used to 404 (bayswater-north, cranbourne-east, ...). If a suburb is
  added, give it coordinates and a region or the hub/map will skip it.
