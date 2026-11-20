from django.urls import path

from . import views

urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("new/", views.product_form, name="product_create"),
    path("<int:pk>/edit/", views.product_form, name="product_edit"),
]
