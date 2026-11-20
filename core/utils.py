from django.core.paginator import Paginator


def paginate(request, queryset, per_page=40):
    page = Paginator(queryset, per_page).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return page, params.urlencode()
