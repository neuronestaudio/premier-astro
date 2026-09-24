"""Load a deployment's / and /thank-you in a clean headless browser and list every
Google Ads conversion ping plus the dataLayer events, so the GTM wiring can be
verified on a preview URL before it goes live.

    python tools/tagcheck.py https://premier-astro-xxxx.vercel.app [bypass-token]

No gclid, fresh profile: nothing is attributed or counted in Google Ads.
"""
import re, sys

from playwright.sync_api import sync_playwright

ADS_HOSTS = ("googleadservices.com", "googleads.g.doubleclick.net", "google.com/pagead", "google.com.au/pagead",
             "google.com/ccm", "google.com.au/ccm")
base = sys.argv[1].rstrip("/")
bypass = sys.argv[2] if len(sys.argv) > 2 else None
hits, gtm = [], []

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(extra_http_headers={"x-vercel-protection-bypass": bypass} if bypass else {})
    page = ctx.new_page()
    page.on("request", lambda r: hits.append((page.url, r.url)) if any(h in r.url for h in ADS_HOSTS) else None)
    page.on("request", lambda r: gtm.append(r.url) if "googletagmanager.com/gtm.js" in r.url else None)
    page.goto(base + "/", wait_until="networkidle")
    page.wait_for_timeout(2000)
    page.goto(base + "/thank-you", wait_until="networkidle")
    page.wait_for_timeout(4000)
    dl = page.evaluate("JSON.stringify((window.dataLayer||[]).map(e => e && e.event).filter(Boolean))")
    title = page.title()
    browser.close()

print("thank-you title:", title)
print("gtm.js loads:", len(gtm), gtm[:1])
print("dataLayer events on /thank-you:", dl)
labels = set()
for where, url in hits:
    path = re.sub(r"\?.*", "", url)
    label = re.search(r"[?&]label=([^&]+)", url)
    ev = re.search(r"[?&]en=([^&]+)", url)
    if label:
        labels.add(label.group(1))
    print(f"on {where.replace(base, '') or '/'}: {path}  label={label.group(1) if label else '-'}  event={ev.group(1) if ev else '-'}")
print("conversion labels fired:", sorted(labels))
if not hits:
    sys.exit("no Google Ads requests seen")
