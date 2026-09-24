"""Parity gate: every page in dist/ must carry the same visible text, links,
images, meta and JSON-LD as its baked visitor DOM in _bake/.

    python tools/parity.py          # all pages
    python tools/parity.py /about   # one route

Known, intended differences are filtered (CTA buttons became /booking links,
old CDN image URLs became local, the Leaflet map is mounted at runtime).
"""
import json, re, sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
BAKE, DIST = ROOT / "_bake", ROOT / "dist"
CDN_RE = re.compile(r"https://vibe\.filesafe\.space/\d+/(?:attachments|assets)/")
GOOGLE_LOGO = "https://upload.wikimedia.org/wikipedia/commons/2/2f/Google_2015_logo.svg"


def soup_of(path, rewrite):
    html = path.read_text(encoding="utf-8")
    if rewrite:
        html = CDN_RE.sub("/assets/images/", html).replace(GOOGLE_LOGO, "/assets/images/google-logo.svg")
    return BeautifulSoup(html, "html.parser")


def text_of(s):
    s = BeautifulSoup(str(s), "html.parser")
    for t in s.find_all(["script", "style", "noscript"]):
        t.decompose()
    for t in s.select(".leaflet-container, .leaflet-control-container, .tds-modal"):
        t.decompose()  # runtime-built widgets
    return re.sub(r"\s+", " ", s.body.get_text(" ") if s.body else s.get_text(" ")).strip()


def links_of(s):
    return [a.get("href") for a in s.body.find_all("a") if not a.find_parent(class_=["leaflet-container", "tds-modal"])]


def imgs_of(s):
    return [i.get("src") for i in s.body.find_all("img") if not i.find_parent(class_="leaflet-container")]


def meta_of(s):
    m = {"title": s.title.get_text() if s.title else ""}
    for t in s.head.find_all("meta"):
        k = t.get("name") or t.get("property")
        if k and k not in ("viewport", "author"):
            m[k] = t.get("content")
    c = s.head.find("link", rel="canonical")
    m["canonical"] = c.get("href") if c else None
    m["jsonld"] = [json.loads(x.string) for x in s.head.find_all("script", type="application/ld+json")]
    return m


def first_diff(a, b):
    k = next((i for i in range(min(len(a), len(b))) if a[i] != b[i]), min(len(a), len(b)))
    return f"@{k}: BAKE …{a[max(0,k-70):k+90]}…  |  DIST …{b[max(0,k-70):k+90]}…"


def check(route):
    name = "index" if route == "/" else route.strip("/").replace("/", "__")
    dist = DIST / ("index.html" if route == "/" else route.strip("/") + "/index.html")
    if not dist.exists():
        return [f"MISSING dist page {dist}"]
    A = soup_of(BAKE / f"{name}.html", True)
    B = soup_of(dist, False)
    probs = []
    ta, tb = text_of(A), text_of(B)
    if ta != tb:
        probs.append("TEXT " + first_diff(ta, tb))
    from collections import Counter
    ca, cb = Counter(links_of(A)), Counter(links_of(B))
    # CTA <button>s became <a href="/booking">: extra /booking links are intended
    booking_gain = cb["/booking"] - ca["/booking"]
    bad = {h: (ca[h], cb[h]) for h in set(ca) | set(cb) if ca[h] != cb[h]
           and not (h == "/booking" and cb[h] > ca[h])
           and not (h == "/" and ca[h] - cb[h] <= booking_gain)}  # a CTA that pointed at "/" now points at /booking
    if bad:
        probs.append(f"LINKS count changes {dict(list(bad.items())[:8])}")
    ia, ib = Counter(imgs_of(A)), Counter(imgs_of(B))
    LOGO = "/assets/images/45ead650-192d-44cb-8c3f-0ae51ecbbc4b.webp"
    # the old nav carried the logo twice (one per breakpoint); the shared nav carries it once
    HERO = "/assets/images/57982f66-2a3a-44b2-8853-af37ac4c757d.webp"
    badi = {h: (ia[h], ib[h]) for h in set(ia) | set(ib) if ia[h] != ib[h]
            and not (h == LOGO and ia[h] - ib[h] == 1)
            and not (h == HERO and route != "/" and ia[h] - ib[h] == 1)}  # hidden #static-hero picture dropped off non-home pages
    if badi:
        probs.append(f"IMGS count changes {dict(list(badi.items())[:6])}")
    ma, mb = meta_of(A), meta_of(B)
    for k in sorted(set(ma) | set(mb)):
        va, vb = ma.get(k), mb.get(k)
        if k in ("canonical", "og:url", "og:image", "twitter:image") and isinstance(va, str) and va.startswith("/"):
            va = "https://premiermobiledetailing.com.au" + va
        if k == "jsonld":
            va = json.loads(re.sub(r'"(https://premiermobiledetailing\.com\.au)?/', '"https://premiermobiledetailing.com.au/', CDN_RE.sub("/assets/images/", json.dumps(va))))
        if k == "canonical" and va is None and vb:
            continue  # self-canonical added where the old page had none
        if va != vb:
            probs.append(f"META {k}: {str(va)[:90]!r} -> {str(vb)[:90]!r}")
    return probs


def main(sel):
    routes = sel or ["/"] + sorted("/" + p.stem.replace("__", "/") for p in BAKE.glob("*.html") if p.stem != "index")
    bad = 0
    for r in routes:
        p = check(r)
        if p:
            bad += 1
            print(f"✗ {r}")
            for x in p:
                print("    " + x)
        else:
            print(f"✓ {r}")
    print(f"\n{len(routes) - bad}/{len(routes)} pages at parity")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
