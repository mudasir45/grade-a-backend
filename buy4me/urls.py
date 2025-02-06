from rest_framework_nested import routers
from django.urls import path, include
from . import views

router = routers.DefaultRouter()
router.register('requests', views.Buy4MeRequestViewSet, basename='buy4me-request')

requests_router = routers.NestedDefaultRouter(router, 'requests', lookup='request')
requests_router.register('items', views.Buy4MeItemViewSet, basename='buy4me-item')

app_name = 'buy4me'

urlpatterns = [
    path('', include(router.urls)),
    path('', include(requests_router.urls)),
] 