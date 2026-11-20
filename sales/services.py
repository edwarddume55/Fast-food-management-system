from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from inventory.models import Ingredient, StockMovement
from inventory.services import record_movement
from menu.models import Product

from .models import Order, OrderItem

CENT = Decimal("0.01")


class OrderError(Exception):
    pass


def availability():
    """{product_id: servings left, or None if untracked} for active products."""
    products = Product.objects.filter(is_active=True).prefetch_related("recipe__ingredient")
    return {p.id: p.max_servings() for p in products}


@transaction.atomic
def create_order(*, user, lines, payment_method, order_type,
                 discount=Decimal("0"), tendered=None, note=""):
    """lines: iterable of (product_id, quantity). Prices and costs come from the
    database, never from the client. Stock is checked and deducted atomically."""
    if payment_method not in Order.Payment.values:
        raise OrderError("Choose a payment method.")
    if order_type not in Order.Type.values:
        raise OrderError("Choose an order type.")

    wanted = defaultdict(int)
    for pid, qty in lines:
        if qty <= 0:
            raise OrderError("Quantities must be at least 1.")
        wanted[pid] += qty
    if not wanted:
        raise OrderError("The cart is empty.")

    products = {
        p.id: p
        for p in Product.objects.filter(id__in=list(wanted), is_active=True).prefetch_related("recipe")
    }
    if len(products) != len(wanted):
        raise OrderError("An item in the cart is no longer on the menu.")

    # Total ingredient demand across the whole order
    needs = defaultdict(Decimal)
    for pid, qty in wanted.items():
        for r in products[pid].recipe.all():
            needs[r.ingredient_id] += r.quantity * qty

    # Lock ingredient rows in a stable order to avoid deadlocks
    ingredients = {
        i.id: i for i in Ingredient.objects.select_for_update().filter(id__in=list(needs)).order_by("id")
    }
    short = [ingredients[i].name for i, need in needs.items() if ingredients[i].stock < need]
    if short:
        raise OrderError("Not enough stock for: " + ", ".join(sorted(short)) + ".")

    subtotal = Decimal("0")
    cogs = Decimal("0")
    rows = []
    for pid, qty in wanted.items():
        p = products[pid]
        unit_cost = sum((r.quantity * ingredients[r.ingredient_id].avg_cost for r in p.recipe.all()), Decimal("0"))
        line_total = p.price * qty
        subtotal += line_total
        cogs += unit_cost * qty
        rows.append((p, qty, unit_cost, line_total))

    discount = max(Decimal("0"), min(discount, subtotal)).quantize(CENT)
    total = (subtotal - discount).quantize(CENT)
    rate = settings.TAX_RATE
    tax = (total * rate / (1 + rate)).quantize(CENT, rounding=ROUND_HALF_UP) if rate else Decimal("0")

    if payment_method == Order.Payment.CASH:
        if tendered is None or tendered < total:
            raise OrderError("Cash tendered is less than the total.")
    else:
        tendered = total
    change = (tendered - total).quantize(CENT)

    order = Order.objects.create(
        order_type=order_type, payment_method=payment_method,
        subtotal=subtotal, discount=discount, total=total, tax=tax,
        cogs=cogs.quantize(Decimal("0.0001")),
        tendered=tendered, change_due=change, note=note[:200], created_by=user,
    )
    OrderItem.objects.bulk_create([
        OrderItem(
            order=order, product=p, name=p.name, quantity=qty, unit_price=p.price,
            line_total=line_total, unit_cost=unit_cost, line_cost=unit_cost * qty,
        )
        for p, qty, unit_cost, line_total in rows
    ])
    for iid, need in needs.items():
        ing = ingredients[iid]
        record_movement(
            ing, StockMovement.Kind.SALE, -need,
            user=user, unit_cost=ing.avg_cost, reference=order.number,
        )
    return order


@transaction.atomic
def void_order(order_id, user, reason):
    """Mark an order void and put back exactly what the sale took out."""
    order = Order.objects.select_for_update().get(pk=order_id)
    if order.status == Order.Status.VOID:
        raise OrderError("This order is already void.")
    sales = list(
        StockMovement.objects.filter(kind=StockMovement.Kind.SALE, reference=order.number)
        .order_by("ingredient_id")
    )
    for mv in sales:
        ing = Ingredient.objects.select_for_update().get(pk=mv.ingredient_id)
        record_movement(
            ing, StockMovement.Kind.VOID, -mv.quantity,
            user=user, unit_cost=mv.unit_cost, reference=order.number, note=reason[:200],
        )
    order.status = Order.Status.VOID
    order.voided_at = timezone.now()
    order.voided_by = user
    order.void_reason = reason[:200]
    order.save(update_fields=["status", "voided_at", "voided_by", "void_reason"])
    return order
