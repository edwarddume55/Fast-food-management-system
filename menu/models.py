from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=60, unique=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=120, unique=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0"))],
        help_text="Selling price, tax included.",
    )
    description = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category__sort_order", "name"]

    def __str__(self):
        return self.name

    # Use prefetch_related("recipe__ingredient") when calling these in loops.
    @property
    def cost(self):
        return sum((r.quantity * r.ingredient.avg_cost for r in self.recipe.all()), Decimal("0"))

    @property
    def margin(self):
        return self.price - self.cost

    @property
    def margin_pct(self):
        return (self.margin / self.price * 100) if self.price else Decimal("0")

    def max_servings(self):
        """How many can be made from current stock. None if there is no recipe."""
        items = list(self.recipe.all())
        if not items:
            return None
        return max(0, min(int(r.ingredient.stock // r.quantity) for r in items))


class RecipeItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="recipe")
    ingredient = models.ForeignKey("inventory.Ingredient", on_delete=models.PROTECT, related_name="recipe_items")
    quantity = models.DecimalField(
        max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))],
        help_text="Amount used per serving, in the ingredient's unit.",
    )

    class Meta:
        unique_together = [("product", "ingredient")]

    def __str__(self):
        return f"{self.product}: {self.quantity} {self.ingredient}"
