from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views, views_driver

app_name = 'accounts'

# Create a router for ViewSets
router = DefaultRouter()
router.register('users', views.UserViewSet)

urlpatterns = [
    # Include router URLs
    path('', include(router.urls)),
    path('signup/', views.SignUpView.as_view(), name='signup'),
    path('user-countries/', views.UserCountryView.as_view(), name='user-countries'),
    path('contact/', views.ContactView.as_view(), name='contact'),
    
    # Driver panel endpoints
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
    path('stores/', views.StoresView.as_view(), name='stores'),
    path('check-staff-user/', views.CheckStaffUserView.as_view(), name='check-staff-user'),
] 