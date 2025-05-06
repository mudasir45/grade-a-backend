from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views, views_driver

app_name = 'accounts'

# Register default router for ViewSets
router = DefaultRouter()
router.register('users', views.UserViewSet, basename='user')

urlpatterns = [
    # User authentication & management
    path('signup/', views.SignUpView.as_view(), name='signup'),
    path('login/', views.PhoneTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('user-countries/', views.UserCountryView.as_view(), name='user-countries'),
    path('contact/', views.ContactView.as_view(), name='contact'),
    path('stores/', views.StoresView.as_view(), name='stores'),
    path('check-staff-user/', views.CheckStaffUserView.as_view(), name='check-staff-user'),
    path('check-driver-user/', views.CheckDriverUserView.as_view(), name='check-driver-user'),
    path('cities/', views.CitiesView.as_view(), name='cities'),
    
    # Staff-related endpoints
    path('staff-associated-users/', views.StaffAssociatedUsersView.as_view(), name='staff-associated-users'),
    
    # Driver-related endpoints
    path('driver/dashboard/', views_driver.DriverDashboardView.as_view(), name='driver-dashboard'),
    path('driver/shipments/', views_driver.DriverShipmentList.as_view(), name='driver-shipments'),
    path('driver/buy4me/', views_driver.DriverBuy4MeList.as_view(), name='driver-buy4me'),
    path('driver/shipments/<str:shipment_id>/update/', 
         views_driver.DriverShipmentStatusUpdateView.as_view(), 
         name='driver-shipment-update'),
    path('driver/buy4me/<str:request_id>/update/', 
         views_driver.DriverBuy4MeStatusUpdateView.as_view(), 
         name='driver-buy4me-update'),
    path('driver/earnings/', views_driver.DriverEarningsView.as_view(), name='driver-earnings'),
    path('driver/payments/', views.DriverPaymentView.as_view(), name='driver-payments'),
    path('driver/bulk-payments/', views_driver.BulkDriverPaymentView.as_view(), name='driver-bulk-payments'),
    
    # Support ticket endpoints
    path('tickets/', views.SupportTicketListCreateView.as_view(), name='ticket-list-create'),
    path('tickets/<str:ticket_number>/', views.SupportTicketDetailView.as_view(), name='ticket-detail'),
    
    # Assign driver to shipment
    path('assign-driver-to-shipment/', views.AssignDriverToShipmentView.as_view(), name='assign-driver-to-shipment'),
    path('drivers/', views.DriversListView.as_view(), name='drivers-list'),
]

urlpatterns += router.urls