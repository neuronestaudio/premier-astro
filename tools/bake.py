"""Bake the visitor-visible DOM of every page on the live static mirror.

The live site is a React SPA snapshot + enhance.js, which rewrites the DOM after
load (header, prices, FAQ, footer tiles...). Crawlers see the pre-JS HTML, visitors
see the post-JS DOM. This renders each route in headless Chromium with the SPA and
enhance.js running (third-party requests blocked), scrolls through so every
IntersectionObserver fires, and serialises the final DOM to _bake/<route>.html.
It also stores a full-page screenshot for later visual diffing.

    python tools/bake.py            # all routes
    python tools/bake.py /about /   # selected routes
"""
import asyncio, mimetypes, os, sys, time
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

LIVE = Path(r"D:\CLIENTS\PREMIER\Premiermobiledetailing")
OUT = Path(__file__).resolve().parent.parent / "_bake"
HOST = "premiermobiledetailing.com.au"
VIEWPORT = {"width": 1440, "height": 900}
CONCURRENCY = 4


def routes():
    rs = ["/"]
    for f in sorted(LIVE.rglob("index.html")):
        if ".git" in f.parts:
            continue
        rel = f.relative_to(LIVE).parent.as_posix()
        if rel != ".":
            rs.append("/" + rel)
    return rs


def local_file(path):
    p = LIVE / path.lstrip("/")
    if p.is_dir():
        p = p / "index.html"
    if not p.is_file() and not p.suffix:
        p2 = LIVE / (path.lstrip("/") + "/index.html")
        if p2.is_file():
            return p2
    return p if p.is_file() else None


async def handle_route(route):
    u = urlparse(route.request.url)
    if u.hostname != HOST:
        await route.abort()
        return
    f = local_file(u.path)
    if not f:
        await route.fulfill(status=404, body="not found")
        return
    ctype = mimetypes.guess_type(str(f))[0] or "application/octet-stream"
    if f.suffix == ".js":
        ctype = "text/javascript"
    await route.fulfill(status=200, body=f.read_bytes(), content_type=ctype)


async def bake_one(ctx, r, sem):
    async with sem:
        page = await ctx.new_page()
        page.set_default_timeout(60000)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        t0 = time.time()
        await page.goto(f"https://{HOST}{r}", wait_until="load")
        await page.wait_for_timeout(4000)  # enhance.js timers run to 3.5s
        # walk the page so every IntersectionObserver fires (reveal, count-up)
        h = await page.evaluate("document.documentElement.scrollHeight")
        y = 0
        while y < h:
            await page.evaluate(f"window.scrollTo(0,{y})")
            await page.wait_for_timeout(90)
            y += 600
            h = await page.evaluate("document.documentElement.scrollHeight")
        await page.evaluate("window.scrollTo(0,0)")
        await page.wait_for_timeout(1800)  # count-up (1.3s) settles to its raw value
        await page.evaluate(
            "['#pmd-splash','#pmd-abtoggle'].forEach(s=>{const e=document.querySelector(s); if(e) e.remove();})"
        )
        html = await page.evaluate("'<!DOCTYPE html>\\n' + document.documentElement.outerHTML")
        name = "index" if r == "/" else r.strip("/").replace("/", "__")
        (OUT / f"{name}.html").write_text(html, encoding="utf-8")
        try:
            await page.screenshot(path=str(OUT / "shots" / f"{name}.png"), full_page=True)
        except Exception as e:  # screenshots are a nice-to-have
            errors.append(f"screenshot: {e}")
        await page.close()
        print(f"{r:55s} {len(html):8d}b {time.time()-t0:5.1f}s" + (f"  ERR {errors}" if errors else ""), flush=True)


async def main(selected):
    OUT.mkdir(exist_ok=True)
    (OUT / "shots").mkdir(exist_ok=True)
    rs = selected or routes()
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport=VIEWPORT, device_scale_factor=1)
        await ctx.route("**/*", handle_route)
        sem = asyncio.Semaphore(CONCURRENCY)
        await asyncio.gather(*(bake_one(ctx, r, sem) for r in rs))
        await browser.close()
    print(f"baked {len(rs)} routes -> {OUT}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
