from django import forms
from django.forms import inlineformset_factory

from .models import Product, RecipeItem


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "category", "price", "description", "is_active"]


RecipeFormSet = inlineformset_factory(
    Product, RecipeItem, fields=("ingredient", "quantity"), extra=4, can_delete=True
)
