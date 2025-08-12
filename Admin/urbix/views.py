from django.shortcuts import render
from django.views import View
from django.template import TemplateDoesNotExist

def home_view(request):
    return render(request, f"index.html")


def dynamic_view(request, page):
    print(f"Trying to render template: {page}")
    try:
        return render(request, f"{page}")
    except TemplateDoesNotExist as e:
        print(f"Template not found: {e}")
        try:
            return render(request, f"pages-404.html")
        except TemplateDoesNotExist as e2:
            print(f"404 template not found: {e2}")
            return HttpResponse("Page not found", status=404)
    