from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('calculate', views.ShippingRateViewSet, basename='shipping-rate')
router.register('countries', views.CountryViewSet, basename='country')  
router.register('shipping-zones', views.ShippingZoneViewSet, basename='shipping-zone')
router.register('service-types', views.ServiceTypeViewSet, basename='service-type')

app_name = 'shipping_rates'

urlpatterns = [
    path('calculate/', views.ShippingRateCalculatorView.as_view(), name='calculate-rate'),
    path('', include(router.urls)),
    path('extras', views.ExtrasView.as_view(), name="get-extras"),
    path('convert-currency/', views.CurrencyConversionAPIView.as_view(), name='convert-currency'),
    path('currencies/', views.CurrencyAPIView.as_view(), name='currencies'),
    path('dynamic-rates/', views.DynamicRateAPIView.as_view(), name='dynamic-rates'),
] 