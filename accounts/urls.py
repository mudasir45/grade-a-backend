from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('users', views.UserViewSet)

app_name = 'accounts'

urlpatterns = [
    path('', include(router.urls)),
    path('signup/', views.SignUpView.as_view(), name='signup'),
    path('user-countries/', views.UserCountryView.as_view(), name='user-countries'),
    path('contact/', views.ContactView.as_view(), name='contact'),
] 