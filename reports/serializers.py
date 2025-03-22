from rest_framework import serializers


class OverviewStatsSerializer(serializers.Serializer):
    total_users = serializers.IntegerField()
    total_shipments = serializers.IntegerField()
    total_buy4me_requests = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    pending_shipments = serializers.IntegerField()
    pending_buy4me_requests = serializers.IntegerField()
    active_users = serializers.IntegerField()

class UserBreakdownSerializer(serializers.Serializer):
    walk_in_users = serializers.IntegerField()
    buy4me_users = serializers.IntegerField()
    drivers = serializers.IntegerField()
    admins = serializers.IntegerField()
    users_by_country = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField(),
            allow_empty=True
        )
    )
    user_growth = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField(),
            allow_empty=True
        )
    )

class ShipmentAnalyticsSerializer(serializers.Serializer):
    shipments_by_status = serializers.DictField(
        child=serializers.IntegerField()
    )
    shipments_by_month = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField(),
            allow_empty=True
        )
    )
    avg_delivery_time = serializers.FloatField()
    total_shipment_value = serializers.DecimalField(max_digits=12, decimal_places=2)
    popular_destinations = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField(),
            allow_empty=True
        )
    )
    shipment_weight_distribution = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField(),
            allow_empty=True
        )
    )

class Buy4MeAnalyticsSerializer(serializers.Serializer):
    requests_by_status = serializers.DictField(
        child=serializers.IntegerField()
    )
    requests_by_month = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField(),
            allow_empty=True
        )
    )
    avg_processing_time = serializers.FloatField()
    total_buy4me_value = serializers.DecimalField(max_digits=12, decimal_places=2)
    popular_items = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField(),
            allow_empty=True
        )
    )

class RevenueAnalyticsSerializer(serializers.Serializer):
    revenue_by_month = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField(),
            allow_empty=True
        )
    )
    revenue_by_service = serializers.DictField(
        child=serializers.DecimalField(max_digits=12, decimal_places=2)
    )
    payment_method_distribution = serializers.DictField(
        child=serializers.IntegerField()
    )
    average_order_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    refund_rate = serializers.FloatField()

class DriverAnalyticsSerializer(serializers.Serializer):
    top_drivers = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField(),
            allow_empty=True
        )
    )
    deliveries_by_driver = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField(),
            allow_empty=True
        )
    )
    driver_earnings = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField(),
            allow_empty=True
        )
    )
    driver_performance = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField(),
            allow_empty=True
        )
    )

class SupportAnalyticsSerializer(serializers.Serializer):
    tickets_by_status = serializers.DictField(
        child=serializers.IntegerField()
    )
    tickets_by_category = serializers.DictField(
        child=serializers.IntegerField()
    )
    avg_resolution_time = serializers.FloatField()
    open_tickets_count = serializers.IntegerField() 