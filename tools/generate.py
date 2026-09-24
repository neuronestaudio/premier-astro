"""Generate the Astro source tree from the baked visitor-visible DOM in _bake/.

Run tools/bake.py first. This script:
  - splits every baked page into head metadata, header, content, footer
  - normalises the header to two variants (home / page) and the footer to four
    (home / suburb / compact / big+props); one-off footers stay inline
  - strips React/framer/enhance.js runtime residue (toast containers, framer
    opacity-0 states, reveal classes, price-scrub markers, old CDN image URLs)
  - turns quote/booking CTA <button>s into real <a href="/booking"> links
  - writes src/content-html/<route>.html partials + src/pages/<route>.astro
  - derives the 54 suburb pages into one template + src/data/suburbs.json and
    verifies every suburb rebuilds to the baked text
"""
import copy, json, re, sys
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Comment

ROOT = Path(__file__).resolve().parent.parent
BAKE = ROOT / "_bake"
SRC = ROOT / "src"
SITE = "https://premiermobiledetailing.com.au"
CDN_RE = re.compile(r"https://vibe\.filesafe\.space/\d+/(?:attachments|assets)/")
GOOGLE_LOGO = "https://upload.wikimedia.org/wikipedia/commons/2/2f/Google_2015_logo.svg"
GOOGLE_G = "https://upload.wikimedia.org/wikipedia/commons/c/c1/Google_%22G%22_logo.svg"
CTA_RE = re.compile(r"^(book now|book your detail( now)?|start your quote|get a quote|get my quote|request (a )?quote|get started|enquire( now)?|get in touch)$", re.I)
MAP_CLASS = "h-[350px]"
SUBURB_BASE = "cranbourne"  # its name is not a substring of any other suburb's
PAGE_NAV_SOURCE = "ceramic-coating-cost-melbourne"
BIG_FOOTER_SOURCE = "ceramic-coating-cost-melbourne"
COMPACT_FOOTER_SOURCE = "about"
DRAWER_SOURCE = "about"

warnings = []


def warn(msg):
    warnings.append(msg)
    print("  ! " + msg)


# ---------------------------------------------------------------- helpers
def route_of(bake_name):
    return "/" if bake_name == "index" else "/" + bake_name.replace("__", "/")


def load(bake_name):
    html = (BAKE / f"{bake_name}.html").read_text(encoding="utf-8")
    html = CDN_RE.sub("/assets/images/", html)
    html = html.replace(GOOGLE_LOGO, "/assets/images/google-logo.svg").replace(GOOGLE_G, "/assets/images/google-g-logo.svg")
    return BeautifulSoup(html, "html.parser")


def absolutize(u):
    if isinstance(u, str) and u.startswith("/"):
        return SITE + u
    return u


