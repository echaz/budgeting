from datetime import date

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render
from django.urls import reverse

from core.models import Transaction


def _month_bounds(year, month):
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


def _quarter_bounds(year, quarter):
    first_month = (quarter - 1) * 3 + 1
    start = date(year, first_month, 1)
    if quarter == 4:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, first_month + 3, 1)
    return start, end


def _subtract_months(anchor, months):
    total = anchor.year * 12 + (anchor.month - 1) - months
    return date(total // 12, total % 12 + 1, 1)


def _available_months(available):
    return [
        {"value": d.strftime("%Y-%m"), "label": d.strftime("%B %Y")}
        for d in available
    ]


def _available_quarters(available):
    seen = []
    for d in available:
        quarter = (d.month - 1) // 3 + 1
        key = (d.year, quarter)
        if key not in seen:
            seen.append(key)
    return [
        {"value": f"{year}-Q{quarter}", "label": f"Q{quarter} {year}"}
        for year, quarter in seen
    ]


def _available_years(available):
    seen = []
    for d in available:
        if d.year not in seen:
            seen.append(d.year)
    return [{"value": str(year), "label": str(year)} for year in seen]


def _period_range(period):
    if "-Q" in period:
        year, quarter = period.split("-Q")
        year, quarter = int(year), int(quarter)
        start, end = _quarter_bounds(year, quarter)
        return start, end, f"Q{quarter} {year}"
    if "-" in period:
        year, month = (int(p) for p in period.split("-"))
        start, end = _month_bounds(year, month)
        return start, end, date(year, month, 1).strftime("%B %Y")
    year = int(period)
    return date(year, 1, 1), date(year + 1, 1, 1), str(year)


def _category_totals(start, end):
    rows = (
        Transaction.objects.filter(
            amount__gt=0,
            category__isnull=False,
            category__exclude_from_reports=False,
            date__gte=start,
            date__lt=end,
        )
        .values("category__name")
        .annotate(total=Sum("amount"))
    )
    return {r["category__name"]: float(r["total"]) for r in rows}


@login_required
def home(request):
    return render(request, "home.html")


@login_required
def reports_index(request):
    reports = [
        {
            "name": "Category spending",
            "url": reverse("category_report"),
            "description": "Pie chart of spending by category, by month, quarter, or last 12 months.",
        },
        {
            "name": "Compare periods",
            "url": reverse("category_compare"),
            "description": "Side-by-side spending by category for any two months, quarters, or years.",
        },
    ]
    return render(request, "reports_index.html", {"reports": reports})


@login_required
def category_report(request):
    available = list(Transaction.objects.dates("date", "month", order="DESC"))
    option_sets = {
        "month": _available_months(available),
        "quarter": _available_quarters(available),
        "year": _available_years(available),
    }

    granularity = request.GET.get("granularity", "month")
    if granularity not in option_sets:
        granularity = "month"
    options = option_sets[granularity]

    period = request.GET.get("period", "")
    valid_values = {opt["value"] for opt in options}
    if period not in valid_values:
        period = options[0]["value"] if options else ""

    base = Transaction.objects.filter(
        amount__gt=0,
        category__isnull=False,
        category__exclude_from_reports=False,
    )

    if period:
        start, end, label = _period_range(period)
        qs = base.filter(date__gte=start, date__lt=end)
    else:
        qs = base.none()
        label = ""

    rows = (
        qs.values("category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    chart = [
        {"category": r["category__name"], "amount": float(r["total"])}
        for r in rows
    ]
    total = sum(item["amount"] for item in chart)

    transactions = {}
    tx_rows = qs.order_by("-date", "-created_at").values(
        "category__name", "date", "description", "amount", "account__nickname"
    )
    for tx in tx_rows:
        transactions.setdefault(tx["category__name"], []).append({
            "date": tx["date"].strftime("%Y-%m-%d"),
            "description": tx["description"],
            "amount": float(tx["amount"]),
            "account": tx["account__nickname"],
        })

    context = {
        "option_sets_json": option_sets,
        "period_options": options,
        "granularity": granularity,
        "selected_period": period,
        "period_label": label,
        "chart_json": chart,
        "transactions_json": transactions,
        "total": total,
    }
    return render(request, "category_report.html", context)


@login_required
def category_compare(request):
    available = list(Transaction.objects.dates("date", "month", order="DESC"))
    option_sets = {
        "month": _available_months(available),
        "quarter": _available_quarters(available),
        "year": _available_years(available),
    }
    months = option_sets["month"]
    default_a = months[0]["value"] if months else ""
    default_b = months[1]["value"] if len(months) > 1 else default_a

    def resolve(gran_param, period_param, default_period):
        granularity = request.GET.get(gran_param, "month")
        if granularity not in option_sets:
            granularity = "month"
        options = option_sets[granularity]
        valid_values = {opt["value"] for opt in options}
        period = request.GET.get(period_param, "")
        if period not in valid_values:
            if default_period in valid_values:
                period = default_period
            else:
                period = options[0]["value"] if options else ""
        return granularity, options, period

    gran_a, options_a, period_a = resolve("ga", "a", default_a)
    gran_b, options_b, period_b = resolve("gb", "b", default_b)

    def totals_for(period):
        if not period:
            return {}, ""
        start, end, label = _period_range(period)
        return _category_totals(start, end), label

    totals_a, label_a = totals_for(period_a)
    totals_b, label_b = totals_for(period_b)

    categories = sorted(set(totals_a) | set(totals_b))
    rows = []
    for name in categories:
        amt_a = totals_a.get(name, 0.0)
        amt_b = totals_b.get(name, 0.0)
        rows.append({
            "category": name,
            "amount_a": amt_a,
            "amount_b": amt_b,
            "delta": amt_b - amt_a,
        })
    rows.sort(key=lambda r: max(r["amount_a"], r["amount_b"]), reverse=True)

    context = {
        "option_sets_json": option_sets,
        "gran_a": gran_a,
        "gran_b": gran_b,
        "options_a": options_a,
        "options_b": options_b,
        "period_a": period_a,
        "period_b": period_b,
        "label_a": label_a,
        "label_b": label_b,
        "chart_json": rows,
        "total_a": sum(totals_a.values()),
        "total_b": sum(totals_b.values()),
    }
    return render(request, "category_compare.html", context)
