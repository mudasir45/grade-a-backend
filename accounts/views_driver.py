from decimal import Decimal

from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import DeliveryCommission, DriverProfile
from accounts.permissions import IsDriver, IsDriverForShipment, IsDriverOrStaff
from accounts.serializers import (DeliveryCommissionSerializer,
                                  DriverProfileSerializer)
from buy4me.models import Buy4MeRequest
from buy4me.serializers import Buy4MeRequestSerializer
from shipments.models import ShipmentRequest, ShipmentStatusLocation
from shipments.permissions import IsStaffUser
from shipments.serializers import (ShipmentRequestSerializer,
                                   ShipmentStatusLocationSerializer)


@extend_schema(tags=['driver'])
class DriverDashboardView(APIView):
    """
    View to get driver dashboard information
    """
    permission_classes = [permissions.IsAuthenticated, IsDriver]
    
    @extend_schema(
        summary="Get driver dashboard",
        description="Get driver dashboard information including stats and earnings"
    )
    def get(self, request):
        """Get driver dashboard information"""
        try:
            driver_profile = DriverProfile.objects.get(user=request.user)
        except DriverProfile.DoesNotExist:
            return Response(
                {"error": "Driver profile not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Update driver stats
        driver_profile.update_stats()
        
        # Get pending deliveries
        pending_shipments = ShipmentRequest.objects.filter(
            driver=request.user
        ).exclude(
            status__in=[
                ShipmentRequest.Status.DELIVERED,
                ShipmentRequest.Status.CANCELLED
            ]
        ).count()
        
        pending_buy4me = Buy4MeRequest.objects.filter(
            driver=request.user
        ).exclude(
            status__in=[
                Buy4MeRequest.Status.COMPLETED,
                Buy4MeRequest.Status.CANCELLED
            ]
        ).count()
        
        # Get earnings data
        today = timezone.now().date()
        earnings_today = DeliveryCommission.objects.filter(
            driver=driver_profile,
            earned_at__date=today
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Get last 5 commissions
        recent_commissions = DeliveryCommission.objects.filter(
            driver=driver_profile
        ).order_by('-earned_at')[:5]
        commission_serializer = DeliveryCommissionSerializer(
            recent_commissions,
            many=True
        )
        
        return Response({
            'driver_profile': DriverProfileSerializer(driver_profile).data,
            'pending_deliveries': {
                'shipments': pending_shipments,
                'buy4me': pending_buy4me,
                'total': pending_shipments + pending_buy4me
            },
            'earnings_today': earnings_today,
            'recent_commissions': commission_serializer.data
        })


@extend_schema(tags=['driver'])
class DriverShipmentList(generics.ListAPIView):
    """
    View to list shipments assigned to a driver
    """
    serializer_class = ShipmentRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsDriver]
    
    def get_queryset(self):
        """Get shipments assigned to the driver"""
        user = self.request.user
        queryset = ShipmentRequest.objects.filter(driver=user)
        
        # Filter by status if provided
        status_param = self.request.GET.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
        
        # Filter out delivered/cancelled if param provided
        active_only = self.request.GET.get('active_only')
        if active_only and active_only.lower() == 'true':
            queryset = queryset.exclude(
                status__in=[
                    ShipmentRequest.Status.DELIVERED,
                    ShipmentRequest.Status.CANCELLED
                ]
            )
        
        return queryset.order_by('-created_at')


@extend_schema(tags=['driver'])
class DriverBuy4MeList(generics.ListAPIView):
    """
    View to list Buy4Me requests assigned to a driver
    """
    serializer_class = Buy4MeRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsDriver]
    
    def get_queryset(self):
        """Get Buy4Me requests assigned to the driver"""
        user = self.request.user
        queryset = Buy4MeRequest.objects.filter(driver=user)
        
        # Filter by status if provided
        status_param = self.request.GET.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
        
        # Filter out completed/cancelled if param provided
        active_only = self.request.GET.get('active_only')
        if active_only and active_only.lower() == 'true':
            queryset = queryset.exclude(
                status__in=[
                    Buy4MeRequest.Status.COMPLETED,
                    Buy4MeRequest.Status.CANCELLED
                ]
            )
        
        return queryset.order_by('-created_at')


@extend_schema(tags=['driver'])
class DriverShipmentStatusUpdateView(APIView):
    """
    View for drivers to update shipment status using available status locations.
    Only the assigned driver can update the shipment status.
    """
    permission_classes = [permissions.IsAuthenticated, IsDriver, IsDriverForShipment]
    
    def get_shipment(self, shipment_id):
        """Get shipment and check permissions"""
        shipment = get_object_or_404(
            ShipmentRequest.objects.select_related(
                'user', 'staff', 'service_type'
            ),
            pk=shipment_id
        )
        self.check_object_permissions(self.request, shipment)
        return shipment
    
    @extend_schema(
        summary="Get shipment status options",
        description="Get available status locations for a specific shipment"
    )
    def get(self, request, shipment_id):
        """Get available status locations for a shipment"""
        shipment = self.get_shipment(shipment_id)
        
        # Get status locations filtered by status type if provided
        locations = ShipmentStatusLocation.objects.filter(is_active=True)
        status_type = request.GET.get('status_type')
        
        if status_type:
            locations = locations.filter(status_type=status_type)
            
        # Order by display_order
        locations = locations.order_by('display_order', 'status_type')
        
        serializer = ShipmentStatusLocationSerializer(locations, many=True)
        
        return Response({
            'shipment': {
                'id': shipment.id,
                'tracking_number': shipment.tracking_number,
                'current_status': shipment.status,
                'current_location': shipment.current_location
            },
            'available_status_locations': serializer.data
        })
    
    @extend_schema(
        summary="Update shipment status",
        description="Update the status of a shipment",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'status_location_id': {
                        'type': 'integer',
                        'description': 'ID of the status location to use'
                    },
                    'custom_description': {
                        'type': 'string',
                        'description': 'Optional custom description'
                    }
                },
                'required': ['status_location_id']
            }
        }
    )
    def post(self, request, shipment_id):
        """Update shipment status"""
        shipment = self.get_shipment(shipment_id)
        
        # Get the status location
        status_location_id = request.data.get('status_location_id')
        if not status_location_id:
            return Response(
                {"error": "status_location_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            status_location = ShipmentStatusLocation.objects.get(
                id=status_location_id, is_active=True
            )
        except ShipmentStatusLocation.DoesNotExist:
            return Response(
                {"error": "Status location not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get custom description if provided
        custom_description = request.data.get('custom_description')
        
        # Update shipment status
        old_status = shipment.status
        shipment.status = status_location.status_type
        shipment.current_location = status_location.location_name
        
        # Add tracking history entry
        description = custom_description or status_location.description
        shipment.tracking_history.append({
            'status': status_location.status_type,
            'location': status_location.location_name,
            'timestamp': timezone.now().isoformat(),
            'description': description,
            'updated_by': request.user.username,
            'staff_id': request.user.id
        })
        
        # Save the shipment
        shipment.save()
        
        # If status changed to DELIVERED, create a commission
        if old_status != ShipmentRequest.Status.DELIVERED and shipment.status == ShipmentRequest.Status.DELIVERED:
            try:
                driver_profile = DriverProfile.objects.get(user=request.user)
                
                # Calculate commission based on shipment value and commission rate
                commission_amount = (shipment.total_cost * driver_profile.commission_rate) / Decimal('100.00')
                
                # Create the commission record
                DeliveryCommission.objects.create(
                    driver=driver_profile,
                    delivery_type=DeliveryCommission.DeliveryType.SHIPMENT,
                    reference_id=shipment.tracking_number,
                    amount=commission_amount,
                    description=f"Delivery commission for shipment {shipment.tracking_number}"
                )
                
                # Update driver stats
                driver_profile.update_stats()
                
            except DriverProfile.DoesNotExist:
                # Log error but don't fail the update
                print(f"Error: Driver profile not found for user {request.user.id}")
        
        # Return the updated shipment
        return Response({
            'shipment': ShipmentRequestSerializer(shipment).data,
            'message': "Shipment status updated successfully"
        })


@extend_schema(tags=['driver'])
class DriverBuy4MeStatusUpdateView(APIView):
    """
    View for drivers to update Buy4Me request status.
    Only the assigned driver can update the request status.
    """
    permission_classes = [permissions.IsAuthenticated, IsDriver]
    
    def get_buy4me_request(self, request_id):
        """Get Buy4Me request and check permissions"""
        buy4me_request = get_object_or_404(
            Buy4MeRequest.objects.select_related('user', 'driver'),
            pk=request_id
        )
        
        # Check if current user is assigned to this request
        if not buy4me_request.driver or str(buy4me_request.driver.pk) != str(self.request.user.pk):
            raise PermissionDenied("You are not authorized to update this request")
            
        return buy4me_request
    
    @extend_schema(
        summary="Update Buy4Me request status",
        description="Update the status of a Buy4Me request",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'status': {
                        'type': 'string',
                        'description': 'New status for the request'
                    },
                    'notes': {
                        'type': 'string',
                        'description': 'Optional notes about the status update'
                    }
                },
                'required': ['status']
            }
        }
    )
    def post(self, request, request_id):
        """Update Buy4Me request status"""
        buy4me_request = self.get_buy4me_request(request_id)
        
        # Get the new status
        new_status = request.data.get('status')
        if not new_status:
            return Response(
                {"error": "status is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate the status
        if new_status not in dict(Buy4MeRequest.Status.choices):
            return Response(
                {"error": "Invalid status"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update request status
        old_status = buy4me_request.status
        buy4me_request.status = new_status
        
        # Add notes if provided
        notes = request.data.get('notes')
        if notes:
            if buy4me_request.notes:
                buy4me_request.notes += f"\n\n{timezone.now().strftime('%Y-%m-%d %H:%M')} - Status updated to {new_status} by {request.user.username}: {notes}"
            else:
                buy4me_request.notes = f"{timezone.now().strftime('%Y-%m-%d %H:%M')} - Status updated to {new_status} by {request.user.username}: {notes}"
        
        # Save the request
        buy4me_request.save()
        
        # If status changed to COMPLETED, create a commission
        if old_status != Buy4MeRequest.Status.COMPLETED and new_status == Buy4MeRequest.Status.COMPLETED:
            try:
                driver_profile = DriverProfile.objects.get(user=request.user)
                
                # Calculate commission based on request value and commission rate
                commission_amount = (buy4me_request.total_cost * driver_profile.commission_rate) / Decimal('100.00')
                
                # Create the commission record
                DeliveryCommission.objects.create(
                    driver=driver_profile,
                    delivery_type=DeliveryCommission.DeliveryType.BUY4ME,
                    reference_id=str(buy4me_request.pk),
                    amount=commission_amount,
                    description=f"Commission for Buy4Me request {buy4me_request.pk}"
                )
                
                # Update driver stats
                driver_profile.update_stats()
                
            except DriverProfile.DoesNotExist:
                # Log error but don't fail the update
                print(f"Error: Driver profile not found for user {request.user.pk}")
        
        # Return the updated request
        return Response({
            'buy4me_request': Buy4MeRequestSerializer(buy4me_request).data,
            'message': "Buy4Me request status updated successfully"
        })


@extend_schema(tags=['driver'])
class DriverEarningsView(APIView):
    """
    View to get driver earnings information
    """
    permission_classes = [permissions.IsAuthenticated, IsDriver]
    
    @extend_schema(
        summary="Get driver earnings",
        description="Get driver earnings information",
        parameters=[
            OpenApiParameter(
                name='start_date',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Start date for filtering earnings (YYYY-MM-DD)'
            ),
            OpenApiParameter(
                name='end_date',
                type=str,
                location=OpenApiParameter.QUERY,
                description='End date for filtering earnings (YYYY-MM-DD)'
            )
        ]
    )
    def get(self, request):
        """Get driver earnings information"""
        try:
            driver_profile = DriverProfile.objects.get(user=request.user)
        except DriverProfile.DoesNotExist:
            return Response(
                {"error": "Driver profile not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Parse date filters if provided
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        
        # Query conditions
        query_conditions = {'driver': driver_profile}
        
        if start_date_str:
            try:
                start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d')
                start_date = timezone.make_aware(start_date)
                query_conditions['earned_at__gte'] = start_date
            except ValueError:
                return Response(
                    {"error": "Invalid start_date format. Use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if end_date_str:
            try:
                end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d')
                end_date = timezone.make_aware(end_date) + timezone.timedelta(days=1)
                query_conditions['earned_at__lt'] = end_date
            except ValueError:
                return Response(
                    {"error": "Invalid end_date format. Use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Get commissions
        commissions = DeliveryCommission.objects.filter(**query_conditions).order_by('-earned_at')
        
        # Calculate totals
        total_earnings = commissions.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Get earnings by type
        shipment_earnings = commissions.filter(
            delivery_type=DeliveryCommission.DeliveryType.SHIPMENT
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        buy4me_earnings = commissions.filter(
            delivery_type=DeliveryCommission.DeliveryType.BUY4ME
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Serialize commissions
        commission_serializer = DeliveryCommissionSerializer(commissions, many=True)
        
        return Response({
            'total_earnings': total_earnings,
            'shipment_earnings': shipment_earnings,
            'buy4me_earnings': buy4me_earnings,
            'commissions': commission_serializer.data
        }) 
        
