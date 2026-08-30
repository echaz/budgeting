"""
Amazon order crawler — captures your own order history for the budgeting app.

This script is DELIBERATELY standalone and decoupled from the Django app. It only
crawls and writes a raw JSON file. It never touches the database. A separate Django
management command reads that JSON and creates the rows (with the tax/shipping
allocation described below). Keep that separation: the scraper stays "dumb" and
faithful to what Amazon shows; all business logic lives in the importer where it is
testable.

────────────────────────────────────────────────────────────────────────────────
WHY A CRAWLER (and the honest caveat)
────────────────────────────────────────────────────────────────────────────────
Amazon's official "Request My Data" export (Account → Privacy → Request Your
Information → Your Orders) gives clean per-item CSVs with zero bot-fighting and is
strictly less work than this. Prefer it for a one-off backfill. This crawler exists
for repeatable, on-demand syncs. It only ever reads the account owner's own data.

────────────────────────────────────────────────────────────────────────────────
ANTI-BOT APPROACH (what actually works)
────────────────────────────────────────────────────────────────────────────────
- Persistent context (launch_persistent_context with a real user-data dir) so the
  login session sticks between runs. Do NOT use a throwaway headless browser.
- Manual login, ONCE. First run opens headed; you log in by hand (password + 2FA);
  the script waits until it sees the orders page, then the session persists.
- Headed / human-paced. Amazon fingerprints fast headless loops → CAPTCHA walls.
- Loop years, then loop pages within each year:
      https://www.amazon.com/gp/css/order-history?timeFilter=year-YYYY
  Selectors WILL rot when Amazon changes the DOM; keep them isolated (SELECTORS
  dict below) so fixes are one place.

────────────────────────────────────────────────────────────────────────────────
WHAT TO CAPTURE (raw, per order)
────────────────────────────────────────────────────────────────────────────────
Per ORDER:
  - order_number   Amazon's order ID. Natural dedupe key (unique per account) so
                   re-running the crawler / importer is idempotent.
  - date           Order date.
  - order_total    Grand total actually charged.
  - tax            Order tax total.        (usually small)
  - shipping       Order shipping total.   (usually 0 — account has Prime)
  - card_last4     If shown ("...ending in 1234"), helps auto-link to the card
                   charge later. Optional / best effort.
Per LINE ITEM (an order has many):
  - name           Product title  → Transaction.description
  - pre_tax_price  Item price BEFORE tax/shipping (the shelf price).
  - quantity       If shown.

The crawler captures pre-tax prices + the order's tax + the order's shipping. It
does NOT compute the blended amounts — the importer does (see ALLOCATION).

────────────────────────────────────────────────────────────────────────────────
ALLOCATION (done by the Django importer, NOT here — recorded so both sides agree)
────────────────────────────────────────────────────────────────────────────────
Goal: every dollar charged lands on a categorized line item, so Σ(items) ==
order_total with no reconciliation gap. Each item's stored amount is tax- AND
shipping-inclusive:

    amount_i = pre_tax_i
             + tax      × (pre_tax_i / Σ pre_tax)   # TAX: proportional to price
             + shipping / N                          # SHIPPING: split equally

  - TAX is prorated proportionally to item price (a bigger item eats more tax).
  - SHIPPING is split equally across the N line items (each pays shipping / N),
    regardless of price. Prime means this is usually 0.
  - Both allocators use the LARGEST-REMAINDER method for pennies: round each share
    down, then hand the leftover cents to the items with the biggest fractional
    remainders, so Σ(amount_i) == order_total EXACTLY.

────────────────────────────────────────────────────────────────────────────────
DOWNSTREAM DATA MODEL (what the importer writes — reference for field mapping)
────────────────────────────────────────────────────────────────────────────────
New model  Order:
  account (FK→Account, PROTECT, the Amazon account), order_number (unique per
  account), date, order_total, tax, shipping, created_at.

Transaction changes:
  + order            FK→Order (PROTECT), nullable. Non-Amazon rows leave it null
                     and behave exactly as today (no breaking change).
  + pre_tax_amount   nullable Decimal. Original shelf price kept alongside the
                     blended `amount` so the tax/shipping blend is transparent.
  + settles_against  self-FK→Transaction (PROTECT), nullable. DECIDED: item-level.
                     Each Amazon line item points at the CREDIT-CARD Transaction it
                     settled against. Because Amazon charges per shipment, item-level
                     (not order-level) linking handles split-shipment orders; the
                     importer auto-populates it (all items in a shipment → same card
                     charge). DEFERRED until card statements are imported (see #3).
  * category/domain  DECIDED: nullable. The credit-card Amazon charge is zeroed (see
                     reporting rule) and acts only as a link anchor, so it carries no
                     meaningful category/domain.

  `amount` on an Amazon line item is TAX- AND SHIPPING-INCLUSIVE (see ALLOCATION).

Reporting rule (avoids double-counting) — DECIDED via ZEROING: when card statements
are imported, the credit-card Amazon charge has its `amount` set to 0 once its line
items are linked. Graphs are spend-weighted (they sum `amount` by category/domain),
so a $0 anchor is invisible to them — no leaf/exclusion query needed; just sum all
amounts. The actually-charged figure is preserved on Order.order_total for
reconciliation. (Caveat to settle later: zeroing discards the per-line card amount;
if per-shipment reconciliation is ever wanted, keep the original in a separate field.)

Shape:
    Account(credit_card) ─< Transaction (Amazon charge, amount ZEROED, link anchor)
                                  ▲
                                  │ settles_against
    Account(amazon) ─< Order ─< Transaction (line item, blended, categorized) ─┘

────────────────────────────────────────────────────────────────────────────────
DECISIONS (settled with the account owner)
────────────────────────────────────────────────────────────────────────────────
1. Link placement: ITEM-LEVEL settles_against (Transaction → Transaction).
2. Summary card charge: category/domain NULLABLE. The card charge is ZEROED and used
   only as a link anchor, so it needs no classification; graphs are spend-weighted so
   a $0 row is invisible to them.
3. Card-statement import comes LATER. Until then there is nothing to link to, so
   settles_against + zeroing are DEFERRED (the field can exist unused; it's nullable).
None of these change what THIS crawler captures — it records raw data either way.

────────────────────────────────────────────────────────────────────────────────
OUTPUT
────────────────────────────────────────────────────────────────────────────────
Writes amazon_orders.json:
    [
      {
        "order_number": "111-2223334-5556667",
        "date": "2026-03-14",
        "order_total": "87.43",
        "tax": "5.44",
        "shipping": "0.00",
        "card_last4": "1234",
        "items": [
          {"name": "USB-C cable 2-pack", "pre_tax_price": "11.99", "quantity": 1},
          ...
        ]
      },
      ...
    ]
All money as strings to avoid float rounding before it reaches Decimal in Django.

────────────────────────────────────────────────────────────────────────────────
SETUP
────────────────────────────────────────────────────────────────────────────────
    pip install playwright
    playwright install chromium
(Not added to the app's requirements.txt — this is standalone tooling.)

Run:
    python scrapers/amazon_crawl.py --years 2025 2026
First run: log in by hand when the window opens.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# Anchor everything relative to this file so runs from any cwd behave the same.
BASE_DIR = Path(__file__).resolve().parent
USER_DATA_DIR = BASE_DIR / ".amazon_profile"   # persistent login session (gitignore this)
OUTPUT_FILE = BASE_DIR / "amazon_orders.json"

ORDERS_URL = "https://www.amazon.com/gp/css/order-history?timeFilter=year-{year}"

# All fragile DOM knowledge lives here so selector rot is a one-place fix.
# These are BEST-GUESS placeholders and MUST be verified against the live page
# (Amazon A/B-tests its order history layout). Do not trust them until confirmed.
SELECTORS = {
    "order_card": ".order-card, .js-order-card",
    "order_number": "[data-test-id='order-id'], .yohtmlc-order-id",
    "order_date": ".order-header .a-color-secondary .value",
    "order_total": ".order-header .value .a-color-base",
    "item_row": ".item-box, .yohtmlc-item",
    "item_name": ".item-box .a-link-normal, .yohtmlc-product-title",
    "next_page": ".a-pagination .a-last a",
    "logged_in_marker": "#nav-link-accountList",  # present only when signed in
}


def crawl(years: list[int]) -> list[dict]:
    """Crawl the given years and return a list of raw order dicts (see module docstring)."""
    from playwright.sync_api import sync_playwright

    orders: list[dict] = []
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            headless=False,  # headed: survives Amazon's bot checks + lets you log in by hand
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # Manual login, once. Session persists in USER_DATA_DIR for later runs.
        page.goto(ORDERS_URL.format(year=years[0]))
        print("If prompted, log in (password + 2FA) in the browser window, then return here.")
        page.wait_for_selector(SELECTORS["logged_in_marker"], timeout=0)  # wait indefinitely

        for year in years:
            page.goto(ORDERS_URL.format(year=year))
            while True:
                orders.extend(_extract_orders_on_page(page))
                nxt = page.query_selector(SELECTORS["next_page"])
                if not nxt:
                    break
                nxt.click()
                page.wait_for_load_state("networkidle")

        ctx.close()
    return orders


def _extract_orders_on_page(page) -> list[dict]:
    """Extract every order card on the current page.

    TODO: fill in against the real DOM. Per order, read order_number, date,
    order_total, tax, shipping, card_last4, and the item rows (name, pre_tax_price,
    quantity). tax/shipping usually require opening the order details or invoice —
    decide whether to expand each order or read the summary line.
    """
    raise NotImplementedError("Wire up SELECTORS against the live order-history DOM.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Crawl your Amazon order history to JSON.")
    ap.add_argument("--years", type=int, nargs="+", required=True, help="Years to crawl, e.g. 2025 2026")
    ap.add_argument("--out", type=Path, default=OUTPUT_FILE, help="Output JSON path")
    args = ap.parse_args()

    orders = crawl(args.years)
    args.out.write_text(json.dumps(orders, indent=2))
    print(f"Wrote {len(orders)} orders → {args.out}")


if __name__ == "__main__":
    main()
