from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import (Avg, Count, DurationField, ExpressionWrapper, F,
                              Q, Sum)
from django.db.models.functions import ExtractMonth, TruncDate, TruncMonth
from django.shortcuts import render
from django.utils import timezone
from rest_framework import permissions, status, views
from rest_framework.response import Response

from accounts.models import Contact, DeliveryCommission, DriverProfile, User
from buy4me.models import Buy4MeItem, Buy4MeRequest
from payments.models import Invoice, Payment, Refund
from shipments.models import ShipmentRequest, SupportTicket

from .serializers import (Buy4MeAnalyticsSerializer, DriverAnalyticsSerializer,
                          OverviewStatsSerializer, RevenueAnalyticsSerializer,
                          ShipmentAnalyticsSerializer,
                          SupportAnalyticsSerializer, UserBreakdownSerializer)


class OverviewStatsView(views.APIView):
    """
    Get overview metrics for the admin dashboard
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        # Calculate date ranges
        today = timezone.now().date()
        thirty_days_ago = today - timedelta(days=30)

        # Get total users, shipments, buy4me requests
        total_users = User.objects.count()
        total_shipments = ShipmentRequest.objects.count()
        total_buy4me_requests = Buy4MeRequest.objects.count()

        # Get active users in last 30 days
        active_users = User.objects.filter(last_login__gte=thirty_days_ago).count()

        # Get pending shipments and buy4me requests
        pending_shipments = ShipmentRequest.objects.filter(
            status=ShipmentRequest.Status.PENDING
        ).count()
        pending_buy4me_requests = Buy4MeRequest.objects.filter(
            status=Buy4MeRequest.Status.SUBMITTED
        ).count()

        # Calculate total revenue
        total_revenue = Invoice.objects.filter(
            status=Invoice.Status.PAID
        ).aggregate(
            total=Sum('total')
        )['total'] or Decimal('0.00')

        data = {
            'total_users': total_users,
            'total_shipments': total_shipments,
            'total_buy4me_requests': total_buy4me_requests,
            'total_revenue': total_revenue,
            'pending_shipments': pending_shipments,
            'pending_buy4me_requests': pending_buy4me_requests,
            'active_users': active_users,
        }

        serializer = OverviewStatsSerializer(data)
        return Response(serializer.data)


class UserAnalyticsView(views.APIView):
    """
    Get user-related analytics for the admin dashboard
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        # Count users by type
        walk_in_users = User.objects.filter(user_type=User.UserType.WALK_IN).count()
        buy4me_users = User.objects.filter(user_type=User.UserType.BUY4ME).count()
        drivers = User.objects.filter(user_type=User.UserType.DRIVER).count()
        admins = User.objects.filter(
            Q(user_type=User.UserType.ADMIN) | 
            Q(user_type=User.UserType.SUPER_ADMIN)
        ).count()

        # Get users by country
        users_by_country = list(User.objects.values('country__name').annotate(
            count=Count('id')
        ).order_by('-count').values('country__name', 'count'))
        
        # Format users by country
        users_by_country_formatted = []
        for item in users_by_country:
            if item['country__name']:
                users_by_country_formatted.append({
                    'name': item['country__name'],
                    'value': item['count']
                })

        # Get user growth by month
        current_year = timezone.now().year
        user_growth = list(User.objects.filter(
            created_at__year=current_year
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            count=Count('id')
        ).order_by('month'))
        
        # Format user growth data
        user_growth_formatted = []
        for item in user_growth:
            month_name = item['month'].strftime('%B')
            user_growth_formatted.append({
                'name': month_name,
                'value': item['count']
            })

        data = {
            'walk_in_users': walk_in_users,
            'buy4me_users': buy4me_users,
            'drivers': drivers,
            'admins': admins,
            'users_by_country': users_by_country_formatted,
            'user_growth': user_growth_formatted,
        }

        serializer = UserBreakdownSerializer(data)
        return Response(serializer.data)


