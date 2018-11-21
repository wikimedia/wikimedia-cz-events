from django.contrib import admin
from eventsite import models
from django.urls import path
from django.http import HttpResponseRedirect
from django.contrib import messages
import simplejson as json

class EventAdmin(admin.ModelAdmin):
    exclude = ('header', )

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('<id>/pull/', self.admin_site.admin_view(self.pull))
        ]
        return my_urls + urls

    def pull(self, request, id):
        models.Event.objects.get(id=id).pull() # TODO: This should be asynchronous
        messages.success(request, 'Pull of participants was successfully done')
        return HttpResponseRedirect(request.path + "../change/")

    class Meta:
        model = models.Event
admin.site.register(models.Event, EventAdmin)

class MailTextAdmin(admin.ModelAdmin):
    class Meta:
        model = models.MailText
admin.site.register(models.MailText, MailTextAdmin)

class RegistrationAdmin(admin.ModelAdmin):
    readonly_fields = ('data', )
    list_display = ('full_name', 'event', 'verified', 'confirmed')
    class Meta:
        model = models.Registration
admin.site.register(models.Registration, RegistrationAdmin)