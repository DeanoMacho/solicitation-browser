"""Pull DIBBS RFQs for one issue date and save them to data/rfqs.json.

Usage: .venv/bin/python scrape.py [MM-DD-YYYY] [max_pages]
"""
import json, os, re, sys, time, warnings
from datetime import date

warnings.filterwarnings("ignore")
import requests
from bs4 import BeautifulSoup

BASE = "https://www.dibbs.bsm.dla.mil"
HEADERS = {
    # DIBBS's firewall rejects requests that don't look like a browser.
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
GRID = "ctl00_cph1_grdRfqSearch"


def hidden_fields(soup):
    form = soup.find("form")
    return {i["name"]: i.get("value", "") for i in form.find_all("input")
            if i.get("name") and i.get("type") == "hidden"}


def session_with_consent(goto):
    """DIBBS shows a DoD consent banner first; accept it the way a browser does."""
    s = requests.Session()
    s.headers.update(HEADERS)
    url = f"{BASE}/dodwarning.aspx?goto={goto}"
    soup = BeautifulSoup(s.get(url, timeout=30).text, "html.parser")
    data = hidden_fields(soup)
    data["butAgree"] = "OK"
    s.post(url, data=data, timeout=30)
    return s


def text(el):
    return el.get_text(" ", strip=True) if el else ""


def parse_rows(soup):
    grid = soup.find("table", id=GRID)
    out = []
    if not grid:
        return out
    for tr in grid.find_all("tr"):
        nsn_span = tr.find("span", id=re.compile(r"_lblNsn$"))
        if not nsn_span:
            continue
        get = lambda suffix: tr.find("span", id=re.compile(suffix + "$"))
        nsn_a = nsn_span.find("a")
        nsn = text(nsn_a) if nsn_a else text(nsn_span)
        sol_span = get("_lblSolicitation")
        sol_a = sol_span.find("a") if sol_span else None
        pkg_a = sol_span.find("a", title="Package View") if sol_span else None
        # DIBBS shows several icons here (set-aside type, fast award, ...); read their alt text.
        icons = [i.get("alt", "") for i in sol_span.find_all("img")] if sol_span else []
        set_aside = next((a for a in icons if re.search(r"set.?aside|unrestricted", a, re.I)), "")
        fast_award = any("fast award" in a.lower() for a in icons)
        status_span = get("_lblStatus")
        pr_span = get("_lblPR") or get("_lblPurchaseRequest")
        tds = tr.find_all("td", recursive=False)
        pr_text = text(tds[6]) if len(tds) > 6 else text(pr_span)
        qty = re.search(r"QTY:\s*([\d,]+)", pr_text)
        tech = get("_lblTechnicalDocuments")
        tech_a = tech.find("a") if tech else None
        digits = re.sub(r"\D", "", nsn)
        out.append({
            "nsn": nsn,
            "fsc": digits[:4] if len(digits) >= 13 else "",
            "milspec": "Mil-Spec" in text(nsn_span),
            "nomenclature": text(get("_lblNomenclature")),
            "solicitation": text(sol_a),
            "pdf_url": sol_a["href"] if sol_a else "",
            "dibbs_url": pkg_a["href"] if pkg_a else "",
            "nsn_url": nsn_a["href"] if nsn_a else "",
            "tech_docs_url": tech_a["href"] if tech_a else "",
            "set_aside": set_aside,
            "fast_award": fast_award,
            "status": text(status_span.find("span")) if status_span else "",
            "purchase_request": pr_text.split("QTY")[0].strip(),
            "qty": int(qty.group(1).replace(",", "")) if qty else None,
            "issued": text(tds[7]) if len(tds) > 7 else "",
            "return_by": text(tds[8]) if len(tds) > 8 else "",
        })
    return out


def scrape(day, max_pages=999):
    path = f"/RFQ/RfqRecs.aspx?category=issue&TypeSrch=dt&Value={day}"
    s = session_with_consent(path)
    resp = s.get(BASE + path, timeout=60)
    rows, seen = [], set()
    page = 1
    while True:
        soup = BeautifulSoup(resp.text, "html.parser")
        new = [r for r in parse_rows(soup) if r["solicitation"] + r["nsn"] not in seen]
        if not new:
            break
        for r in new:
            seen.add(r["solicitation"] + r["nsn"])
        rows.extend(new)
        print(f"page {page}: {len(new)} rows (total {len(rows)})", flush=True)
        page += 1
        if page > max_pages:
            break
        # The grid pages by ASP.NET postback, not by URL.
        data = hidden_fields(soup)
        data["__EVENTTARGET"] = "ctl00$cph1$grdRfqSearch"
        data["__EVENTARGUMENT"] = f"Page${page}"
        resp = s.post(BASE + path, data=data, timeout=60)
        time.sleep(0.5)  # be polite to a government site
    return rows


def combine():
    """Merge every saved day into data/rfqs.json, the one file the app reads."""
    days, rows, seen = [], [], set()
    for name in sorted(os.listdir("data/days"), reverse=True):
        with open(f"data/days/{name}") as f:
            d = json.load(f)
        days.append(d["issue_date"])
        for r in d["rows"]:
            key = r["solicitation"] + r["nsn"]
            if key not in seen:
                seen.add(key)
                rows.append(r)
    with open("data/rfqs.json", "w") as f:
        json.dump({"issue_dates": days, "pulled_at": time.strftime("%Y-%m-%d %H:%M"), "rows": rows}, f)
    print(f"data/rfqs.json: {len(rows)} RFQs across {len(days)} issue dates")


if __name__ == "__main__":
    # Usage: scrape.py [MM-DD-YYYY ...]   (no dates = today)
    day_args = sys.argv[1:] or [date.today().strftime("%m-%d-%Y")]
    os.makedirs("data/days", exist_ok=True)
    for day in day_args:
        rows = scrape(day)
        y = day.split("-")
        with open(f"data/days/{y[2]}-{y[0]}-{y[1]}.json", "w") as f:
            json.dump({"issue_date": day, "pulled_at": time.strftime("%Y-%m-%d %H:%M"), "rows": rows}, f)
        print(f"saved {len(rows)} RFQs for {day}")
    combine()
