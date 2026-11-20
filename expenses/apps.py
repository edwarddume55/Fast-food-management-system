from django.apps import AppConfig
from django.db.models.signals import post_migrate


def create_default_categories(sender, **kwargs):
    from .models import DEFAULT_CATEGORIES, ExpenseCategory

    for name in DEFAULT_CATEGORIES:
        ExpenseCategory.objects.get_or_create(name=name)


class ExpensesConfig(AppConfig):
    name = "expenses"

    def ready(self):
        post_migrate.connect(create_default_categories, sender=self)