def abs_urls(obj):
    """Absolutise url/image-ish values inside JSON-LD, recursively."""
    if isinstance(obj, dict):
        return {k: (absolutize(v) if k in ("url", "image", "logo", "@id", "target", "sameAs", "contentUrl", "thumbnailUrl") else abs_urls(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [abs_urls(x) for x in obj]
    return obj


def parse_style(s):
    out = []
    for part in s.split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            out.append((k.strip(), v.strip()))
    return out


def render_style(decls):
    return "; ".join(f"{k}: {v}" for k, v in decls) + (";" if decls else "")


def norm_text(el):
    return re.sub(r"\s+", " ", el.get_text(" ")).strip()


# --------------------------------------------------------- content transforms
def clean_content(root, route):
    """In-place cleanup of a body subtree (everything under #root or body)."""
    # toast containers React leaves behind
    for el in root.select('div[role="region"][aria-label^="Notifications"], section[aria-label^="Notifications"]'):
        el.decompose()
    for c in root.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for el in root.find_all(True):
        attrs = el.attrs
        # framer-motion whileInView states -> data-reveal (runtime reveal re-adds motion)
        if "style" in attrs:
            decls = parse_style(attrs["style"])
            has_fm = any(k == "transform" and v in ("translateY(30px)", "none") for k, v in decls) and any(k == "opacity" and v in ("0", "1") for k, v in decls)
            if has_fm:
                decls = [(k, v) for k, v in decls if k not in ("opacity", "transform")]
                if not any(k == "display" and v == "none" for k, v in decls):
                    attrs["data-reveal"] = ""
            decls = [(k, v) for k, v in decls if k != "transition-delay"]
            if decls:
                attrs["style"] = render_style(decls)
            else:
                del attrs["style"]
        # enhance.js reveal classes -> runtime re-applies them
        if "class" in attrs:
            cls = [c for c in attrs["class"] if c not in ("rz", "rz-in")]
            if cls:
                attrs["class"] = cls
            else:
                del attrs["class"]
        for a in ("data-pmdq", "data-rh"):
            attrs.pop(a, None)
    # quote / booking CTAs -> real links (enhance.js used to hijack these clicks)
    if route != "/booking":
        for el in list(root.find_all(["button", "a"])):
            if el.find_parent("form"):
                continue
            href = el.get("href", "")
            if href.startswith(("tel:", "mailto:")):
                continue
            if not CTA_RE.match(norm_text(el)):
                continue
            if el.name == "button":
                el.name = "a"
                for a in ("type", "aria-haspopup", "aria-expanded", "aria-controls", "data-state"):
                    el.attrs.pop(a, None)
            el.attrs["href"] = "/booking"
    # Leaflet map container -> empty placeholder mounted at runtime
    has_map = False
    for d in root.find_all("div", class_=lambda c: c and MAP_CLASS in c):
        for c in list(d.find_all(recursive=False)):
            if "absolute" not in (c.get("class") or []):
                c.decompose()
        d.attrs["data-pmd-map"] = ""
        has_map = True
    return has_map


# ------------------------------------------------------------- head extraction
def extract_head(soup, route, has_static_hero):
    head = soup.head
    meta = {"title": soup.title.string.strip() if soup.title and soup.title.string else "", "og": {}, "twitter": {}, "jsonld": [], "preloads": [], "styles": []}
    for m in head.find_all("meta"):
        n, p, c = m.get("name"), m.get("property"), m.get("content", "")
        if n == "description":
            meta["description"] = c
        elif n == "robots":
            meta["robots"] = c
        elif n and n.startswith("twitter:"):
            meta["twitter"][n[8:]] = absolutize(c)
        elif p and p.startswith("og:"):
            meta["og"][p[3:]] = absolutize(c)
        elif n in ("viewport", "author") or m.get("charset"):
            pass
        else:
            warn(f"{route}: unhandled meta {m}")
    can = head.find("link", rel="canonical")
    meta["canonical"] = absolutize(can["href"]) if can else SITE + ("" if route == "/" else route)
    if route == "/":
        meta["canonical"] = SITE + "/"
    for s in head.find_all("script", type="application/ld+json"):
        try:
            meta["jsonld"].append(abs_urls(json.loads(s.string)))
        except Exception as e:
            warn(f"{route}: bad JSON-LD ({e})")
    for l in head.find_all("link", rel="preload"):
        if route != "/" and not has_static_hero:
            continue  # the hero-image preloads belonged to the homepage shell only
        meta["preloads"].append({k: l[k] for k in ("as", "href", "media", "fetchpriority") if l.get(k)})
    for l in head.find_all("link", rel="stylesheet"):
        if "index-BzKcK88v" not in l.get("href", "") and "Map-" not in l.get("href", ""):
            warn(f"{route}: extra stylesheet {l.get('href')}")
    for st in head.find_all("style"):
        css = st.string or ""
        if "data-sonner-toaster" in css:
            continue
        if css.strip() == "body{background:#080B16;margin:0;color:#fff}":
            continue
        if "#static-hero" in css and not has_static_hero:
            continue
        if css.strip():
            meta["styles"].append(css.strip("\n"))
    # dedupe styles
    seen, uniq = set(), []
    for css in meta["styles"]:
        if css not in seen:
            seen.add(css)
            uniq.append(css)
    meta["styles"] = uniq
    return meta


# ------------------------------------------------------------- body splitting
def split_body(soup, route):
    body = soup.body
    out = {"before": "", "after": "", "scripts": [], "static_hero": False}
    root = body.find(id="root")
    static_hero = body.find(id="static-hero")
    if static_hero and route == "/":
        # the old React shell shipped the homepage hero picture on EVERY page; only the
        # homepage shows it (its wrapper has no background), elsewhere it was hidden weight
        out["static_hero"] = True
        out["before"] = str(static_hero)
    for sc in body.find_all("script", recursive=False):
        if sc.get("src"):
            continue  # enhance.js -> replaced by site.js
        out["scripts"].append(str(sc))
    star = body.find("svg", id="pmd-star-grad-svg")
    if star:
        out["after"] = str(star)
    # anything else at body level we did not expect? Elements the page's own inline
    # script creates (e.g. the TDS modal) are runtime residue and must not be baked.
    script_text = "".join(out["scripts"])
    for c in list(body.find_all(recursive=False)):
        if c.name in ("noscript", "script") or c is root or c is static_hero or c is star or (c.get("id") == "pmd-mdrawer"):
            continue
        if root is None:
            continue  # standalone page: whole body is content
        if c.get("id") and c.get("id") in script_text:
            c.decompose()
            continue
        if c.name == "style":
            out["scripts"].insert(0, str(c))
            c.decompose()
            continue
        warn(f"{route}: unexpected body child <{c.name} id={c.get('id')} class={c.get('class')}>")
    if root is None:
        # standalone hand-written page (privacy-policy, thank-you): its own nav/footer stay inline
        kids = [c for c in body.find_all(recursive=False) if c.name not in ("noscript", "script") and c.get("id") != "pmd-mdrawer"]
        has_map = clean_content(body, route)
        out.update(root=False, wrapper=None, header="none", footer="none", content="".join(str(k) for k in kids), map=has_map, footer_html=None)
        return out
    has_map = clean_content(root, route)
    kids = [c for c in root.find_all(recursive=False) if not isinstance(c, NavigableString)]
    wrapper = [c for c in kids if c.name == "div" and "min-h-screen" in " ".join(c.get("class") or [])]
    host = wrapper[0] if wrapper else root
    out["wrapper"] = " ".join(wrapper[0]["class"]) if wrapper else None
    hk = [c for c in host.find_all(recursive=False) if not isinstance(c, NavigableString)]
    nav = hk[0] if hk and hk[0].name == "nav" else None
    footer = hk[-1] if hk and hk[-1].name == "footer" else None
    if nav is None:
        warn(f"{route}: no leading <nav>")
    middle = [c for c in hk if c is not nav and c is not footer]
    out.update(root=True, header="home" if route == "/" else "page", nav_html=str(nav) if nav else None, footer_html=str(footer) if footer else None,
               content="".join(str(c) for c in middle), map=has_map)
    return out


# ------------------------------------------------------------- footer model
def footer_props(footer):
    """Pull the CTA block + blurb out of a 'big' footer. Returns None if the shape is off."""
    block = footer.select_one(".max-w-4xl.mx-auto.text-center")
    if not block:
        return None
    kicker = block.select_one("p.text-primary")
    h2 = block.find("h2")
    sub = block.select_one("p.text-xl")
    links = block.find_all("a")
    blurb = footer.select_one("p.text-muted-foreground.max-w-sm")
    if not (kicker and h2 and sub and links and blurb):
        return None
    span = h2.find("span")
    line1 = "".join(str(x) for x in h2.contents if isinstance(x, NavigableString)).strip()
    line2 = span.get_text().strip() if span else ""
    props = {"kicker": kicker.get_text().strip(), "line1": line1, "line2": line2, "sub": norm_text(sub),
             "primary": {"text": norm_text(links[0]), "href": links[0].get("href", "")},
             "secondary": {"text": norm_text(links[1]), "href": links[1].get("href", "")} if len(links) > 1 else None,
             "blurb": norm_text(blurb)}
    return props


def tokenise_footer(footer):
    """Replace the CTA strings in a big footer with tokens; returns template html."""
    f = copy.copy(footer)
    block = f.select_one(".max-w-4xl.mx-auto.text-center")
    block.select_one("p.text-primary").string = "@@KICKER@@"
    h2 = block.find("h2")
    span = h2.find("span")
    for x in list(h2.contents):
        if isinstance(x, NavigableString):
            x.extract()
    h2.insert(0, NavigableString("@@LINE1@@"))
    span.string = "@@LINE2@@"
    block.select_one("p.text-xl").string = "@@SUB@@"
    links = block.find_all("a")
    links[0].string = "@@PTEXT@@"; links[0]["href"] = "@@PHREF@@"
    links[1].string = "@@STEXT@@"; links[1]["href"] = "@@SHREF@@"
    f.select_one("p.text-muted-foreground.max-w-sm").string = "@@BLURB@@"
    return str(f)


def fill_footer(tpl, p):
    esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    sec = p["secondary"] or {"text": "", "href": ""}
    return (tpl.replace("@@KICKER@@", esc(p["kicker"])).replace("@@LINE1@@", esc(p["line1"])).replace("@@LINE2@@", esc(p["line2"]))
            .replace("@@SUB@@", esc(p["sub"])).replace("@@PTEXT@@", esc(p["primary"]["text"])).replace("@@PHREF@@", p["primary"]["href"])
            .replace("@@STEXT@@", esc(sec["text"])).replace("@@SHREF@@", sec["href"]).replace("@@BLURB@@", esc(p["blurb"])))


def same_footer(a_html, b_html):
    A = BeautifulSoup(a_html, "html.parser"); B = BeautifulSoup(b_html, "html.parser")
    ta, tb = norm_text(A), norm_text(B)
    la = [x.get("href") for x in A.find_all("a")]; lb = [x.get("href") for x in B.find_all("a")]
    return ta == tb and la == lb


# --------------------------------------------------------------- astro emit
def js_str(s):
    return json.dumps(s, ensure_ascii=False)


def astro_page(route, meta, parts, footer_variant, footer_props, content_import):
    up = "../" * (1 + (route.strip("/").count("/") if route != "/" else 0))
    props = {
        "title": meta["title"], "description": meta.get("description", ""), "canonical": meta["canonical"],
        "robots": meta.get("robots"), "og": meta["og"], "twitter": meta["twitter"], "jsonld": meta["jsonld"],
        "preloads": meta["preloads"], "styles": meta["styles"], "root": parts["root"], "wrapper": parts["wrapper"],
        "header": parts["header"], "footer": footer_variant, "footerProps": footer_props, "map": parts["map"],
    }
    lines = ["---", f"import Base from '{up}layouts/Base.astro';", f"import html from '{up}content-html/{content_import}?raw';"]
    if parts["before"]:
        lines.append(f"const before = {js_str(parts['before'])};")
    if parts["after"]:
        lines.append(f"const after = {js_str(parts['after'])};")
    lines.append(f"const page = {json.dumps(props, ensure_ascii=False, indent=2)};")
    lines.append("---")
    lines.append("<Base {...page}>")
    if parts["before"]:
        lines.append("  <Fragment slot=\"before\" set:html={before} />")
    lines.append("  <Fragment set:html={html} />")
    if parts["after"]:
        lines.append("  <Fragment slot=\"after\" set:html={after} />")
    lines.append("</Base>")
    return "\n".join(lines) + "\n"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def assert_no_braces(html, what):
    html = re.sub(r"\{(p|s)\.[a-z0-9.]+\}|\{name\}", "", html)
    m = re.search(r"[{}]", html)
    if m:
        raise SystemExit(f"{what}: contains braces; Astro would parse them as expressions: …{html[max(0, m.start()-120):m.start()+60]}…")


# ================================================================== main
def main():
    if (SRC / "content-html").exists() and "--force" not in sys.argv:
        raise SystemExit("src/content-html already exists: this was the one-time migration from the old mirror. "
                         "Re-running would overwrite hand edits made since (e.g. the booking relay). Pass --force if you really mean it.")
    bakes = sorted(p.stem for p in BAKE.glob("*.html"))
    pages = {}
    for name in bakes:
        route = route_of(name)
        soup = load(name)
        parts = split_body(soup, route)
        meta = extract_head(soup, route, parts["static_hero"])
        pages[route] = {"name": name, "meta": meta, "parts": parts}
    print(f"parsed {len(pages)} bakes")

    # ---- shared components from reference pages
    page_nav = BeautifulSoup(pages["/" + PAGE_NAV_SOURCE]["parts"]["nav_html"], "html.parser").nav
    page_nav.attrs.pop("style", None)
    page_nav["class"] = [("bg-transparent" if c == "bg-background/90" else c) for c in page_nav["class"]]
    home_nav = pages["/"]["parts"]["nav_html"]
    # every page nav must carry the same links as the reference, or we'd silently drop one
    ref_links = [(a.get("href"), norm_text(a)) for a in page_nav.find_all("a")]
    for route, pg in pages.items():
        if route == "/" or not pg["parts"].get("nav_html"):
            continue
        links = [(a.get("href"), norm_text(a)) for a in BeautifulSoup(pg["parts"]["nav_html"], "html.parser").find_all("a")]
        if links != ref_links:
            warn(f"{route}: nav links differ from reference: {links}")
    drawer = load(DRAWER_SOURCE).find(id="pmd-mdrawer")
    drawer_html = str(drawer)

    compact_footer = pages["/" + COMPACT_FOOTER_SOURCE]["parts"]["footer_html"]
    home_footer = pages["/"]["parts"]["footer_html"]
    big_src = BeautifulSoup(pages["/" + BIG_FOOTER_SOURCE]["parts"]["footer_html"], "html.parser").footer
    big_props_ref = footer_props(big_src)
    big_tpl = tokenise_footer(big_src)
    assert same_footer(fill_footer(big_tpl, big_props_ref), str(big_src)), "big footer template does not round-trip"

    # ---- suburbs: template from the base suburb + per-suburb data
    sub_routes = sorted(r for r in pages if r.startswith("/mobile-detailing/"))
    base = pages["/mobile-detailing/" + SUBURB_BASE]
    base_name = "Cranbourne"
    suburb_footer_html = base["parts"]["footer_html"]  # identical on all 54 pages (it names Officer, the home base)
    bsoup = BeautifulSoup(base["parts"]["content"], "html.parser")
    intro = bsoup.select_one("p.text-xl.text-gray-200"); focus = bsoup.select_one("p.text-white.text-base")
    areas = bsoup.select_one("section#areas")
    area_links = areas.find_all("a", href=re.compile(r"^/mobile-detailing/"))
    link_tpl = copy.copy(area_links[0]); link_tpl["href"] = "@@HREF@@"; link_tpl.string = "@@TEXT@@"
    link_box = area_links[0].parent
    intro.string = "@@INTRO@@"; focus.string = "@@FOCUS@@"
    link_box.clear(); link_box.append(NavigableString("@@NEARBY@@"))
    sub_tpl = str(bsoup).replace(base_name, "@@NAME@@").replace(SUBURB_BASE, "@@SLUG@@")
    link_tpl_html = str(link_tpl)

    suburbs = []
    for r in sub_routes:
        pg = pages[r]; slug = r.rsplit("/", 1)[1]
        s = BeautifulSoup(pg["parts"]["content"], "html.parser")
        kick = s.find(string=re.compile(r"^Mobile Detailing in .+"))
        name = kick.strip()[len("Mobile Detailing in "):] if kick else " ".join(w.capitalize() for w in slug.split("-"))
        i = s.select_one("p.text-xl.text-gray-200"); f = s.select_one("p.text-white.text-base")
        nearby = [(a["href"], norm_text(a)) for a in s.select_one("section#areas").find_all("a", href=re.compile(r"^/mobile-detailing/"))]
        rec = {"slug": slug, "name": name, "intro": i.decode_contents().strip(), "focus": f.decode_contents().strip(), "nearby": nearby,
               "title": pg["meta"]["title"], "description": pg["meta"].get("description", ""), "og": pg["meta"]["og"], "twitter": pg["meta"]["twitter"], "jsonld": pg["meta"]["jsonld"]}
        # rebuild and verify against the bake
        nearby_html = "".join(link_tpl_html.replace("@@HREF@@", h).replace("@@TEXT@@", t) for h, t in nearby)
        rebuilt = (sub_tpl.replace("@@INTRO@@", rec["intro"]).replace("@@FOCUS@@", rec["focus"]).replace("@@NEARBY@@", nearby_html)
                   .replace("@@NAME@@", name).replace("@@SLUG@@", slug))
        A = BeautifulSoup(rebuilt, "html.parser"); B = s
        if norm_text(A) != norm_text(B) or [x.get("href") for x in A.find_all("a")] != [x.get("href") for x in B.find_all("a")]:
            ta, tb = norm_text(A), norm_text(B)
            k = next((j for j in range(min(len(ta), len(tb))) if ta[j] != tb[j]), min(len(ta), len(tb)))
            warn(f"suburb {slug} does not rebuild from template; first text diff at {k}: TEMPLATE …{ta[max(0,k-60):k+80]}… BAKE …{tb[max(0,k-60):k+80]}…")
        fsoup = BeautifulSoup(pg["parts"]["footer_html"], "html.parser")
        fexp = BeautifulSoup(suburb_footer_html, "html.parser")
        if norm_text(fsoup) != norm_text(fexp):
            warn(f"suburb {slug}: footer differs from suburb footer template")
        suburbs.append(rec)
    print(f"suburbs: {len(suburbs)} records")

    # ---- write components
    def as_astro_component(html_variants, props_line):
        """html_variants: list of (condition, html). Emits an .astro with {cond && <Fragment>…</Fragment>}."""
        out = ["---", props_line, "---"]
        for cond, html in html_variants:
            assert_no_braces(html, cond)
            out.append("{" + cond + " && (<Fragment>")
            out.append(html)
            out.append("</Fragment>)}")
        return "\n".join(out) + "\n"

    home_nav_s = str(BeautifulSoup(home_nav, "html.parser"))
    write(SRC / "components/Header.astro", as_astro_component(
        [("variant === 'home'", home_nav_s), ("variant !== 'home'", str(page_nav))],
        "const { variant = 'page' } = Astro.props;"))

    big_astro = (big_tpl.replace("@@KICKER@@", "{p.kicker}").replace("@@LINE1@@", "{p.line1}").replace("@@LINE2@@", "{p.line2}")
                 .replace("@@SUB@@", "{p.sub}").replace("@@PTEXT@@", "{p.primary.text}").replace('href="@@PHREF@@"', "href={p.primary.href}")
                 .replace("@@STEXT@@", "{s.text}").replace('href="@@SHREF@@"', "href={s.href}").replace("@@BLURB@@", "{p.blurb}"))
    suburb_astro = suburb_footer_html
    write(SRC / "components/Footer.astro", as_astro_component(
        [("variant === 'home'", home_footer), ("variant === 'suburb'", suburb_astro), ("variant === 'compact'", compact_footer), ("variant === 'big'", big_astro)],
        "const { variant = 'compact', props = {} } = Astro.props;\nconst p = { ...%s, ...props };\nconst s = p.secondary || { text: '', href: '' };" % json.dumps(big_props_ref, ensure_ascii=False)))
    write(SRC / "components/MobileDrawer.astro", "---\n---\n" + drawer_html + "\n")

    # ---- write pages
    content_dir = SRC / "content-html"
    for route, pg in pages.items():
        if route.startswith("/mobile-detailing/"):
            continue
        parts, meta = pg["parts"], pg["meta"]
        fv, fp = "none", None
        fh = parts.get("footer_html")
        content = parts["content"]
        if fh:
            if fh == home_footer:
                fv = "home"
            elif fh == compact_footer:
                fv = "compact"
            else:
                fs = BeautifulSoup(fh, "html.parser").footer
                p = footer_props(fs)
                if p and same_footer(fill_footer(big_tpl, p), fh):
                    fv, fp = "big", p
                else:
                    fv = "none"
                    content += "\n<!-- one-off footer kept inline (does not match a shared variant) -->\n" + fh
                    print(f"  {route}: footer kept inline")
        content += "".join("\n" + s for s in parts["scripts"])
        fname = "index" if route == "/" else route.strip("/")
        write(content_dir / f"{fname}.html", content)
        write(SRC / "pages" / f"{fname}.astro", astro_page(route, meta, parts, fv, fp, f"{fname}.html"))

    # ---- suburb template + data + dynamic page
    write(content_dir / "mobile-detailing/_template.html", sub_tpl)
    write(content_dir / "mobile-detailing/_nearby-link.html", link_tpl_html)
    write(SRC / "data/suburbs.json", json.dumps(suburbs, ensure_ascii=False, indent=2))
    bp = base["parts"]
    write(SRC / "pages/mobile-detailing/[suburb].astro", f"""---
import Base from '../../layouts/Base.astro';
import template from '../../content-html/mobile-detailing/_template.html?raw';
import linkTpl from '../../content-html/mobile-detailing/_nearby-link.html?raw';
import suburbs from '../../data/suburbs.json';

export function getStaticPaths() {{
  return suburbs.map((s) => ({{ params: {{ suburb: s.slug }}, props: {{ s }} }}));
}}
const {{ s }} = Astro.props;
const nearby = s.nearby.map(([href, text]) => linkTpl.replace('@@HREF@@', href).replace('@@TEXT@@', text)).join('');
const html = template
  .replaceAll('@@INTRO@@', s.intro).replaceAll('@@FOCUS@@', s.focus).replaceAll('@@NEARBY@@', nearby)
  .replaceAll('@@NAME@@', s.name).replaceAll('@@SLUG@@', s.slug);
const page = {{
  title: s.title, description: s.description, canonical: `https://premiermobiledetailing.com.au/mobile-detailing/${{s.slug}}`,
  og: s.og, twitter: s.twitter, jsonld: s.jsonld,
  preloads: {json.dumps(base['meta']['preloads'])}, styles: {json.dumps(base['meta']['styles'], ensure_ascii=False)},
  root: true, wrapper: {json.dumps(bp['wrapper'])}, header: 'page', footer: 'suburb', map: {json.dumps(bp['map'])},
}};
const before = {js_str(bp['before'])};
---
<Base {{...page}}>
  <Fragment slot="before" set:html={{before}} />
  <Fragment set:html={{html}} />
</Base>
""")
    print(f"warnings: {len(warnings)}")
    return 1 if warnings else 0


if __name__ == "__main__":
    sys.exit(main())
