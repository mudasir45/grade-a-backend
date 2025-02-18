from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('invoices', views.InvoiceViewSet, basename='invoice')
router.register('payments', views.PaymentViewSet, basename='payment')
router.register('refunds', views.RefundViewSet, basename='refund')

app_name = 'payments'

urlpatterns = [
    path('', include(router.urls)),
] 