import json
from datetime import date
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.permissions import is_manager, manager_required
from core.utils import paginate
from menu.models import Category, Product

from .models import Order
from .services import OrderError, availability, create_order, void_order


@login_required
def pos(request):
    products = (
        Product.objects.filter(is_active=True, category__is_active=True)
        .select_related("category").prefetch_related("recipe__ingredient")
    )
    categories = Category.objects.filter(is_active=True, products__is_active=True).distinct()
    data = {
        "currency": settings.CURRENCY,
        "checkout_url": reverse("checkout"),
        "categories": [{"id": c.id, "name": c.name} for c in categories],
        "products": [
            {"id": p.id, "name": p.name, "price": float(p.price), "cat": p.category_id, "left": p.max_servings()}
            for p in products
        ],
        "payments": [{"id": v, "label": l} for v, l in Order.Payment.choices],
        "types": [{"id": v, "label": l} for v, l in Order.Type.choices],
    }
    return render(request, "sales/pos.html", {"pos_data": data})


@login_required
@require_POST
def checkout(request):
    try:
        body = json.loads(request.body)
        lines = [(int(l["id"]), int(l["qty"])) for l in body["lines"]]
        discount = Decimal(str(body.get("discount") or 0))
        raw_tendered = body.get("tendered")
        tendered = Decimal(str(raw_tendered)) if raw_tendered not in (None, "") else None
        payment = str(body.get("payment", ""))
        order_type = str(body.get("order_type", ""))
        note = str(body.get("note", ""))
    except (ValueError, KeyError, TypeError, InvalidOperation):
        return JsonResponse({"ok": False, "error": "Invalid request."}, status=400)

    try:
        order = create_order(
            user=request.user, lines=lines, payment_method=payment, order_type=order_type,
            discount=discount, tendered=tendered, note=note,
        )
    except OrderError as exc:
        return JsonResponse({"ok": False, "error": str(exc), "left": availability()}, status=400)

    return JsonResponse({
        "ok": True,
        "number": order.number,
        "total": str(order.total),
        "change": str(order.change_due),
        "receipt_url": reverse("order_detail", args=[order.pk]) + "?print=1",
        "left": availability(),
    })


@login_required
def order_list(request):
    qs = Order.objects.select_related("created_by").prefetch_related("items")
    if not is_manager(request.user):
        qs = qs.filter(created_by=request.user)

    def parse(name):
        try:
            return date.fromisoformat(request.GET.get(name, ""))
        except ValueError:
            return None

    start, end = parse("start"), parse("end")
    status = request.GET.get("status", "")
    pay = request.GET.get("payment", "")
    if not start and not end and not request.GET:
        start = end = timezone.localdate()
    if start:
        qs = qs.filter(created_at__date__gte=start)
    if end:
        qs = qs.filter(created_at__date__lte=end)
    if status in Order.Status.values:
        qs = qs.filter(status=status)
    if pay in Order.Payment.values:
        qs = qs.filter(payment_method=pay)

    page, qstring = paginate(request, qs, 40)
    paid = [o for o in page.object_list if o.status == Order.Status.PAID]
    return render(request, "sales/order_list.html", {
        "page": page, "qs": qstring, "start": start, "end": end,
        "f_status": status, "f_payment": pay,
        "statuses": Order.Status.choices, "payments": Order.Payment.choices,
        "page_total": sum((o.total for o in paid), Decimal("0")),
    })


@login_required
def order_detail(request, pk):
    qs = Order.objects.select_related("created_by", "voided_by").prefetch_related("items")
    if not is_manager(request.user):
        qs = qs.filter(created_by=request.user)
    order = get_object_or_404(qs, pk=pk)
    return render(request, "sales/order_detail.html", {
        "order": order, "auto_print": request.GET.get("print") == "1",
    })


@manager_required
@require_POST
def order_void(request, pk):
    reason = request.POST.get("reason", "").strip()
    if not reason:
        messages.error(request, "Enter a reason to void this order.")
    else:
        try:
            void_order(pk, request.user, reason)
            messages.success(request, "Order voided and stock returned.")
        except OrderError as exc:
            messages.error(request, str(exc))
    return redirect("order_detail", pk=pk)
