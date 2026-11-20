import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.utils import timezone

from expenses.models import DEFAULT_CATEGORIES, Expense, ExpenseCategory
from inventory.models import Ingredient, Purchase, PurchaseItem, Supplier
from inventory.services import receive_purchase
from menu.models import Category, Product, RecipeItem
from sales.models import Order
from sales.services import OrderError, create_order

SUPPLIERS = ["Mama Oven Bakery", "Kariokor Butchery", "Limuru Dairy", "Wakulima Fresh Produce", "Eastleigh Wholesale"]

# name, unit, cost per unit, reorder level, supplier
INGREDIENTS = [
    ("Burger bun", "pcs", 18, 60, 0), ("Hot dog bun", "pcs", 15, 30, 0),
    ("Beef patty", "pcs", 75, 50, 1), ("Chicken fillet", "pcs", 85, 40, 1),
    ("Chicken piece", "pcs", 60, 60, 1), ("Chicken wing", "pcs", 22, 100, 1), ("Sausage", "pcs", 35, 30, 1),
    ("Cheese slice", "pcs", 14, 80, 2), ("Milk", "l", 120, 15, 2), ("Ice cream mix", "l", 450, 5, 2),
    ("Lettuce", "kg", 220, 3, 3), ("Tomato", "kg", 150, 4, 3), ("Potatoes", "kg", 90, 20, 3),
    ("Cooking oil", "l", 320, 10, 4), ("Ketchup", "l", 380, 3, 4), ("Burger sauce", "l", 520, 2, 4),
    ("Soda 300ml", "pcs", 45, 48, 4), ("Bottled water 500ml", "pcs", 28, 48, 4), ("Paper packaging", "pcs", 8, 150, 4),
]

# category, name, price, recipe {ingredient: qty}
PRODUCTS = [
    ("Burgers", "Classic Beef Burger", 450, {"Burger bun": 1, "Beef patty": 1, "Lettuce": .02, "Tomato": .03, "Burger sauce": .02, "Paper packaging": 1}),
    ("Burgers", "Cheeseburger", 520, {"Burger bun": 1, "Beef patty": 1, "Cheese slice": 1, "Lettuce": .02, "Burger sauce": .02, "Paper packaging": 1}),
    ("Burgers", "Crispy Chicken Burger", 480, {"Burger bun": 1, "Chicken fillet": 1, "Lettuce": .02, "Burger sauce": .02, "Cooking oil": .03, "Paper packaging": 1}),
    ("Chicken", "Fried Chicken (2 pc)", 550, {"Chicken piece": 2, "Cooking oil": .05, "Paper packaging": 1}),
    ("Chicken", "Wings (6 pc)", 600, {"Chicken wing": 6, "Cooking oil": .05, "Paper packaging": 1}),
    ("Sides", "Fries", 200, {"Potatoes": .25, "Cooking oil": .06, "Ketchup": .03, "Paper packaging": 1}),
    ("Sides", "Hot Dog", 250, {"Hot dog bun": 1, "Sausage": 1, "Ketchup": .02, "Paper packaging": 1}),
    ("Drinks", "Soda", 100, {"Soda 300ml": 1}),
    ("Drinks", "Water", 80, {"Bottled water 500ml": 1}),
    ("Drinks", "Vanilla Shake", 350, {"Milk": .25, "Ice cream mix": .15}),
]


