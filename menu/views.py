from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from core.permissions import manager_required

from .forms import ProductForm, RecipeFormSet
from .models import Product


@manager_required
def product_list(request):
    products = Product.objects.select_related("category").prefetch_related("recipe__ingredient")
    return render(request, "menu/product_list.html", {"products": products})


@manager_required
def product_form(request, pk=None):
    product = get_object_or_404(Product, pk=pk) if pk else None
    form = ProductForm(request.POST or None, instance=product)
    formset = RecipeFormSet(request.POST or None, instance=product)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            saved = form.save()
            formset.instance = saved
            formset.save()
        messages.success(request, f"{saved.name} saved.")
        return redirect("product_list")
    return render(request, "menu/product_form.html", {"form": form, "formset": formset, "product": product})
