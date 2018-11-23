from eventsite import views
from django.urls import path

urlpatterns = [
    path('', views.index),
    path('verify/<id>/<token>', views.verify, name='verify'),
    path('answer/<id>/<token>', views.answer, name="answer"),
]