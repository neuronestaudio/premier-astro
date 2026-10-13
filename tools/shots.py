"""Screenshot the built site (dist/) the same way tools/bake.py shot the live
mirror, collect JS errors + failed requests per page, and score each page's
visual difference against _bake/shots/<name>.png.

    python tools/shots.py              # all routes
    python tools/shots.py / /about     # selected
"""
import asyncio, mimetypes, sys, time
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
DIST, BAKE, OUT = ROOT / "dist", ROOT / "_bake", ROOT / "_parity"
HOST = "premiermobiledetailing.com.au"
VIEWPORT = {"width": 1440, "height": 900}
ALLOW_HOSTS = {HOST, "tile.openstreetmap.org"}


def routes():
    rs = ["/"]
    for f in sorted(DIST.rglob("index.html")):
        rel = f.relative_to(DIST).parent.as_posix()
        if rel != ".":
            rs.append("/" + rel)
    return rs


def local_file(path):
    p = DIST / path.lstrip("/")
    if p.is_dir():
        p = p / "index.html"
    if not p.is_file() and not p.suffix:
        p2 = DIST / (path.lstrip("/") + "/index.html")
        if p2.is_file():
            return p2
    return p if p.is_file() else None


async def handle_route(route):
    u = urlparse(route.request.url)
    if u.hostname != HOST:
        if u.hostname in ALLOW_HOSTS:
            await route.continue_()
        else:
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


def score(a_png, b_png):
    from PIL import Image, ImageChops
    a, b = Image.open(a_png).convert("RGB"), Image.open(b_png).convert("RGB")
    w = min(a.width, b.width); h = min(a.height, b.height)
    a, b = a.crop((0, 0, w, h)), b.crop((0, 0, w, h))
    d = ImageChops.difference(a, b).convert("L")
    hist = d.histogram()
    changed = sum(hist[24:]) / (w * h)  # share of pixels that differ noticeably
    return changed, a.height, b.height


async def shoot(ctx, r, sem, results):
    async with sem:
        page = await ctx.new_page()
        page.set_default_timeout(60000)
        errors, failed = [], []
        page.on("pageerror", lambda e: errors.append(str(e)[:160]))
        page.on("requestfailed", lambda q: failed.append(q.url[:100]) if urlparse(q.url).hostname in ALLOW_HOSTS else None)
        page.on("response", lambda rs: failed.append(f"{rs.status} {rs.url[:90]}") if rs.status >= 400 and urlparse(rs.url).hostname == HOST else None)
        await page.goto(f"https://{HOST}{r}?gclid=TESTCLICK", wait_until="load")
        await page.wait_for_timeout(1500)
        h = await page.evaluate("document.documentElement.scrollHeight")
        y = 0
        while y < h:
            await page.evaluate(f"window.scrollTo(0,{y})"); await page.wait_for_timeout(90); y += 600
            h = await page.evaluate("document.documentElement.scrollHeight")
        await page.evaluate("window.scrollTo(0,0)")
        await page.wait_for_timeout(1800)
        await page.evaluate("const s=document.getElementById('pmd-splash'); if(s) s.remove();")
        attr = await page.evaluate("localStorage.getItem('premier_attribution')")
        name = "index" if r == "/" else r.strip("/").replace("/", "__")
        await page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
        await page.close()
        sc = score(BAKE / "shots" / f"{name}.png", OUT / f"{name}.png") if (BAKE / "shots" / f"{name}.png").exists() else (None, 0, 0)
        results.append((r, sc, errors, failed, attr and '"gclid":"TESTCLICK"' in attr))


async def main(selected):
    OUT.mkdir(exist_ok=True)
    rs = selected or routes()
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport=VIEWPORT, device_scale_factor=1)
        await ctx.route("**/*", handle_route)
        sem = asyncio.Semaphore(4)
        await asyncio.gather(*(shoot(ctx, r, sem, results) for r in rs))
        await browser.close()
    results.sort(key=lambda x: -(x[1][0] or 0))
    for r, (ch, hb, hd), errors, failed, attr_ok in results:
        flag = "" if (not errors and not failed and attr_ok) else "  <-- " + "; ".join(errors + failed + ([] if attr_ok else ["attribution NOT captured"]))
        print(f"{(ch or 0)*100:5.1f}% diff  bake_h={hb:5d} dist_h={hd:5d}  {r}{flag}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
