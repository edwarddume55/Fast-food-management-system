from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

DEFAULT_CATEGORIES = [
    "Rent", "Salaries & wages", "Electricity", "Water", "Gas", "Internet & phone",
    "Transport & delivery", "Marketing", "Repairs & maintenance", "Cleaning & hygiene",
    "Licenses & permits", "Bank & M-Pesa charges", "Other",
]


class ExpenseCategory(models.Model):
    name = models.CharField(max_length=80, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "expense categories"

    def __str__(self):
        return self.name


class Expense(models.Model):
    """Running costs other than ingredients. Stock purchases belong in Purchases:
    their cost reaches profit through food cost, so recording them here would count them twice."""

    class Payment(models.TextChoices):
        CASH = "CASH", "Cash"
        MPESA = "MPESA", "M-Pesa"
        BANK = "BANK", "Bank transfer"
        CARD = "CARD", "Card"

    date = models.DateField(default=timezone.localdate, db_index=True)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name="expenses")
    description = models.CharField(max_length=200)
    payee = models.CharField("paid to", max_length=120, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    payment_method = models.CharField(max_length=6, choices=Payment.choices, default=Payment.CASH)
    reference = models.CharField("receipt / M-Pesa code", max_length=60, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.date} {self.category}: {self.amount}"
