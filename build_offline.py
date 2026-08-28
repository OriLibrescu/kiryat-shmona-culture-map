"""
מייצר קובץ HTML יחיד, עצמאי לחלוטין , כולל הגופנים העבריים מוטמעים בתוכו.
עובד בלחיצה כפולה, בלי אינטרנט, בלי התקנה, בכל דפדפן.
מייצר גם ZIP לשליחה במייל (חלק משרתי דואר חוסמים קובצי .html מצורפים).

הרצה:  python build_offline.py
"""
import io, os, re, base64, zipfile, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = "מפת התרבות - קריית שמונה"
OUT_HTML = os.path.join(HERE, NAME + ".html")
OUT_ZIP  = os.path.join(HERE, NAME + ".zip")
CACHE    = os.path.join(HERE, ".fontcache")

UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")}
GF = ("https://fonts.googleapis.com/css2?family=Assistant:wght@400;600;700"
      "&family=Frank+Ruhl+Libre:wght@700;900&display=swap")
WEIGHT_RANGE = {"Assistant": "300 800", "Frank Ruhl Libre": "400 900"}
SUBSETS = {"hebrew", "latin", "latin-ext"}


def fetch(url):
    """הורדה עם מטמון מקומי, כדי שהבנייה תעבוד גם אופליין בפעם הבאה."""
    os.makedirs(CACHE, exist_ok=True)
    key = os.path.join(CACHE, re.sub(r"[^A-Za-z0-9._-]", "_", url)[-100:])
    if os.path.exists(key):
        return open(key, "rb").read()
    raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
    open(key, "wb").write(raw)
    return raw


def font_css():
    css = fetch(GF).decode("utf-8")
    blocks = re.findall(r"/\*\s*([\w\-\[\]]+)\s*\*/\s*@font-face\s*\{(.*?)\}", css, re.S)
    rules, seen, total = [], set(), 0
    for subset, body in blocks:
        if subset not in SUBSETS:
            continue
        fam = re.search(r"font-family:\s*'([^']+)'", body).group(1)
        url = re.search(r"url\((https://[^)]+\.woff2)\)", body).group(1)
        rng = re.search(r"unicode-range:\s*([^;]+);", body).group(1).strip()
        if (fam, subset) in seen:
            continue
        seen.add((fam, subset))
        raw = fetch(url)
        total += len(raw)
        b64 = base64.b64encode(raw).decode()
        rules.append(
            "@font-face{font-family:'%s';font-style:normal;font-weight:%s;font-display:swap;"
            "src:url(data:font/woff2;base64,%s) format('woff2');unicode-range:%s}"
            % (fam, WEIGHT_RANGE[fam], b64, rng))
        print("  embedded %-18s %-10s %5d KB" % (fam, subset, len(raw) // 1024))
    print("  fonts total: %d KB raw" % (total // 1024))
    return "<style>\n" + "\n".join(rules) + "\n</style>"


def main():
    html = io.open(os.path.join(HERE, "index.html"), encoding="utf-8").read()
    geo  = io.open(os.path.join(HERE, "geo.js"),     encoding="utf-8").read()
    data = io.open(os.path.join(HERE, "data.js"),    encoding="utf-8").read()

    tag = '<script src="geo.js"></script>\n<script src="data.js"></script>'
    if tag not in html:
        raise SystemExit("script tags not found in index.html , build aborted")
    html = html.replace(tag, "<script>\n" + geo + "\n</script>\n<script>\n" + data + "\n</script>", 1)

    # החלפת קישורי Google Fonts בגופנים מוטמעים
    link = re.search(r'<link rel="preconnect".*?display=swap">', html, re.S)
    if not link:
        raise SystemExit("font <link> block not found , build aborted")
    html = html.replace(link.group(0), font_css(), 1)

    # הקשחה לקובץ העצמאי: החלפת ה-CSP של גרסת הרשת (המתירה גופנים מ-Google)
    # ב-CSP שחוסם כל פנייה לרשת, והסתרת כתובת הקובץ בעת יציאה לקישור חיצוני.
    web_csp = ('<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
               "style-src 'unsafe-inline' https://fonts.googleapis.com; "
               "font-src https://fonts.gstatic.com data:; script-src 'self' 'unsafe-inline'; "
               'img-src data:; base-uri \'none\'; form-action \'none\'">')
    if web_csp not in html:
        raise SystemExit("web CSP meta not found in index.html , build aborted")
    offline_csp = ('<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
                   "style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
                   'font-src data:; img-src data:; base-uri \'none\'; form-action \'none\'">\n'
                   '<meta name="referrer" content="no-referrer">')
    html = html.replace(web_csp, offline_csp, 1)
    if not html.lstrip().lower().startswith("<!doctype"):
        html = "<!doctype html>\n" + html

    io.open(OUT_HTML, "w", encoding="utf-8").write(html)
    size = len(html.encode("utf-8")) // 1024
    print("wrote %s  (%d KB)" % (OUT_HTML, size))

    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.write(OUT_HTML, NAME + ".html")
    print("wrote %s  (%d KB)" % (OUT_ZIP, os.path.getsize(OUT_ZIP) // 1024))


if __name__ == "__main__":
    main()
