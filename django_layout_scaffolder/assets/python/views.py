from django.shortcuts import render


def index(request):
    return render(request, "__APP_NAME__/index.html")