class Command(BaseCommand):
    help = "Create demo users, menu, stock and two weeks of sales."

    def add_arguments(self, parser):
        parser.add_argument("--no-sales", action="store_true", help="Skip generating historical sales.")

    def handle(self, *args, **opts):
        mgr_group, _ = Group.objects.get_or_create(name=settings.MANAGER_GROUP)
        for username, pwd, manager in [("manager", "manager123", True), ("cashier", "cashier123", False)]:
            user, created = User.objects.get_or_create(username=username, defaults={"is_staff": manager})
            if created:
                user.set_password(pwd)
                user.save()
            if manager:
                user.groups.add(mgr_group)
        cashier = User.objects.get(username="cashier")
        manager = User.objects.get(username="manager")

        suppliers = [Supplier.objects.get_or_create(name=n)[0] for n in SUPPLIERS]
        ingredients = {}
        for name, unit, cost, reorder, sup in INGREDIENTS:
            ing, _ = Ingredient.objects.get_or_create(
                name=name, defaults={"unit": unit, "reorder_level": reorder, "supplier": suppliers[sup]})
            ingredients[name] = (ing, Decimal(cost), reorder, sup)

        cats = {}
        for i, name in enumerate(["Burgers", "Chicken", "Sides", "Drinks"]):
            cats[name] = Category.objects.get_or_create(name=name, defaults={"sort_order": i})[0]
        for cat, name, price, recipe in PRODUCTS:
            product, created = Product.objects.get_or_create(name=name, defaults={"category": cats[cat], "price": price})
            if created:
                for ing_name, q in recipe.items():
                    RecipeItem.objects.create(product=product, ingredient=ingredients[ing_name][0], quantity=Decimal(str(q)))

        if not Purchase.objects.exists():
            for si, supplier in enumerate(suppliers):
                purchase = Purchase.objects.create(supplier=supplier, created_by=manager, notes="Opening stock")
                for ing, cost, reorder, sup in ingredients.values():
                    if sup == si:
                        PurchaseItem.objects.create(purchase=purchase, ingredient=ing, quantity=reorder * 10, unit_cost=cost)
                receive_purchase(purchase.pk, manager)

        if not Expense.objects.exists():
            self.generate_expenses(manager)

        if not opts["no_sales"] and not Order.objects.exists():
            self.generate_sales(cashier)

        self.stdout.write(self.style.SUCCESS(
            "Demo data ready.\n  manager / manager123  (full access)\n  cashier / cashier123  (POS only)\n"
            "Change these passwords before real use."))

    def generate_expenses(self, manager):
        for name in DEFAULT_CATEGORIES:
            ExpenseCategory.objects.get_or_create(name=name)
        cat = {c.name: c for c in ExpenseCategory.objects.all()}
        today = timezone.localdate()
        this_month = today.replace(day=1)
        last_month = (this_month - timedelta(days=1)).replace(day=1)
        rows = [
            (last_month, "Rent", "Shop rent", "Landlord", 60000, "BANK"),
            (this_month, "Rent", "Shop rent", "Landlord", 60000, "BANK"),
            (last_month + timedelta(days=24), "Salaries & wages", "Staff wages", "Kitchen & counter team", 95000, "MPESA"),
            (today - timedelta(days=9), "Electricity", "KPLC tokens", "Kenya Power", 7800, "MPESA"),
            (today - timedelta(days=8), "Water", "Water bill", "Nairobi Water", 2400, "MPESA"),
            (today - timedelta(days=6), "Gas", "Cooking gas refill", "Gas depot", 3200, "CASH"),
            (today - timedelta(days=5), "Marketing", "Flyers and social ads", "", 4500, "MPESA"),
            (today - timedelta(days=3), "Repairs & maintenance", "Fryer thermostat", "Cool Fix Ltd", 6500, "CASH"),
            (today - timedelta(days=1), "Cleaning & hygiene", "Detergents and bin liners", "", 1800, "CASH"),
        ]
        for d, c, desc, payee, amount, method in rows:
            if d <= today:
                Expense.objects.create(date=d, category=cat[c], description=desc, payee=payee,
                                       amount=amount, payment_method=method, created_by=manager)

    def generate_sales(self, cashier):
        random.seed(7)
        products = list(Product.objects.filter(is_active=True))
        now = timezone.now()
        made = 0
        for back in range(13, -1, -1):
            day = timezone.localdate() - timedelta(days=back)
            for _ in range(random.randint(18, 40)):
                hour = random.choices([9, 10, 11, 12, 13, 14, 15, 17, 18, 19, 20, 21],
                                      [2, 3, 5, 10, 10, 6, 3, 4, 8, 9, 6, 3])[0]
                when = timezone.make_aware(datetime.combine(day, time(hour, random.randint(0, 59))))
                when = min(when, now)
                chosen = random.sample(products, random.randint(1, 4))
                pay = random.choices(["CASH", "MPESA", "CARD"], [5, 6, 2])[0]
                lines = [(p.id, random.randint(1, 2)) for p in chosen]
                total = sum(p.price * q for p, (_, q) in zip(chosen, lines))
                try:
                    order = create_order(
                        user=cashier, lines=lines, payment_method=pay,
                        order_type=random.choice(["DINE_IN", "TAKEAWAY", "TAKEAWAY", "DELIVERY"]),
                        tendered=(total + 500) if pay == "CASH" else None)
                except OrderError:
                    continue  # ran out of something - realistic
                Order.objects.filter(pk=order.pk).update(created_at=when)
                made += 1
        self.stdout.write(f"Generated {made} historical orders.")
