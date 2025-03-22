from django.urls import path

from .views import (Buy4MeAnalyticsView, DriverAnalyticsView,
                    OverviewStatsView, RevenueAnalyticsView,
                    ShipmentAnalyticsView, SupportAnalyticsView,
                    UserAnalyticsView)

app_name = 'reports'

urlpatterns = [
    # Overview and summary endpoints
    path('analytics/overview/', OverviewStatsView.as_view(), name='overview_stats'),
    path('analytics/users/', UserAnalyticsView.as_view(), name='user_analytics'),
    path('analytics/shipments/', ShipmentAnalyticsView.as_view(), name='shipment_analytics'),
    path('analytics/buy4me/', Buy4MeAnalyticsView.as_view(), name='buy4me_analytics'),
    path('analytics/revenue/', RevenueAnalyticsView.as_view(), name='revenue_analytics'),
    path('analytics/drivers/', DriverAnalyticsView.as_view(), name='driver_analytics'),
    path('analytics/support/', SupportAnalyticsView.as_view(), name='support_analytics'),
] 