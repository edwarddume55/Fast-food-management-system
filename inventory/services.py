"""All stock changes go through here so the ledger and the balance never drift."""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import Ingredient, Purchase, StockMovement


class StockError(Exception):
    pass


def record_movement(ingredient, kind, quantity, *, user=None, unit_cost=None, reference="", note=""):
    """Apply a signed quantity. The ingredient row must already be locked
    (select_for_update) inside a transaction."""
    ingredient.stock = ingredient.stock + quantity
    ingredient.save(update_fields=["stock", "avg_cost"])
    return StockMovement.objects.create(
        ingredient=ingredient,
        kind=kind,
        quantity=quantity,
        unit_cost=unit_cost,
        balance_after=ingredient.stock,
        reference=reference,
        note=note,
        created_by=user,
    )


@transaction.atomic
def receive_purchase(purchase_id, user):
    purchase = Purchase.objects.select_for_update().get(pk=purchase_id)
    if purchase.status != Purchase.Status.DRAFT:
        raise StockError("Only draft purchases can be received.")
    items = list(purchase.items.order_by("ingredient_id", "id"))
    if not items:
        raise StockError("Add at least one item before receiving.")

    for item in items:
        ing = Ingredient.objects.select_for_update().get(pk=item.ingredient_id)
        on_hand = max(ing.stock, Decimal("0"))
        new_total = on_hand + item.quantity
        # Weighted-average costing
        ing.avg_cost = (
            (on_hand * ing.avg_cost + item.quantity * item.unit_cost) / new_total
        ).quantize(Decimal("0.0001"))
        record_movement(
            ing, StockMovement.Kind.PURCHASE, item.quantity,
            user=user, unit_cost=item.unit_cost, reference=purchase.number,
        )

    purchase.status = Purchase.Status.RECEIVED
    purchase.received_at = timezone.now()
    purchase.save(update_fields=["status", "received_at"])
    return purchase


@transaction.atomic
def adjust_stock(ingredient_id, mode, quantity, user, note=""):
    """mode 'WASTE' removes `quantity`; mode 'COUNT' sets stock to `quantity`."""
    ing = Ingredient.objects.select_for_update().get(pk=ingredient_id)
    if mode == "WASTE":
        if quantity > ing.stock:
            raise StockError(f"Only {ing.stock.normalize():f} {ing.unit} of {ing.name} in stock.")
        return record_movement(
            ing, StockMovement.Kind.WASTE, -quantity,
            user=user, unit_cost=ing.avg_cost, note=note,
        )
    delta = quantity - ing.stock
    if delta == 0:
        return None
    return record_movement(
        ing, StockMovement.Kind.ADJUST, delta,
        user=user, unit_cost=ing.avg_cost, note=note or "Stock count",
    )
