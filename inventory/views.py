from django.contrib import messages
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.permissions import manager_required
from core.utils import paginate

from .forms import (IngredientForm, PurchaseForm, PurchaseItemFormSet,
                    StockAdjustForm, SupplierForm)
from .models import Ingredient, Purchase, StockMovement, Supplier
from .services import StockError, adjust_stock, receive_purchase


# ---------------------------------------------------------------- ingredients
@manager_required
def ingredient_list(request):
    qs = Ingredient.objects.select_related("supplier")
    q = request.GET.get("q", "").strip()
    low = bool(request.GET.get("low"))
    if q:
        qs = qs.filter(name__icontains=q)
    if low:
        qs = qs.filter(is_active=True, reorder_level__gt=0, stock__lte=F("reorder_level"))
    return render(request, "inventory/ingredient_list.html", {
        "ingredients": qs, "q": q, "low": low,
        "stock_value": sum(i.stock_value for i in qs if i.is_active),
    })


@manager_required
def ingredient_form(request, pk=None):
    obj = get_object_or_404(Ingredient, pk=pk) if pk else None
    form = IngredientForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Ingredient saved.")
        return redirect("ingredient_list")
    return render(request, "form.html", {
        "form": form, "title": "Edit ingredient" if obj else "New ingredient",
        "back": "ingredient_list",
        "hint": None if obj else "Starting stock is added by receiving a purchase, so costs stay accurate.",
    })


@manager_required
def stock_adjust(request):
    initial = {"ingredient": request.GET.get("ingredient")}
    form = StockAdjustForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        cd = form.cleaned_data
        try:
            adjust_stock(cd["ingredient"].pk, cd["mode"], cd["quantity"], request.user, cd["note"])
        except StockError as exc:
            form.add_error("quantity", str(exc))
        else:
            messages.success(request, "Stock updated.")
            return redirect("movement_list")
    return render(request, "form.html", {
        "form": form, "title": "Record waste or stock count", "back": "ingredient_list",
        "hint": "Use waste for spoiled or dropped food. Use a stock count after a physical check.",
    })


@manager_required
def movement_list(request):
    qs = StockMovement.objects.select_related("ingredient", "created_by")
    ingredient = request.GET.get("ingredient", "")
    kind = request.GET.get("kind", "")
    if ingredient.isdigit():
        qs = qs.filter(ingredient_id=ingredient)
    if kind in StockMovement.Kind.values:
        qs = qs.filter(kind=kind)
    page, qstring = paginate(request, qs, 50)
    return render(request, "inventory/movement_list.html", {
        "page": page, "qs": qstring, "kinds": StockMovement.Kind.choices,
        "ingredients": Ingredient.objects.all(), "f_ingredient": ingredient, "f_kind": kind,
    })


# ------------------------------------------------------------------ suppliers
@manager_required
def supplier_list(request):
    return render(request, "inventory/supplier_list.html", {"suppliers": Supplier.objects.all()})


@manager_required
def supplier_form(request, pk=None):
    obj = get_object_or_404(Supplier, pk=pk) if pk else None
    form = SupplierForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Supplier saved.")
        return redirect("supplier_list")
    return render(request, "form.html", {
        "form": form, "title": "Edit supplier" if obj else "New supplier", "back": "supplier_list",
    })


# ------------------------------------------------------------------ purchases
@manager_required
def purchase_list(request):
    qs = Purchase.objects.select_related("supplier").prefetch_related("items")
    status = request.GET.get("status", "")
    if status in Purchase.Status.values:
        qs = qs.filter(status=status)
    return render(request, "inventory/purchase_list.html", {
        "purchases": qs[:200], "statuses": Purchase.Status.choices, "f_status": status,
    })


@manager_required
def purchase_form(request, pk=None):
    purchase = get_object_or_404(Purchase, pk=pk) if pk else None
    if purchase and purchase.status != Purchase.Status.DRAFT:
        messages.error(request, "Only draft purchases can be edited.")
        return redirect("purchase_detail", pk=purchase.pk)

    form = PurchaseForm(request.POST or None, instance=purchase)
    formset = PurchaseItemFormSet(request.POST or None, instance=purchase)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        has_items = any(
            f.cleaned_data and not f.cleaned_data.get("DELETE") for f in formset.forms
        )
        if not has_items:
            messages.error(request, "Add at least one item.")
        else:
            with transaction.atomic():
                saved = form.save(commit=False)
                if not saved.pk:
                    saved.created_by = request.user
                saved.save()
                formset.instance = saved
                formset.save()
            messages.success(request, f"{saved.number} saved as draft.")
            return redirect("purchase_detail", pk=saved.pk)
    return render(request, "inventory/purchase_form.html", {
        "form": form, "formset": formset, "purchase": purchase,
    })


@manager_required
def purchase_detail(request, pk):
    purchase = get_object_or_404(
        Purchase.objects.select_related("supplier", "created_by").prefetch_related("items__ingredient"),
        pk=pk,
    )
    return render(request, "inventory/purchase_detail.html", {"purchase": purchase})


@manager_required
@require_POST
def purchase_receive(request, pk):
    try:
        receive_purchase(pk, request.user)
        messages.success(request, "Purchase received. Stock and average costs are updated.")
    except StockError as exc:
        messages.error(request, str(exc))
    return redirect("purchase_detail", pk=pk)


@manager_required
@require_POST
def purchase_cancel(request, pk):
    purchase = get_object_or_404(Purchase, pk=pk)
    if purchase.status == Purchase.Status.DRAFT:
        purchase.status = Purchase.Status.CANCELLED
        purchase.save(update_fields=["status"])
        messages.success(request, "Purchase cancelled.")
    else:
        messages.error(request, "Only draft purchases can be cancelled.")
    return redirect("purchase_detail", pk=pk)
