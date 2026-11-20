import csv
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.permissions import manager_required
from core.utils import paginate

from .forms import CategoryForm, ExpenseForm
from .models import Expense, ExpenseCategory


def _filtered(request):
    today = timezone.localdate()

    def parse(name, default):
        try:
            return date.fromisoformat(request.GET.get(name, ""))
        except ValueError:
            return default

    start = parse("start", today.replace(day=1))
    end = parse("end", today)
    if start > end:
        start, end = end, start
    qs = Expense.objects.select_related("category", "created_by").filter(date__range=(start, end))
    cat = request.GET.get("category", "")
    if cat.isdigit():
        qs = qs.filter(category_id=cat)
    return qs, start, end, cat


@manager_required
def expense_list(request):
    qs, start, end, cat = _filtered(request)
    total = qs.aggregate(s=Sum("amount"))["s"] or Decimal("0")
    by_cat = list(qs.values("category__name").order_by().annotate(spent=Sum("amount")).order_by("-spent"))
    for r in by_cat:
        r["name"] = r.pop("category__name")
        r["pct"] = int(r["spent"] / total * 100) if total else 0
    page, qstring = paginate(request, qs, 40)
    return render(request, "expenses/expense_list.html", {
        "page": page, "qs": qstring, "start": start, "end": end, "total": total, "by_cat": by_cat,
        "categories": ExpenseCategory.objects.all(), "f_category": cat,
    })


@manager_required
def expense_form(request, pk=None):
    obj = get_object_or_404(Expense, pk=pk) if pk else None
    form = ExpenseForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        if not saved.pk:
            saved.created_by = request.user
        saved.save()
        messages.success(request, "Expense saved.")
        return redirect("expense_list")
    return render(request, "form.html", {
        "form": form, "title": "Edit expense" if obj else "Record an expense", "back": "expense_list",
        "hint": "For rent, wages, bills and other running costs. Record ingredient buying under Purchases instead.",
    })


@manager_required
@require_POST
def expense_delete(request, pk):
    get_object_or_404(Expense, pk=pk).delete()
    messages.success(request, "Expense deleted.")
    return redirect("expense_list")


@manager_required
def category_list(request):
    form = CategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Category added.")
        return redirect("expense_category_list")
    return render(request, "expenses/category_list.html", {
        "form": form, "categories": ExpenseCategory.objects.all(),
    })


@manager_required
@require_POST
def category_toggle(request, pk):
    cat = get_object_or_404(ExpenseCategory, pk=pk)
    cat.is_active = not cat.is_active
    cat.save(update_fields=["is_active"])
    return redirect("expense_category_list")


@manager_required
def expense_csv(request):
    qs, start, end, _ = _filtered(request)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="expenses_{start}_{end}.csv"'
    w = csv.writer(response)
    w.writerow(["date", "category", "description", "paid_to", "amount", "method", "reference", "recorded_by"])
    for e in qs.order_by("date", "id"):
        w.writerow([e.date, e.category.name, e.description, e.payee, e.amount, e.payment_method,
                    e.reference, e.created_by.get_username() if e.created_by else ""])
    return response
