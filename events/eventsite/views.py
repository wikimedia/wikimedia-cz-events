from django.shortcuts import render
from django.http import HttpResponseRedirect
from eventsite.models import Registration, Event

# Create your views here.

def index(request):
    return render(request, 'index.html')

def verify(request):
    token = request.GET['token']
    reg = Registration.objects.get(id=int(request.GET['id']))
    if reg.confirmed:
        return HttpResponseRedirect(reg.event.already_confirmed_url)
    if reg.verify_token() == token:
        reg.confirmed = True
        reg.save()
        return HttpResponseRedirect(reg.event.successfully_confirmed_url)
    else:
        return HttpResponseRedirect(reg.event.invalid_token_url)