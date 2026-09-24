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
- `/booking` POSTs JSON to the GHL inbound webhook and only then redirects to `/thank-you`,
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
