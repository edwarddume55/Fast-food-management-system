from django.conf import settings
from django.db import models


class Order(models.Model):
    class Status(models.TextChoices):
        PAID = "PAID", "Paid"
        VOID = "VOID", "Void"

    class Payment(models.TextChoices):
        CASH = "CASH", "Cash"
        MPESA = "MPESA", "M-Pesa"
        CARD = "CARD", "Card"

    class Type(models.TextChoices):
        DINE_IN = "DINE_IN", "Dine in"
        TAKEAWAY = "TAKEAWAY", "Takeaway"
        DELIVERY = "DELIVERY", "Delivery"

    status = models.CharField(max_length=5, choices=Status.choices, default=Status.PAID, db_index=True)
    order_type = models.CharField(max_length=10, choices=Type.choices, default=Type.DINE_IN)
    payment_method = models.CharField(max_length=6, choices=Payment.choices, default=Payment.CASH)

    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    tax = models.DecimalField("VAT included", max_digits=12, decimal_places=2, default=0)
    cogs = models.DecimalField("cost of goods", max_digits=12, decimal_places=4, default=0)
    tendered = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    change_due = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    note = models.CharField(max_length=200, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="orders"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    void_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.number

    @property
    def number(self):
        return f"ORD-{self.pk:06d}"

    @property
    def profit(self):
        return self.total - self.tax - self.cogs


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("menu.Product", on_delete=models.PROTECT, related_name="+")
    name = models.CharField(max_length=120)  # snapshot, survives renames
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    line_cost = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    def __str__(self):
        return f"{self.quantity} x {self.name}"
