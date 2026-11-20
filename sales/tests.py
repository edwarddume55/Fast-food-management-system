from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from inventory.models import Ingredient, Purchase, PurchaseItem, StockMovement, Supplier
from inventory.services import StockError, receive_purchase
from menu.models import Category, Product, RecipeItem

from .models import Order
from .services import OrderError, create_order, void_order


class StockAndSalesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("cashier", password="pw12345!")
        supplier = Supplier.objects.create(name="Test supplier")
        self.bun = Ingredient.objects.create(name="Bun", unit="pcs")
        self.patty = Ingredient.objects.create(name="Patty", unit="pcs")
        self.receive([(self.bun, 10, "20"), (self.patty, 10, "80")], supplier)
        cat = Category.objects.create(name="Burgers")
        self.burger = Product.objects.create(name="Burger", category=cat, price=Decimal("400"))
        RecipeItem.objects.create(product=self.burger, ingredient=self.bun, quantity=1)
        RecipeItem.objects.create(product=self.burger, ingredient=self.patty, quantity=1)

    def receive(self, rows, supplier=None):
        supplier = supplier or Supplier.objects.first()
        po = Purchase.objects.create(supplier=supplier)
        for ing, qty, cost in rows:
            PurchaseItem.objects.create(purchase=po, ingredient=ing, quantity=qty, unit_cost=Decimal(cost))
        receive_purchase(po.pk, self.user)
        return po

    def sell(self, qty, **kw):
        args = dict(user=self.user, lines=[(self.burger.id, qty)], payment_method="CASH",
                    order_type="DINE_IN", tendered=Decimal("5000"))
        args.update(kw)
        return create_order(**args)

    def test_receiving_sets_stock_and_weighted_average_cost(self):
        self.bun.refresh_from_db()
        self.assertEqual(self.bun.stock, 10)
        self.assertEqual(self.bun.avg_cost, Decimal("20"))
        self.receive([(self.bun, 10, "30")])
        self.bun.refresh_from_db()
        self.assertEqual(self.bun.stock, 20)
        self.assertEqual(self.bun.avg_cost, Decimal("25"))

    def test_purchase_cannot_be_received_twice(self):
        po = Purchase.objects.first()
        with self.assertRaises(StockError):
            receive_purchase(po.pk, self.user)

    def test_sale_deducts_stock_and_snapshots_cost(self):
        order = self.sell(3, tendered=Decimal("1500"))
        self.bun.refresh_from_db()
        self.patty.refresh_from_db()
        self.assertEqual((self.bun.stock, self.patty.stock), (7, 7))
        self.assertEqual(order.total, Decimal("1200.00"))
        self.assertEqual(order.change_due, Decimal("300.00"))
        self.assertEqual(order.cogs, Decimal("300"))          # 3 x (20 + 80)
        self.assertEqual(order.tax, Decimal("165.52"))        # 16% VAT included
        self.assertEqual(StockMovement.objects.filter(reference=order.number).count(), 2)

    def test_prices_come_from_the_database(self):
        order = self.sell(1)
        self.assertEqual(order.items.get().unit_price, Decimal("400.00"))

    def test_insufficient_stock_rolls_everything_back(self):
        with self.assertRaises(OrderError):
            self.sell(11)
        self.bun.refresh_from_db()
        self.assertEqual(self.bun.stock, 10)
        self.assertEqual(Order.objects.count(), 0)

    def test_cash_underpayment_is_rejected(self):
        with self.assertRaises(OrderError):
            self.sell(1, tendered=Decimal("100"))
        self.assertEqual(Order.objects.count(), 0)

    def test_discount_is_capped_at_subtotal(self):
        order = self.sell(1, discount=Decimal("9999"), payment_method="MPESA", tendered=None)
        self.assertEqual(order.total, Decimal("0.00"))

    def test_void_returns_stock_once(self):
        order = self.sell(4)
        void_order(order.pk, self.user, "Customer left")
        self.bun.refresh_from_db()
        self.assertEqual(self.bun.stock, 10)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.VOID)
        with self.assertRaises(OrderError):
            void_order(order.pk, self.user, "again")


class AccessTests(TestCase):
    def setUp(self):
        self.cashier = User.objects.create_user("cashier", password="pw12345!")

    def test_pos_requires_login(self):
        self.assertEqual(self.client.get("/sales/pos/").status_code, 302)

    def test_cashier_can_open_pos_but_not_inventory(self):
        self.client.login(username="cashier", password="pw12345!")
        self.assertEqual(self.client.get("/sales/pos/").status_code, 200)
        self.assertEqual(self.client.get("/inventory/").status_code, 403)
        self.assertEqual(self.client.get("/reports/").status_code, 403)

    def test_cashier_dashboard_redirects_to_pos(self):
        self.client.login(username="cashier", password="pw12345!")
        self.assertRedirects(self.client.get("/"), "/sales/pos/")