class ShipmentAnalyticsView(views.APIView):
    """
    Get shipment-related analytics for the admin dashboard
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        # Get shipments by status
        shipments_by_status = dict(
            ShipmentRequest.objects.values_list('status').annotate(
                count=Count('id')
            )
        )

        # Get shipments by month
        current_year = timezone.now().year
        shipments_by_month = list(ShipmentRequest.objects.filter(
            created_at__year=current_year
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            count=Count('id')
        ).order_by('month'))
        
        # Format shipments by month
        shipments_by_month_formatted = []
        for item in shipments_by_month:
            month_name = item['month'].strftime('%B')
            shipments_by_month_formatted.append({
                'name': month_name,
                'value': item['count']
            })

        # Calculate average delivery time for completed shipments
        # This assumes there's a created_at field when the shipment was created and a delivery date
        delivered_shipments = ShipmentRequest.objects.filter(
            status=ShipmentRequest.Status.DELIVERED
        )
        
        delivery_times = []
        for shipment in delivered_shipments:
            # Look through tracking history for the delivered event
            for event in shipment.tracking_history:
                if event.get('status') == ShipmentRequest.Status.DELIVERED:
                    delivery_date = datetime.fromisoformat(event.get('timestamp').replace('Z', '+00:00'))
                    delivery_days = (delivery_date.date() - shipment.created_at.date()).days
                    if delivery_days >= 0:  # Sanity check
                        delivery_times.append(delivery_days)
                    break
        
        avg_delivery_time = sum(delivery_times) / len(delivery_times) if delivery_times else 0

        # Get total shipment value
        total_shipment_value = ShipmentRequest.objects.aggregate(
            total=Sum('total_cost')
        )['total'] or Decimal('0.00')

        # Get popular destinations
        popular_destinations = list(ShipmentRequest.objects.values(
            'recipient_country__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10].values('recipient_country__name', 'count'))
        
        # Format popular destinations
        popular_destinations_formatted = []
        for item in popular_destinations:
            if item['recipient_country__name']:
                popular_destinations_formatted.append({
                    'name': item['recipient_country__name'],
                    'value': item['count']
                })

        # Get shipment weight distribution
        weight_ranges = [
            {'min': 0, 'max': 1, 'label': 'Under 1kg'},
            {'min': 1, 'max': 5, 'label': '1-5kg'},
            {'min': 5, 'max': 10, 'label': '5-10kg'},
            {'min': 10, 'max': 20, 'label': '10-20kg'},
            {'min': 20, 'max': float('inf'), 'label': 'Over 20kg'}
        ]
        
        weight_distribution = []
        for range_info in weight_ranges:
            if range_info['max'] == float('inf'):
                count = ShipmentRequest.objects.filter(
                    weight__gte=range_info['min']
                ).count()
            else:
                count = ShipmentRequest.objects.filter(
                    weight__gte=range_info['min'],
                    weight__lt=range_info['max']
                ).count()
            
            weight_distribution.append({
                'name': range_info['label'],
                'value': count
            })

        data = {
            'shipments_by_status': shipments_by_status,
            'shipments_by_month': shipments_by_month_formatted,
            'avg_delivery_time': avg_delivery_time,
            'total_shipment_value': total_shipment_value,
            'popular_destinations': popular_destinations_formatted,
            'shipment_weight_distribution': weight_distribution,
        }

        serializer = ShipmentAnalyticsSerializer(data)
        return Response(serializer.data)


class Buy4MeAnalyticsView(views.APIView):
    """
    Get Buy4Me-related analytics for the admin dashboard
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        # Get requests by status
        requests_by_status = dict(
            Buy4MeRequest.objects.values_list('status').annotate(
                count=Count('id')
            )
        )

        # Get requests by month
        current_year = timezone.now().year
        requests_by_month = list(Buy4MeRequest.objects.filter(
            created_at__year=current_year
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            count=Count('id')
        ).order_by('month'))
        
        # Format requests by month
        requests_by_month_formatted = []
        for item in requests_by_month:
            month_name = item['month'].strftime('%B')
            requests_by_month_formatted.append({
                'name': month_name,
                'value': item['count']
            })

        # Calculate average processing time (from SUBMITTED to COMPLETED)
        completed_requests = Buy4MeRequest.objects.filter(
            status=Buy4MeRequest.Status.COMPLETED
        )
        
        total_days = 0
        count = 0
        for request in completed_requests:
            if request.created_at and request.updated_at and request.status == Buy4MeRequest.Status.COMPLETED:
                days = (request.updated_at.date() - request.created_at.date()).days
                if days >= 0:  # Sanity check
                    total_days += days
                    count += 1
        
        avg_processing_time = total_days / count if count > 0 else 0

        # Get total Buy4Me value
        total_buy4me_value = Buy4MeRequest.objects.aggregate(
            total=Sum('total_cost')
        )['total'] or Decimal('0.00')

        # Get popular items
        # This creates a dictionary of item names and their counts
        buy4me_items = Buy4MeItem.objects.values('product_name')
        item_counts = {}
        for item in buy4me_items:
            name = item['product_name']
            if name in item_counts:
                item_counts[name] += 1
            else:
                item_counts[name] = 1
        
        # Convert to list of dictionaries and sort by count
        popular_items = [{'name': k, 'value': v} for k, v in item_counts.items()]
        popular_items.sort(key=lambda x: x['value'], reverse=True)
        popular_items = popular_items[:10]  # Take top 10

        data = {
            'requests_by_status': requests_by_status,
            'requests_by_month': requests_by_month_formatted,
            'avg_processing_time': avg_processing_time,
            'total_buy4me_value': total_buy4me_value,
            'popular_items': popular_items,
        }

        serializer = Buy4MeAnalyticsSerializer(data)
        return Response(serializer.data)


