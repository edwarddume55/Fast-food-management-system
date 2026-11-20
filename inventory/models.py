from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Supplier(models.Model):
    name = models.CharField(max_length=120, unique=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Ingredient(models.Model):
    class Unit(models.TextChoices):
        PCS = "pcs", "pieces"
        KG = "kg", "kg"
        G = "g", "g"
        L = "l", "litres"
        ML = "ml", "ml"

    name = models.CharField(max_length=120, unique=True)
    unit = models.CharField(max_length=5, choices=Unit.choices, default=Unit.PCS)
    stock = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    reorder_level = models.DecimalField(
        max_digits=12, decimal_places=3, default=0,
        help_text="Raise a low-stock alert at or below this quantity.",
    )
    avg_cost = models.DecimalField(
        "average cost", max_digits=12, decimal_places=4, default=0,
        help_text="Cost per unit. Updated automatically when purchases are received.",
    )
    supplier = models.ForeignKey(
        Supplier, null=True, blank=True, on_delete=models.SET_NULL, related_name="ingredients"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def is_low(self):
        return self.reorder_level > 0 and self.stock <= self.reorder_level

    @property
    def stock_value(self):
        return max(self.stock, Decimal("0")) * self.avg_cost


class StockMovement(models.Model):
    """Append-only ledger. Every change to Ingredient.stock writes one row."""

    class Kind(models.TextChoices):
        PURCHASE = "PURCHASE", "Purchase received"
        SALE = "SALE", "Sale"
        VOID = "VOID", "Sale voided"
        WASTE = "WASTE", "Waste / spoilage"
        ADJUST = "ADJUST", "Stock count"

    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name="movements")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, help_text="Signed change.")
    unit_cost = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    balance_after = models.DecimalField(max_digits=12, decimal_places=3)
    reference = models.CharField(max_length=40, blank=True, db_index=True)
    note = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.ingredient} {self.quantity:+} ({self.kind})"


class Purchase(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        RECEIVED = "RECEIVED", "Received"
        CANCELLED = "CANCELLED", "Cancelled"

    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchases")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    notes = models.CharField(max_length=250, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    received_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.number

    @property
    def number(self):
        return f"PO-{self.pk:05d}" if self.pk else "PO-new"

    @property
    def total(self):
        return sum((i.line_total for i in self.items.all()), Decimal("0"))


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name="items")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name="+")
    quantity = models.DecimalField(
        max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))]
    )
    unit_cost = models.DecimalField(
        max_digits=12, decimal_places=4, validators=[MinValueValidator(Decimal("0"))]
    )

    @property
    def line_total(self):
        return self.quantity * self.unit_cost
