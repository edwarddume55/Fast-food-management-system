from decimal import Decimal

from django import forms
from django.forms import inlineformset_factory

from .models import Ingredient, Purchase, PurchaseItem, Supplier


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "phone", "email", "address", "is_active"]


class IngredientForm(forms.ModelForm):
    class Meta:
        model = Ingredient
        fields = ["name", "unit", "reorder_level", "avg_cost", "supplier", "is_active"]


class StockAdjustForm(forms.Form):
    MODES = [
        ("WASTE", "Waste or spoilage - remove this quantity"),
        ("COUNT", "Stock count - set stock to the counted quantity"),
    ]
    ingredient = forms.ModelChoiceField(queryset=Ingredient.objects.none())
    mode = forms.ChoiceField(choices=MODES, initial="WASTE")
    quantity = forms.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0"))
    note = forms.CharField(max_length=200, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ingredient"].queryset = Ingredient.objects.filter(is_active=True)


class PurchaseForm(forms.ModelForm):
    class Meta:
        model = Purchase
        fields = ["supplier", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier"].queryset = Supplier.objects.filter(is_active=True)


PurchaseItemFormSet = inlineformset_factory(
    Purchase, PurchaseItem,
    fields=("ingredient", "quantity", "unit_cost"),
    extra=4, can_delete=True,
)