class RevenueAnalyticsView(views.APIView):
    """
    Get revenue-related analytics for the admin dashboard
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        # Get revenue by month
        current_year = timezone.now().year
        revenue_by_month = list(Invoice.objects.filter(
            status=Invoice.Status.PAID,
            created_at__year=current_year
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            total=Sum('total')
        ).order_by('month'))
        
        # Format revenue by month
        revenue_by_month_formatted = []
        for item in revenue_by_month:
            month_name = item['month'].strftime('%B')
            revenue_by_month_formatted.append({
                'name': month_name,
                'value': float(item['total'])
            })

        # Get revenue by service (Shipment vs Buy4Me)
        shipment_revenue = Invoice.objects.filter(
            status=Invoice.Status.PAID,
            shipment__isnull=False
        ).aggregate(
            total=Sum('total')
        )['total'] or Decimal('0.00')
        
        buy4me_revenue = Invoice.objects.filter(
            status=Invoice.Status.PAID,
            buy4me_request__isnull=False
        ).aggregate(
            total=Sum('total')
        )['total'] or Decimal('0.00')
        
        revenue_by_service = {
            'Shipment': shipment_revenue,
            'Buy4Me': buy4me_revenue
        }

        # Get payment method distribution
        payment_method_distribution = dict(
            Payment.objects.filter(
                status=Payment.Status.COMPLETED
            ).values_list('payment_method').annotate(
                count=Count('id')
            )
        )

        # Calculate average order value
        total_orders = Invoice.objects.filter(status=Invoice.Status.PAID).count()
        total_revenue = Invoice.objects.filter(
            status=Invoice.Status.PAID
        ).aggregate(
            total=Sum('total')
        )['total'] or Decimal('0.00')
        
        average_order_value = total_revenue / total_orders if total_orders > 0 else Decimal('0.00')

        # Calculate refund rate
        total_payments = Payment.objects.filter(status=Payment.Status.COMPLETED).count()
        total_refunds = Refund.objects.filter(status=Refund.Status.COMPLETED).count()
        
        refund_rate = (total_refunds / total_payments * 100) if total_payments > 0 else 0

        data = {
            'revenue_by_month': revenue_by_month_formatted,
            'revenue_by_service': revenue_by_service,
            'payment_method_distribution': payment_method_distribution,
            'average_order_value': average_order_value,
            'refund_rate': refund_rate,
        }

        serializer = RevenueAnalyticsSerializer(data)
        return Response(serializer.data)


class DriverAnalyticsView(views.APIView):
    """
    Get driver-related analytics for the admin dashboard
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        # Get top drivers by completed deliveries
        top_drivers = list(DriverProfile.objects.order_by('-total_deliveries')[:10].values(
            'user__id', 'user__first_name', 'user__last_name', 'total_deliveries', 'total_earnings'
        ))
        
        # Format top drivers
        top_drivers_formatted = []
        for driver in top_drivers:
            name = f"{driver['user__first_name']} {driver['user__last_name']}"
            top_drivers_formatted.append({
                'id': driver['user__id'],
                'name': name,
                'deliveries': driver['total_deliveries'],
                'earnings': float(driver['total_earnings'])
            })

        # Get deliveries by driver
        deliveries_by_driver = list(ShipmentRequest.objects.filter(
            status=ShipmentRequest.Status.DELIVERED,
            driver__isnull=False
        ).values('driver__id').annotate(
            count=Count('id')
        ).order_by('-count')[:10])
        
        # Format deliveries by driver
        deliveries_by_driver_formatted = []
        for item in deliveries_by_driver:
            try:
                driver = User.objects.get(id=item['driver__id'])
                name = f"{driver.first_name} {driver.last_name}" if driver.first_name else driver.username
                deliveries_by_driver_formatted.append({
                    'id': driver.id,
                    'name': name,
                    'value': item['count']
                })
            except User.DoesNotExist:
                pass

        # Get driver earnings
        driver_earnings = list(DeliveryCommission.objects.values('driver__user__id').annotate(
            total=Sum('amount')
        ).order_by('-total')[:10])
        
        # Format driver earnings
        driver_earnings_formatted = []
        for item in driver_earnings:
            try:
                driver = User.objects.get(id=item['driver__user__id'])
                name = f"{driver.first_name} {driver.last_name}" if driver.first_name else driver.username
                driver_earnings_formatted.append({
                    'id': driver.id,
                    'name': name,
                    'value': float(item['total'])
                })
            except User.DoesNotExist:
                pass

        # Calculate driver performance (on-time deliveries)
        driver_performance = []
        drivers = DriverProfile.objects.all()
        
        for driver_profile in drivers:
            total_deliveries = ShipmentRequest.objects.filter(
                driver=driver_profile.user,
                status=ShipmentRequest.Status.DELIVERED
            ).count()
            
            on_time_deliveries = 0
            for shipment in ShipmentRequest.objects.filter(
                driver=driver_profile.user,
                status=ShipmentRequest.Status.DELIVERED,
                estimated_delivery__isnull=False
            ):
                # Get actual delivery date from tracking history
                for event in shipment.tracking_history:
                    if event.get('status') == ShipmentRequest.Status.DELIVERED:
                        delivery_date = datetime.fromisoformat(event.get('timestamp').replace('Z', '+00:00'))
                        if delivery_date <= shipment.estimated_delivery:
                            on_time_deliveries += 1
                        break
            
            on_time_percentage = (on_time_deliveries / total_deliveries * 100) if total_deliveries > 0 else 0
            
            driver_performance.append({
                'id': driver_profile.user.id,
                'name': f"{driver_profile.user.first_name} {driver_profile.user.last_name}",
                'total_deliveries': total_deliveries,
                'on_time_deliveries': on_time_deliveries,
                'on_time_percentage': on_time_percentage
            })
        
        # Sort by on-time percentage
        driver_performance.sort(key=lambda x: x['on_time_percentage'], reverse=True)
        driver_performance = driver_performance[:10]

        data = {
            'top_drivers': top_drivers_formatted,
            'deliveries_by_driver': deliveries_by_driver_formatted,
            'driver_earnings': driver_earnings_formatted,
            'driver_performance': driver_performance,
        }

        serializer = DriverAnalyticsSerializer(data)
        return Response(serializer.data)


