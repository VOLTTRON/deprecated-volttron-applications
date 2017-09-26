from django.conf.urls import url, include
from api import views
from django.conf import settings
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

app_name = 'api'

urlpatterns = [
    url(r'ven_test/$', views.OADRPoll.as_view(), name='test_ven'),

]

urlpatterns += router.urls
