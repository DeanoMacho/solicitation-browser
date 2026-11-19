# Solicitation Browser

Pulls each day's DIBBS RFQs and shows a vendor the few that fit their shop, sorted by deadline.

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install requests beautifulsoup4
.venv/bin/python scrape.py 11-19-2026 11-18-2026   # one or more issue dates; no date = today
python3 -m http.server 8000               # open http://127.0.0.1:8000
```

## How vendors find opportunities

A vendor doesn't want to scroll 800 rows. They want the dozen that fit what they make, closing soonest.

1. **My shop profile** (left panel, saved in the browser):
   - **Categories (FSC):** the first 4 digits of every NSN are the Federal Supply Class (5330 = packings and gaskets, 4730 = hose and pipe fittings). Real vendors specialize by FSC, so this is the strongest filter that needs no setup beyond a few codes.
   - **Part numbers supplied before:** an exact NSN repeat buy is the hottest lead. The vendor already has the source, the price and the past performance.
   - **Keywords** on the item name, for vendors who think in words, not codes.
2. **"For my shop" view** ranks by fit (repeat part > category > keyword), then by days left. Every row says *why* it matched (badge), so the ranking is never a black box.
3. **Filters that list every option with live counts** (each count reflects every other active filter):
   - Item type (the noun before the comma in DLA naming: VALVE, GASKET, BATTERY), with search and an A–Z index
   - Category group and FSC class (hover an FSC and click **+ shop** to track it)
   - Return-by date with quick chips (≤ 3, 7, 14 days)
   - Set-aside (Small Business, SDVOSB, WOSB, HUBZone)
   - Highlights: Fast Award candidate, Mil-Spec, tech docs attached, same NSN on several solicitations, new in the latest issue
   - Buying office (from the solicitation prefix: DLA Aviation Richmond, Land and Maritime Columbus, Troop Support Medical, ...)
   - Quantity bands, solicitation type (T automated / Q manual), issue date, part origin (NSN country code), status
   - Search: every word must match across item, NSN, solicitation and purchase request; dashes optional; `-word` excludes
4. **Triage workflow:** ☆ shortlist and ✕ pass on every row (saved in the browser), Shortlist and Passed tabs, CSV export of the current view.
5. **Detail drawer** (click a row): every field, other open solicitations for the same NSN, and one-click "track this FSC" / "I've supplied this NSN".
6. **Every row links back to DIBBS:** the solicitation opens its DIBBS package view, the NSN opens its DIBBS history, plus the RFQ PDF and tech docs.

## How the data is pulled

- DIBBS sits behind a DoD consent banner and a firewall that rejects non-browser requests. The scraper sends browser headers, accepts the banner once per session the way a browser does, then reads the RFQ grid for one issue date.
- The grid pages by ASP.NET postback (50 rows a page), so the scraper replays the form state for each page, with a short pause between requests.
- Fields: solicitation, NSN, FSC, item name, Mil-Spec, set-aside, Fast Award, status, purchase request, quantity, issued, return-by, plus the DIBBS, PDF, NSN and tech-doc links.
- Output is a JSON snapshot (`data/rfqs.json`). The app reads the snapshot, so it stays fast and still works if DIBBS is slow or down.

## Tradeoffs (50-minute build)

- **No framework, no database.** One scraper, one HTML page. A day of RFQs is under 1 MB, so filtering in the browser is instant. SQLite or Postgres comes in when we keep history.
- **Rules, not AI, for matching.** FSC + NSN + keyword matching is explainable and correct by construction. A vendor trusts "FSC 5330" more than a mystery score.
- **Left out on purpose:** accounts, email alerts, multi-day history, award-price history. All of these are next steps, not MVP.

## Next steps

- Nightly job that pulls every new issue date and keeps history (SQLite then Postgres).
- Daily email or Slack digest: "6 new RFQs fit your shop, 2 are repeat parts."
- Past award prices per NSN (DIBBS award data) so the vendor sees what won last time.
- Build the shop profile automatically from the vendor's past quotes, or from a sentence ("we machine aluminum fittings") mapped to FSC codes with an LLM.