class SupportAnalyticsView(views.APIView):
    """
    Get support-related analytics for the admin dashboard
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        # Get tickets by status
        tickets_by_status = dict(
            SupportTicket.objects.values_list('status').annotate(
                count=Count('id')
            )
        )

        # Get tickets by category
        tickets_by_category = dict(
            SupportTicket.objects.values_list('category').annotate(
                count=Count('id')
            )
        )

        # Calculate average resolution time
        resolved_tickets = SupportTicket.objects.filter(
            status=SupportTicket.Status.RESOLVED,
            resolved_at__isnull=False
        )
        
        total_hours = 0
        count = 0
        for ticket in resolved_tickets:
            if ticket.created_at and ticket.resolved_at:
                hours = (ticket.resolved_at - ticket.created_at).total_seconds() / 3600
                if hours >= 0:  # Sanity check
                    total_hours += hours
                    count += 1
        
        avg_resolution_time = total_hours / count if count > 0 else 0

        # Count open tickets
        open_tickets_count = SupportTicket.objects.filter(
            status__in=[SupportTicket.Status.OPEN, SupportTicket.Status.IN_PROGRESS]
        ).count()

        data = {
            'tickets_by_status': tickets_by_status,
            'tickets_by_category': tickets_by_category,
            'avg_resolution_time': avg_resolution_time,
            'open_tickets_count': open_tickets_count,
        }

        serializer = SupportAnalyticsSerializer(data)
        return Response(serializer.data)
