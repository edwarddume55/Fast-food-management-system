from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from .models import Expense, ExpenseCategory


class ExpenseTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_superuser("boss", password="pw12345!")
        User.objects.create_user("cashier", password="pw12345!")
        self.rent = ExpenseCategory.objects.get(name="Rent")   # created by post_migrate

    def test_default_categories_exist(self):
        self.assertTrue(ExpenseCategory.objects.filter(name="Salaries & wages").exists())

    def test_manager_can_record_expense(self):
        self.client.login(username="boss", password="pw12345!")
        r = self.client.post("/expenses/new/", {
            "date": timezone.localdate().isoformat(), "category": self.rent.pk,
            "description": "Shop rent", "amount": "60000", "payment_method": "BANK",
        })
        self.assertEqual(r.status_code, 302)
        e = Expense.objects.get()
        self.assertEqual(e.amount, Decimal("60000"))
        self.assertEqual(e.created_by, self.manager)

    def test_zero_or_negative_amount_rejected(self):
        self.client.login(username="boss", password="pw12345!")
        r = self.client.post("/expenses/new/", {
            "date": timezone.localdate().isoformat(), "category": self.rent.pk,
            "description": "x", "amount": "0", "payment_method": "CASH",
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Expense.objects.count(), 0)

    def test_cashier_is_blocked(self):
        self.client.login(username="cashier", password="pw12345!")
        self.assertEqual(self.client.get("/expenses/").status_code, 403)

    def test_report_subtracts_expenses_from_profit(self):
        today = timezone.localdate()
        Expense.objects.create(date=today, category=self.rent, description="Rent", amount=Decimal("1000"))
        Expense.objects.create(date=today - timedelta(days=400), category=self.rent,
                               description="Old", amount=Decimal("5000"))   # outside default range
        self.client.login(username="boss", password="pw12345!")
        ctx = self.client.get("/reports/").context
        self.assertEqual(ctx["expenses_total"], Decimal("1000"))
        self.assertEqual(ctx["net_profit"], Decimal("-1000"))   # no sales, so gross profit is 0

    def test_expenses_filtered_by_date_range(self):
        today = timezone.localdate()
        Expense.objects.create(date=today, category=self.rent, description="In", amount=Decimal("10"))
        Expense.objects.create(date=today - timedelta(days=90), category=self.rent,
                               description="Out", amount=Decimal("99"))
        self.client.login(username="boss", password="pw12345!")
        ctx = self.client.get("/expenses/").context
        self.assertEqual(ctx["total"], Decimal("10"))
