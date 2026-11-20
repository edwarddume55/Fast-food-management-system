# Burger Barn - fast-food management system (Django)

Point of sale, recipe-based stock, purchasing, suppliers, waste tracking, running expenses and profit reports.
Menu prices are VAT-inclusive; defaults are Kenya (KES, 16% VAT, Africa/Nairobi).

## Run it

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations inventory menu sales expenses
python manage.py migrate
python manage.py seed_demo          # demo menu, stock and 2 weeks of sales (optional)
python manage.py runserver
```

Open http://127.0.0.1:8000 and sign in:

| User    | Password    | Can do                          |
|---------|-------------|---------------------------------|
| manager | manager123  | everything                      |
| cashier | cashier123  | take orders, see own orders     |

Change these before real use. For your own data skip `seed_demo` and run
`python manage.py createsuperuser` (superusers are managers). To make someone else a manager,
add them to the **Manager** group in `/admin/`. Anyone else is a cashier.

Run the tests: `python manage.py test`

## How it works

- **Ingredients** hold stock, reorder level and a weighted-average cost per unit.
- **Menu items** have a **recipe**: how much of each ingredient one serving uses.
  Cost, margin and "can make N" are calculated from the recipe.
- **Purchases** are drafted, then *received*. Receiving adds stock and updates average cost.
- **Sales (POS)**: checkout checks stock, deducts every recipe ingredient and records the sale in one
  database transaction. Prices and costs are read from the database, never trusted from the browser.
  Food cost is snapshotted on each order line so old profit figures never change.
- **Void** (managers): marks the order void and reverses exactly the stock movements the sale made.
- **Waste / stock count**: record spoilage or correct stock after a physical count.
- **Stock history** is an append-only ledger: every change to stock writes a row. Stock cannot be edited
  directly in the admin.
- **Expenses**: record rent, wages, electricity, water, gas, marketing, repairs and any other running cost
  (date, category, amount, who was paid, M-Pesa/receipt reference). Categories are editable. Expenses are kept
  separate from stock purchases on purpose: ingredient cost already reaches profit through food cost, so
  recording it twice would understate profit.
- **Profit and loss**: Sales - VAT - food cost = gross profit; gross profit - expenses = **net profit**.
  Shown for any date range in Reports, and month-to-date on the dashboard.
- **Dashboard & reports**: sales, orders, average ticket, gross profit, best sellers, busiest hours,
  payment mix, purchases, waste, voids, CSV export.

## Settings (environment variables)

`BUSINESS_NAME`, `CURRENCY`, `TAX_RATE` (0 to disable VAT), `DJANGO_TIME_ZONE`,
`DJANGO_SECRET_KEY`, `DJANGO_DEBUG` (set `0` in production), `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_ORIGINS`.

## Going to production

Use PostgreSQL (row locks on stock only matter on a real database), set `DJANGO_DEBUG=0` and a real
secret key, run `collectstatic`, and serve with gunicorn behind nginx (add WhiteNoise if you prefer one
process). Back up the database daily.

## Layout

```
config/      settings, urls
core/        dashboard, reports, permissions, template filters, seed_demo command
expenses/    running costs and categories
inventory/   suppliers, ingredients, purchases, stock ledger (services.py = all stock changes)
menu/        categories, products, recipes
sales/       POS, orders, receipts (services.py = create_order / void_order)
templates/   static/ (css, pos.js - no CDN, works offline on the LAN)
```
