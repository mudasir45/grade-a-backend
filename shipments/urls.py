from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = 'shipments'

# Create a router for ViewSets
router = DefaultRouter()
router.register(r'status-locations', views.ShipmentStatusLocationViewSet, basename='status-locations')
router.register(r'shipments', views.ShipmentRequestViewSet, basename='shipment')

urlpatterns = [
     path('bulk-package-status-update/', views.BulkPackageStatusUpdateView.as_view(), name='bulk-package-status-update'),
    path('', views.ShipmentListCreateView.as_view(), name='shipment-list-create'),
    path('viewsets/', include(router.urls)),
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
    path('staff-shipment/<str:pk>/', views.StaffShipmentManagementView.as_view(), name='staff-shipment-management'),
    path('assign-staff/', views.AssignStaffToShipmentView.as_view(), name='assign-staff'),
    path('create-shipment/<str:user_id>/', views.StaffShipmentCreateView.as_view(), name='create-shipment'),
    
    # Status update endpoints
    path('status-update/<str:shipment_id>/', views.StaffShipmentStatusUpdateView.as_view(), name='status-update'),
    # path('package-status-update/', views.BulkPackageStatusUpdateView.as_view(), name='package-status-update'),
   
    
    # Message generator endpoint
    path('message/<str:pk>/', views.ShipmentMessageGeneratorView.as_view(), name='shipment-message'),
    
    # AWB generation endpoint
    path('generate-awb/<str:shipment_id>/', views.StaffShipmentAWBView.as_view(), name='generate-awb'),
    
    # User shipment history endpoint (staff only)
    path('user-shipments/<str:user_id>/', views.UserShipmentHistoryView.as_view(), name='user-shipment-history'),
    
] 