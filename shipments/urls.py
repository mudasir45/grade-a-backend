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
    path('last-shipment/', views.LastShipmentView.as_view(), name='last-shipment'),
    path('last-shipment/<str:user_id>/', views.LastShipmentView.as_view(), name='last-shipment-with-id'),
    
    # Staff shipments endpoints
    path('staff-shipments/', views.StaffShipmentsView.as_view(), name='staff-shipments'),
    path('staff-shipments/<str:staff_id>/', views.StaffShipmentsView.as_view(), name='staff-shipments-with-id'),
    path('assign-staff/', views.AssignStaffToShipmentView.as_view(), name='assign-staff'),
] 