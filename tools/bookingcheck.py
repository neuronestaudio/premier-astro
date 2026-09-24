"""End-to-end check of the lead funnel on the BUILT site (dist/), offline:
lands with a gclid, walks the 5-step booking wizard, submits, and intercepts the
GHL webhook POST (answered locally with 200, nothing leaves the machine), then
confirms the payload carries attribution + the thank-you page fires generate_lead.

    python tools/bookingcheck.py
"""
import asyncio, json, mimetypes, sys
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
HOST = "premiermobiledetailing.com.au"
WEBHOOK = "services.leadconnectorhq.com"


def local_file(path):
    p = DIST / path.lstrip("/")
    if p.is_dir():
        p = p / "index.html"
    if not p.is_file() and not p.suffix:
        p2 = DIST / (path.lstrip("/") + "/index.html")
        if p2.is_file():
            return p2
    return p if p.is_file() else None


async def main():
    posted = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1280, "height": 900})

        async def handle(route):
            u = urlparse(route.request.url)
            if u.hostname == WEBHOOK:
                posted.append(json.loads(route.request.post_data or "{}"))
                await route.fulfill(status=200, content_type="application/json", body="{}")
                return
            if u.hostname != HOST:
                await route.abort(); return
            f = local_file(u.path)
            if not f:
                await route.fulfill(status=404, body="nf"); return
            ct = mimetypes.guess_type(str(f))[0] or "application/octet-stream"
            await route.fulfill(status=200, body=f.read_bytes(), content_type="text/javascript" if f.suffix == ".js" else ct)

        await ctx.route("**/*", handle)
        page = await ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)[:200]))
        # land on an ad page first (attribution is captured there), then go to the form
        await page.goto(f"https://{HOST}/ceramic-coating-melbourne?gclid=TESTCLICK&utm_source=google&utm_medium=cpc&utm_campaign=testcamp", wait_until="load")
        await page.wait_for_timeout(500)
        await page.click("text=Start Your Quote")
        await page.wait_for_url("**/booking", timeout=10000)
        await page.wait_for_timeout(500)

        async def pick_card(step, extra=""):
            sel = f".pmd-step[data-step='{step}'] .pmd-card{extra}"
            cards = await page.query_selector_all(sel)
            for c in cards:
                if await c.is_visible():
                    await c.click(); return await c.inner_text()
            raise SystemExit(f"no visible card for step {step} ({sel})")

        s1 = await pick_card(1); await page.click("#btnNext")
        s2 = await pick_card(2); await page.click("#btnNext")
        await page.wait_for_timeout(200)
        await pick_card(3)
        await page.fill("#vehicle", "2021 Tesla Model 3")
        await page.fill("#message", "Automated funnel check (no real booking)")
        await page.click("#btnNext")
        s4 = await pick_card(4); await page.click("#btnNext")
        await page.fill("#name", "Test Funnel")
        await page.fill("#mobile", "0400000000")
        await page.fill("#email", "test@example.com")
        await page.click("#enqBtn")
        await page.wait_for_url("**/thank-you", timeout=10000)
        await page.wait_for_timeout(800)
        dl = await page.evaluate("(window.dataLayer||[]).map(e=>e&&e.event).filter(Boolean)")
        ty_text = await page.evaluate("document.body.innerText.slice(0,300)")
        await browser.close()

    print("steps picked:", s1.strip().splitlines()[0], "|", s2.strip().splitlines()[0], "|", s4.strip().splitlines()[0])
    if not posted:
        sys.exit("FAIL: no webhook POST was made")
    d = posted[0]
    keys = ["first_name", "phone", "email", "service", "service_location", "vehicle", "budget", "gclid", "utm_source", "utm_medium", "utm_campaign", "first_landing_page", "submission_id", "notes"]
    for k in keys:
        print(f"  {k:20s} = {str(d.get(k))[:90]!r}")
    ok = d.get("gclid") == "TESTCLICK" and d.get("utm_campaign") == "testcamp" and "ceramic-coating-melbourne" in d.get("first_landing_page", "") and d.get("submission_id")
    print("dataLayer on /thank-you:", dl)
    print("thank-you text:", ty_text.replace("\n", " ")[:160])
    print("page errors:", errors)
    print("RESULT:", "PASS" if ok and "generate_lead" in dl and not errors else "FAIL")


asyncio.run(main())
