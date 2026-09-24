"""GTM / conversion-tracking audit for premiermobiledetailing.com.au (or a preview URL).

Walks the key pages in a clean headless browser and records, per page:
container load, gtag IDs, GA4 events, Google Ads events + conversion labels,
Conversion Linker cookie, dataLayer events and JS errors. Starts the booking
wizard (no submission) to trigger form_start, and opens /thank-you directly to
fire the lead conversion. Nothing is submitted; the gclid is fake so Google Ads
cannot attribute or count anything.

    python tools/gtmcheck.py                      # production
    python tools/gtmcheck.py https://preview-url   # a Vercel preview
"""
import sys
from collections import defaultdict
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://premiermobiledetailing.com.au").rstrip("/")
GTM_ID, GA4_ID, AW_ID = "GTM-W8HNHP9H", "G-GZ2L2JR98Z", "AW-10994383596"
LEAD_LABEL = "ZeoZCK_Y7PEcEOz1w_oo"          # "Submit lead form" 7754951727 — the one primary action
GCLID = "GTMCHECK123"
PAGES = ["/ceramic-coating-melbourne?gclid=" + GCLID, "/", "/services/full-detail", "/mobile-detailing/officer", "/booking", "/thank-you"]

ADS_HOSTS = ("googleadservices.com", "doubleclick.net", "google.com/pagead", "google.com.au/pagead", "google.com/ccm", "google.com.au/ccm", "google.com/rmkt")


def classify(req):
    """-> list of (kind, value). GA4 batches several events into one POST body."""
    url = req.url
    u = urlparse(url); q = parse_qs(u.query); host = u.hostname or ""
    if host == "www.googletagmanager.com" and u.path == "/gtm.js":
        return [("gtm", q.get("id", [""])[0])]
    if host == "www.googletagmanager.com" and u.path == "/gtag/js":
        return [("gtag", q.get("id", [""])[0])]
    if "google-analytics.com" in host or "analytics.google.com" in host:
        evs = set(q.get("en", []))
        for line in (req.post_data or "").splitlines():
            evs |= set(parse_qs(line).get("en", []))
        return [("ga4", e) for e in evs] or [("ga4", "?")]
    if any(h in url for h in ADS_HOSTS):
        return [("ads", q.get("en", ["?"])[0] + (":" + q["label"][0] if "label" in q else ""))]
    return []


results, problems, warnings = {}, [], []
with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    hits, errors = defaultdict(set), []
    page.on("request", lambda r: [hits[k].add(v) for k, v in classify(r)])
    page.on("pageerror", lambda e: errors.append(str(e)[:120]))
    for path in PAGES:
        hits.clear(); errors.clear()
        page.goto(BASE + path, wait_until="networkidle")
        page.wait_for_timeout(1500)
        if path == "/booking":  # start the wizard and type into a field (GA4 form_start), never submit
            page.click(".pmd-step[data-step='1'] .pmd-card >> nth=0"); page.click("#btnNext")
            page.click(".pmd-step[data-step='2'] .pmd-card >> visible=true >> nth=0"); page.click("#btnNext")
            page.fill("#vehicle", "GTM check (not submitted)")
            page.wait_for_timeout(3000)
        if path == "/thank-you":
            page.wait_for_timeout(3000)
        dl = page.evaluate("(window.dataLayer||[]).map(e => e && e.event).filter(Boolean)")
        cookies = {c["name"]: c["value"] for c in ctx.cookies()}
        results[path] = {"gtm": sorted(hits["gtm"]), "gtag": sorted(hits["gtag"]), "ga4": sorted(hits["ga4"]), "ads": sorted(hits["ads"]),
                         "dataLayer": [e for e in dl if not e.startswith("gtm.")], "gcl_aw": cookies.get("_gcl_aw", ""), "errors": list(errors)}
    browser.close()

# ---- report
for path, r in results.items():
    print(f"\n{path}")
    print(f"   container : {', '.join(r['gtm']) or 'NOT LOADED'}")
    print(f"   gtag ids  : {', '.join(r['gtag']) or '-'}")
    print(f"   GA4 events: {', '.join(r['ga4']) or '-'}")
    print(f"   Ads events: {', '.join(r['ads']) or '-'}")
    print(f"   dataLayer : {', '.join(r['dataLayer']) or '-'}")
    if r["gcl_aw"]:
        print(f"   _gcl_aw   : {r['gcl_aw'][:40]}")
    if r["errors"]:
        print(f"   JS errors : {r['errors']}")

# ---- assertions
for path, r in results.items():
    if r["gtm"] != [GTM_ID]:
        problems.append(f"{path}: container {r['gtm']} != {GTM_ID}")
    if GA4_ID not in r["gtag"] or AW_ID not in r["gtag"]:
        problems.append(f"{path}: missing gtag config (have {r['gtag']})")
    if "page_view" not in r["ga4"] and "?" not in r["ga4"]:  # "?" = a batched sendBeacon body Playwright cannot read
        problems.append(f"{path}: no GA4 page_view")
    if r["errors"]:
        problems.append(f"{path}: JS errors {r['errors']}")
    labels = {e.split(":", 1)[1] for e in r["ads"] if ":" in e}
    if path == "/thank-you":
        if "generate_lead" not in r["dataLayer"]:
            problems.append("/thank-you: generate_lead not pushed to dataLayer")
        if labels != {LEAD_LABEL}:
            problems.append(f"/thank-you: conversion labels {sorted(labels)} != [{LEAD_LABEL}]")
    elif labels:
        problems.append(f"{path}: conversion label fired outside /thank-you: {sorted(labels)}")
    if path == "/booking" and not ("form_start" in r["ga4"] and any(e.startswith("form_start") for e in r["ads"])):
        warnings.append("/booking: GA4 enhanced-measurement form_start not seen (cosmetic; the conversion does not depend on it)")
landing = results[PAGES[0]]
if GCLID not in landing["gcl_aw"]:
    problems.append(f"Conversion Linker did not store the gclid (_gcl_aw={landing['gcl_aw']!r})")

print("\n" + ("PASS — GTM, GA4, Google Ads conversion + Conversion Linker all wired as expected" if not problems else "FAIL"))
for x in problems:
    print("  ✗ " + x)
for x in warnings:
    print("  ~ " + x)
sys.exit(1 if problems else 0)
