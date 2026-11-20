import csv
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Sum
from django.db.models.functions import ExtractHour, TruncDate
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from expenses.models import Expense
from inventory.models import Ingredient, Purchase, PurchaseItem, StockMovement
from sales.models import Order, OrderItem

from .permissions import is_manager, manager_required

ZERO = Decimal("0")


def _bars(rows, key):
    peak = max((r[key] for r in rows), default=ZERO)
    for r in rows:
        r["pct"] = int(r[key] / peak * 100) if peak else 0
    return rows


@login_required
def dashboard(request):
    if not is_manager(request.user):
        return redirect("pos")

    today = timezone.localdate()
    paid = Order.objects.filter(status=Order.Status.PAID)
    agg = paid.filter(created_at__date=today).aggregate(
        revenue=Sum("total"), tax=Sum("tax"), cogs=Sum("cogs"), n=Count("id")
    )
    revenue, tax, cogs, n = (agg["revenue"] or ZERO), (agg["tax"] or ZERO), (agg["cogs"] or ZERO), agg["n"]
    profit = revenue - tax - cogs

    start = today - timedelta(days=6)
    rows = (
        paid.filter(created_at__date__gte=start)
        .annotate(d=TruncDate("created_at")).values("d").order_by("d")
        .annotate(amount=Sum("total"), n=Count("id"))
    )
    by_day = {r["d"]: r for r in rows}
    week = []
    for i in range(7):
        d = start + timedelta(days=i)
        r = by_day.get(d)
        week.append({"label": d.strftime("%a"), "total": r["amount"] if r else ZERO, "n": r["n"] if r else 0, "today": d == today})
    _bars(week, "total")

    top = (
        OrderItem.objects.filter(order__status=Order.Status.PAID, order__created_at__date=today)
        .values("name").annotate(q=Sum("quantity"), rev=Sum("line_total")).order_by("-q")[:6]
    )
    low = Ingredient.objects.filter(
        is_active=True, reorder_level__gt=0, stock__lte=F("reorder_level")
    ).order_by("name")
    active = Ingredient.objects.filter(is_active=True)

    month_start = today.replace(day=1)
    m = paid.filter(created_at__date__gte=month_start).aggregate(
        revenue=Sum("total"), tax=Sum("tax"), cogs=Sum("cogs"))
    month_gross = (m["revenue"] or ZERO) - (m["tax"] or ZERO) - (m["cogs"] or ZERO)
    month_expenses = Expense.objects.filter(date__gte=month_start, date__lte=today).aggregate(
        s=Sum("amount"))["s"] or ZERO

    return render(request, "core/dashboard.html", {
        "month": today, "month_gross": month_gross, "month_expenses": month_expenses,
        "month_net": month_gross - month_expenses,
        "today": today, "revenue": revenue, "orders": n, "avg": (revenue / n) if n else ZERO,
        "profit": profit, "margin": (profit / (revenue - tax) * 100) if revenue - tax else ZERO,
        "week": week, "week_total": sum((d["total"] for d in week), ZERO),
        "top": top, "low": low[:8], "low_count": low.count(),
        "stock_value": sum((i.stock_value for i in active), ZERO),
        "drafts": Purchase.objects.filter(status=Purchase.Status.DRAFT).count(),
    })


def _range(request):
    today = timezone.localdate()

    def parse(name, default):
        try:
            return date.fromisoformat(request.GET.get(name, ""))
        except ValueError:
            return default

    end = parse("end", today)
    start = parse("start", end - timedelta(days=29))
    if start > end:
        start, end = end, start
    return start, end


