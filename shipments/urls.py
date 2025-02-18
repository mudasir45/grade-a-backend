from django.urls import path
from . import views

app_name = 'shipments'

urlpatterns = [
    path('', views.ShipmentListCreateView.as_view(), name='shipment-list-create'),
    path('<str:pk>/', views.ShipmentDetailView.as_view(), name='shipment-detail'),
    path(
        'track/<str:tracking_number>/',
        views.ShipmentTrackingView.as_view(),
        name='shipment-tracking'
    ),
] 