@manager_required
def reports(request):
    start, end = _range(request)
    orders = Order.objects.filter(status=Order.Status.PAID, created_at__date__range=(start, end))
    items = OrderItem.objects.filter(order__status=Order.Status.PAID, order__created_at__date__range=(start, end))

    agg = orders.aggregate(revenue=Sum("total"), tax=Sum("tax"), cogs=Sum("cogs"), disc=Sum("discount"), n=Count("id"))
    revenue, tax, cogs = (agg["revenue"] or ZERO), (agg["tax"] or ZERO), (agg["cogs"] or ZERO)
    net = revenue - tax
    profit = net - cogs

    by_day = list(
        orders.annotate(d=TruncDate("created_at")).values("d")
        .annotate(amount=Sum("total"), food=Sum("cogs"), vat=Sum("tax"), n=Count("id")).order_by("d")
    )
    for r in by_day:
        r["profit"] = r["amount"] - r["vat"] - r["food"]
    _bars(by_day, "amount")

    by_product = list(
        items.values("name")
        .annotate(q=Sum("quantity"), rev=Sum("line_total"), cost=Sum("line_cost")).order_by("-rev")
    )
    for r in by_product:
        r["profit"] = r["rev"] - r["cost"]

    by_payment = list(orders.values("payment_method").annotate(amount=Sum("total"), n=Count("id")).order_by("-amount"))
    labels = dict(Order.Payment.choices)
    for r in by_payment:
        r["label"] = labels.get(r["payment_method"], r["payment_method"])

    hours = {r["h"]: r for r in orders.annotate(h=ExtractHour("created_at")).values("h").order_by("h").annotate(n=Count("id"))}
    by_hour = _bars([{"label": f"{h:02d}:00", "n": hours[h]["n"] if h in hours else 0} for h in range(6, 24)], "n")

    purchased = sum(
        (i.quantity * i.unit_cost for i in PurchaseItem.objects.filter(
            purchase__status=Purchase.Status.RECEIVED, purchase__received_at__date__range=(start, end))),
        ZERO,
    )
    wasted = sum(
        (abs(m.quantity) * (m.unit_cost or ZERO) for m in StockMovement.objects.filter(
            kind=StockMovement.Kind.WASTE, created_at__date__range=(start, end))),
        ZERO,
    )
    voids = Order.objects.filter(status=Order.Status.VOID, created_at__date__range=(start, end)).aggregate(
        n=Count("id"), total=Sum("total"))

    expense_qs = Expense.objects.filter(date__range=(start, end))
    expenses_total = expense_qs.aggregate(s=Sum("amount"))["s"] or ZERO
    expense_cats = list(
        expense_qs.values("category__name").order_by().annotate(spent=Sum("amount")).order_by("-spent"))
    for r in expense_cats:
        r["name"] = r.pop("category__name")
    net_profit = profit - expenses_total

    return render(request, "core/reports.html", {
        "expenses_total": expenses_total, "expense_cats": expense_cats, "net_profit": net_profit,
        "net_margin": (net_profit / net * 100) if net else ZERO,
        "start": start, "end": end, "revenue": revenue, "tax": tax, "net": net, "cogs": cogs,
        "profit": profit, "margin": (profit / net * 100) if net else ZERO,
        "orders": agg["n"], "avg": (revenue / agg["n"]) if agg["n"] else ZERO, "discounts": agg["disc"] or ZERO,
        "by_day": by_day, "by_product": by_product, "by_payment": by_payment, "by_hour": by_hour,
        "purchased": purchased, "wasted": wasted, "voids": voids,
    })


@manager_required
def report_csv(request):
    start, end = _range(request)
    items = (
        OrderItem.objects.filter(order__created_at__date__range=(start, end))
        .select_related("order", "order__created_by").order_by("order__created_at", "id")
    )
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="sales_{start}_{end}.csv"'
    w = csv.writer(response)
    w.writerow(["order", "date", "time", "status", "type", "payment", "cashier", "item",
                "qty", "unit_price", "line_total", "line_cost"])
    for i in items:
        o = i.order
        local = timezone.localtime(o.created_at)
        w.writerow([o.number, local.date(), local.strftime("%H:%M"), o.status, o.order_type,
                    o.payment_method, o.created_by.get_username() if o.created_by else "",
                    i.name, i.quantity, i.unit_price, i.line_total, round(i.line_cost, 2)])
    return response
