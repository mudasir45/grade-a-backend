import io
import os
import string
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Count, Prefetch, Q, Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django_filters import rest_framework as filters
from drf_spectacular.utils import OpenApiParameter, extend_schema
from reportlab.graphics.barcode import code128
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User

from .models import (ShipmentExtras, ShipmentMessageTemplate, ShipmentPackage,
                     ShipmentRequest, ShipmentStatusLocation, SupportTicket)
from .permissions import IsStaffUser
from .serializers import (ShipmentCreateSerializer, ShipmentMessageSerializer,
                          ShipmentRequestSerializer,
                          ShipmentStatusLocationSerializer,
                          StatusUpdateSerializer, SupportTicketSerializer,
                          UserSerializer)
from .utils import calculate_shipping_cost

# Create your views here.

@extend_schema(tags=['shipments'])
class ShipmentListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        summary="List user's shipments",
        description="Get a list of all shipments for the authenticated user"
    )
    def get(self, request):
        """Get all shipments for the current user"""
        shipments = ShipmentRequest.objects.filter(
            user=request.user
        ).select_related(
            'sender_country',
            'recipient_country',
            'service_type'
        ).order_by('-created_at')
        
        serializer = ShipmentRequestSerializer(shipments, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Create shipment",
        description="Create a new shipment request",
        request=ShipmentCreateSerializer
    )
    def post(self, request):
        """Create a new shipment request"""
        serializer = ShipmentCreateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(tags=['shipments'])
class ShipmentDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self, pk):
        return get_object_or_404(
            ShipmentRequest.objects.select_related(
                'sender_country',
                'recipient_country',
                'service_type'
            ),
            pk=pk,
            user=self.request.user
        )
    
    @extend_schema(
        summary="Get shipment details",
        description="Get detailed information about a specific shipment"
    )
    def get(self, request, pk):
        """Get details of a specific shipment"""
        shipment = self.get_object(pk)
        serializer = ShipmentRequestSerializer(shipment)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Update shipment",
        description="Update a shipment request (only certain fields)"
    )
    def patch(self, request, pk):
        """Update specific fields of a shipment"""
        shipment = self.get_object(pk)
        
        # Make a copy of the request data
        data = request.data.copy()
        
        # Calculate shipping cost if relevant fields are updated
        recalculate_prices = any(field in data for field in [
            'weight', 'length', 'width', 'height', 'sender_country', 
            'recipient_country', 'service_type', 'city', 'additional_charges'
        ])
        
        if recalculate_prices:
            # Prepare dimensions if they exist
            dimensions = None
            if all(key in data for key in ['length', 'width', 'height']):
                dimensions = {
                    'length': data.get('length', shipment.length),
                    'width': data.get('width', shipment.width),
                    'height': data.get('height', shipment.height)
                }
            elif all(hasattr(shipment, key) for key in ['length', 'width', 'height']):
                dimensions = {
                    'length': shipment.length,
                    'width': shipment.width,
                    'height': shipment.height
                }
            
            # Extract extras data from request if provided
            extras_data = data.get('additional_charges', None)
            
            # Get current values for fields not in the request data
            sender_country_id = data.get('sender_country', shipment.sender_country_id)
            recipient_country_id = data.get('recipient_country', shipment.recipient_country_id)
            service_type_id = data.get('service_type', shipment.service_type_id)
            weight = data.get('weight', shipment.weight)
            city_id = data.get('city', shipment.city_id if shipment.city else None)
            
            # Calculate shipping cost
            cost_breakdown = calculate_shipping_cost(
                sender_country_id=sender_country_id,
                recipient_country_id=recipient_country_id,
                service_type_id=service_type_id,
                weight=weight,
                dimensions=dimensions,
                city_id=city_id,
                extras_data=extras_data
            )
            
            # Check for errors
            if cost_breakdown['errors']:
                return Response(
                    {'errors': cost_breakdown['errors']},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update data with calculated values
            data['weight_charge'] = cost_breakdown['weight_charge']
            data['service_charge'] = cost_breakdown['service_price']
            data['delivery_charge'] = cost_breakdown['city_delivery_charge']
            data['per_kg_rate'] = cost_breakdown.get('per_kg_rate', 0)
            
            # Calculate total_additional_charges from cost_breakdown
            total_additional = Decimal('0.00')
            for charge in cost_breakdown['additional_charges']:
                total_additional += Decimal(str(charge['amount']))
            data['total_additional_charges'] = total_additional
            
            # Calculate extras_charges
            if 'extras_total' in cost_breakdown:
                data['extras_charges'] = cost_breakdown['extras_total']
            
            # Set total cost
            data['total_cost'] = cost_breakdown['total_cost']
            
            # Add the cost breakdown to the data for processing by the serializer
            data['cost_breakdown'] = cost_breakdown
        
        # Update serializer with processed data
        serializer = ShipmentRequestSerializer(
            shipment,
            data=data,
            partial=True
        )
        
        if serializer.is_valid():
            updated_shipment = serializer.save()
            
            # Explicitly regenerate the receipt to ensure it's updated
            updated_shipment.regenerate_receipt()
            
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(tags=['shipments'])
class ShipmentTrackingView(APIView):
    """
    View for tracking shipment status and history
    Can be accessed by tracking number without authentication
    """
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(
        summary="Track shipment",
        description="Get tracking information for a shipment using tracking number",
        parameters=[
            OpenApiParameter(
                name='tracking_number',
                type=str,
                location=OpenApiParameter.PATH,
                description='Shipment tracking number'
            )
        ]
    )
    def get(self, request, tracking_number):
        print(tracking_number)
        try:
            shipment = ShipmentRequest.objects.prefetch_related('packages').get(
                tracking_number=tracking_number
            )
            
            # Get packages information
            packages_data = []
            for package in shipment.packages.all().order_by('id'):
                package_data = {
                    'id': package.id,
                    'number': package.number,
                    'package_type': package.package_type,
                    'status': package.status,
                    'status_display': dict(ShipmentPackage.Status.choices)[package.status],
                    'tracking_history': [
                        {
                            'status': update.get('status', ''),
                            'location': update.get('location', ''),
                            'timestamp': update.get('timestamp', ''),
                            'description': update.get('description', '')
                        }
                        for update in reversed(package.tracking_history)
                    ] if package.tracking_history else []
                }
                packages_data.append(package_data)
            
            response_data = {
                'tracking_number': shipment.tracking_number,
                'status': shipment.get_status_display(),
                'current_location': shipment.current_location,
                'estimated_delivery': (
                    shipment.estimated_delivery.isoformat() 
                    if shipment.estimated_delivery 
                    else None
                ),
                'shipment_details': {
                    'origin': {
                        'name': shipment.sender_name,
                        'country': shipment.sender_country.name
                    },
                    'destination': {
                        'name': shipment.recipient_name,
                        'country': shipment.recipient_country.name
                    },
                    'service': shipment.service_type.name,
                    'package': {
                        'weight': float(shipment.weight),
                        'dimensions': {
                            'length': float(shipment.length),
                            'width': float(shipment.width),
                            'height': float(shipment.height)
                        }
                    },
                    'no_of_packages': shipment.no_of_packages
                },
                'packages': packages_data,
                'tracking_history': [
                    {
                        'status': update.get('status', ''),
                        'location': update.get('location', ''),
                        'timestamp': update.get('timestamp', ''),
                        'description': update.get('description', '')
                    }
                    for update in reversed(shipment.tracking_history)
                ] if shipment.tracking_history else []
            }
            
            return Response(response_data)
            
        except ShipmentRequest.DoesNotExist:
            return Response(
                {'error': 'Invalid tracking number'},
                status=status.HTTP_404_NOT_FOUND
            )

@extend_schema(tags=['shipments'])
class ShipmentRequestViewSet(viewsets.ModelViewSet):
    serializer_class = ShipmentRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Optimize queryset with prefetch_related for tracking updates
        Filter shipments based on user role
        """
        queryset = ShipmentRequest.objects.prefetch_related(
            'tracking_updates',
            'sender_country',
            'recipient_country',
            'service_type'
        )
        
        user = self.request.user
        if not user.is_staff:
            queryset = queryset.filter(user=user)
        
        return queryset.order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'create':
            return ShipmentCreateSerializer
        return ShipmentRequestSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def calculate_shipping_cost(self, data):
        # Add your shipping cost calculation logic here
        # This is a placeholder implementation
        base_cost = 10.00
        weight_cost = float(data['weight']) * 2
        return base_cost + weight_cost

    @extend_schema(
        summary="Add tracking update",
        description="Add a new tracking update to the shipment"
    )
    # @action(detail=True, methods=['post'])
    # def add_tracking(self, request, pk=None):
    #     shipment = self.get_object()
    #     serializer = ShipmentTrackingSerializer(data=request.data)
        
    #     if serializer.is_valid():
    #         serializer.save(shipment=shipment)
    #         return Response(serializer.data, status=status.HTTP_201_CREATED)
    #     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Update shipment status",
        description="Update the status of a shipment"
    )
    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        instance = self.get_object()
        new_status = request.data.get('status')
        
        if new_status not in dict(ShipmentRequest.Status.choices):
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )

        instance.status = new_status
        instance.save()
        return Response(self.get_serializer(instance).data)

    @extend_schema(
        summary="Download receipt",
        description="Regenerate and download the latest receipt for a shipment"
    )
    @action(detail=True, methods=['get'])
    def receipt(self, request, pk=None):
        """
        Regenerate and return the receipt URL for a shipment.
        This ensures the receipt always contains the latest data.
        """
        instance = self.get_object()
        
        # Force regenerate the receipt to ensure it contains the latest data
        instance.regenerate_receipt()
        
        if instance.receipt:
            return Response({
                'receipt_url': request.build_absolute_uri(instance.receipt.url),
                'message': 'Receipt regenerated successfully'
            })
        else:
            return Response(
                {'error': 'Receipt generation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class LastShipmentView(APIView):
    """
    View for getting the last shipment data for a user
    """
    permission_classes = [permissions.AllowAny]  
    
    def get(self, request, user_id=None):
        """Get the last shipment for a specific user using GET"""
        # If user_id is not in the URL path, try to get it from query parameters
        if not user_id:
            user_id = request.query_params.get('user_id')
            
        print("user_id", user_id)
        
        if not user_id:
            return Response(
                {'error': 'user_id is required as a URL parameter or query parameter'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            # Get the most recent shipment for the user
            shipment = ShipmentRequest.objects.filter(
                user__id=user_id
            ).order_by('-created_at').first()
            
            print("shipment", shipment)

            if not shipment:
                user = User.objects.get(id=user_id)
                response = {
                    "sender_name": user.first_name + " " + user.last_name,
                    "sender_email": user.email,
                    "sender_phone": user.phone_number,
                    "sender_address": user.address,
                }
                return Response(response)
            
            serializer = ShipmentRequestSerializer(shipment)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request, user_id=None):
        """Get the last shipment for a specific user using POST"""
        # If user_id is not in the URL path, try to get it from the request body
        if not user_id:
            user_id = request.data.get('user_id')
            
        print("user_id", user_id)
        
        if not user_id:
            return Response(
                {'error': 'user_id is required in the URL path or request body'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            # Get the most recent shipment for the user
            shipment = ShipmentRequest.objects.filter(
                user__id=user_id
            ).select_related(
                'sender_country',
                'recipient_country',
                'service_type'
            ).order_by('-created_at').first()
            
            if not shipment:
                return Response(
                    {'message': 'No shipments found for this user'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            serializer = ShipmentRequestSerializer(shipment)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

@extend_schema(tags=['shipments'])
class StaffShipmentsView(APIView):
    """
    View for getting shipments assigned to a specific staff member
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def check_staff_permission(self, request):
        """Check if user is staff and handle error response"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Only staff members can access this endpoint'},
                status=status.HTTP_403_FORBIDDEN
            )
        return None
    
    @extend_schema(
        summary="Get staff shipments",
        description="Get all shipments assigned to a specific staff member",
        parameters=[
            OpenApiParameter(
                name='staff_id',
                type=str,
                location=OpenApiParameter.QUERY,
                description='ID of the staff member to get shipments for'
            ),
            OpenApiParameter(
                name='status',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Filter by shipment status'
            ),
            OpenApiParameter(
                name='payment_status',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Filter by payment status'
            )
        ]
    )
    def get(self, request, staff_id=None):
        """Get shipments assigned to a specific staff member"""
        shipment_id = request.query_params.get('shipment_id')
        # Check staff permission
        error_response = self.check_staff_permission(request)
        if error_response:
            return error_response
            
        # If staff_id is not in the URL path, try to get it from query parameters
        if not staff_id:
            staff_id = request.query_params.get('staff_id')
        
        # If still no staff_id, use the current user's ID
        if not staff_id:
            staff_id = request.user.id
            
            
        try:
            # Build the base queryset
            queryset = ShipmentRequest.objects.select_related(
                'sender_country',
                'recipient_country',
                'service_type',
                'user',
                'staff'
            )
            
            # Apply filters
            status_filter = request.query_params.get('status')
            if status_filter:
                queryset = queryset.filter(status=status_filter)
                
            payment_status = request.query_params.get('payment_status')
            if payment_status:
                queryset = queryset.filter(payment_status=payment_status)
            
            # Filter by staff_id
            queryset = queryset.filter(staff_id=staff_id).order_by('-created_at')
            
            if not queryset.exists():
                return Response(
                    {'message': 'No shipments found for this staff member'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            serializer = ShipmentRequestSerializer(queryset, many=True, )
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
@extend_schema(tags=['shipments'])
class StaffShipmentCreateView(APIView):
    """
    View for creating a new shipment request for a specific user
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        summary="Create shipment for User",
        description="Create a new shipment request for a specific user",
        request=ShipmentCreateSerializer
    )
    def post(self, request, user_id=None):
        """Create a new shipment request for a specific user"""
        try:
            # Process the request data
            data = request.data.copy()
            data['staff'] = request.user.id
            
            # Get user
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response(
                    {'error': 'User not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Calculate shipping cost
            cost_breakdown = calculate_shipping_cost(
                sender_country_id=data.get('sender_country'),
                recipient_country_id=data.get('recipient_country'),
                service_type_id=data.get('service_type'),
                weight=data.get('weight'),
                dimensions={
                    'length': data.get('length'),
                    'width': data.get('width'),
                    'height': data.get('height')
                },
                city_id=data.get('city'),
                extras_data=data.get('additional_charges', [])
            )

            if cost_breakdown.get('errors'):
                return Response(
                    {'error': cost_breakdown['errors']},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Update data with calculated values
            data.update({
                'weight_charge': cost_breakdown.get('weight_charge', 0),
                'total_additional_charges': sum(float(charge['amount']) for charge in cost_breakdown.get('additional_charges', [])),
                'extras_charges': sum(float(extra['amount']) for extra in cost_breakdown.get('extras', [])),
                'total_cost': cost_breakdown.get('total_cost', 0),
                'per_kg_rate': cost_breakdown.get('per_kg_rate', 0),
                'delivery_charge': cost_breakdown.get('city_delivery_charge', 0)
            })
                
            # Process extras if present in cost_breakdown
            if 'extras' in cost_breakdown:
                extras = []
                for extra in cost_breakdown['extras']:
                    if isinstance(extra, dict) and 'id' in extra:
                        extras.append(extra['id'])
                data['extras'] = extras
            # Handle legacy format with additional_charges
            elif 'additional_charges' in data and isinstance(data['additional_charges'], list):
                extras = []
                for item in data['additional_charges']:
                    if isinstance(item, dict) and 'id' in item:
                        extras.append(item['id'])
                data['extras'] = extras
                
            # Create and validate the serializer
            serializer = ShipmentCreateSerializer(data=data)
            if serializer.is_valid():
                serializer.save(user=user)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    
@extend_schema(tags=['shipments'])
class StaffShipmentManagementView(APIView):
    """
    View for staff to manage individual shipments (update/delete)
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def check_staff_permission(self, request):
        """Check if user is staff and handle error response"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Only staff members can access this endpoint'},
                status=status.HTTP_403_FORBIDDEN
            )
        return None
    
    def get_shipment(self, pk, staff_user):
        """Get shipment and verify staff access"""
        shipment = get_object_or_404(
            ShipmentRequest.objects.select_related(
                'sender_country',
                'recipient_country',
                'service_type',
                'user',
                'staff'
            ),
            pk=pk
        )
        
        # Verify the shipment is assigned to this staff member
        if shipment.staff_id != staff_user.id:
            raise PermissionError(
                "You don't have permission to manage this shipment"
            )
            
        return shipment
    
    @extend_schema(
        summary="Update shipment",
        description="Update shipment details (staff only)"
    )
    def put(self, request, pk):
        """Full update of a shipment"""
        # Check staff permission
        error_response = self.check_staff_permission(request)
        if error_response:
            return error_response
            
        try:
            shipment = self.get_shipment(pk, request.user)
            
            # Make a copy of the request data
            data = request.data.copy()
            
            # Handle city update separately since it's marked as read_only in serializer
            city_id = data.get('city')
            if city_id and city_id != str(shipment.city_id if shipment.city else ''):
                try:
                    from accounts.models import City
                    city = City.objects.get(id=city_id)
                    shipment.city = city
                    shipment.save(update_fields=['city'])
                except City.DoesNotExist:
                    return Response(
                        {'error': f'City with ID {city_id} does not exist'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Calculate shipping cost if relevant fields are present
            recalculate_prices = any(field in data for field in [
                'weight', 'length', 'width', 'height', 'sender_country', 
                'recipient_country', 'service_type', 'city', 'additional_charges'
            ])
            
            if recalculate_prices:
                # Prepare dimensions if they exist
                dimensions = None
                if all(key in data for key in ['length', 'width', 'height']):
                    dimensions = {
                        'length': data.get('length', shipment.length),
                        'width': data.get('width', shipment.width),
                        'height': data.get('height', shipment.height)
                    }
                elif all(hasattr(shipment, key) for key in ['length', 'width', 'height']):
                    dimensions = {
                        'length': shipment.length,
                        'width': shipment.width,
                        'height': shipment.height
                    }
                
                # Extract extras data from request if provided
                extras_data = data.get('extras', None)
                
                # Get current values for fields not in the request data
                sender_country_id = data.get('sender_country', shipment.sender_country_id)
                recipient_country_id = data.get('recipient_country', shipment.recipient_country_id)
                service_type_id = data.get('service_type', shipment.service_type_id)
                weight = data.get('weight', shipment.weight)
                city_id = data.get('city', shipment.city_id if shipment.city else None)
                
                # Calculate shipping cost
                cost_breakdown = calculate_shipping_cost(
                    sender_country_id=sender_country_id,
                    recipient_country_id=recipient_country_id,
                    service_type_id=service_type_id,
                    weight=weight,
                    dimensions=dimensions,
                    city_id=city_id,
                    extras_data=extras_data
                )
                
                # Check for errors
                if cost_breakdown.get('errors'):
                    return Response(
                        {'errors': cost_breakdown['errors']},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Update data with calculated values
                data['weight_charge'] = cost_breakdown['weight_charge']
                data['service_charge'] = cost_breakdown['service_price']
                data['delivery_charge'] = cost_breakdown['city_delivery_charge']
                data['per_kg_rate'] = cost_breakdown.get('per_kg_rate', 0)
                
                # Calculate total_additional_charges from cost_breakdown
                total_additional = Decimal('0.00')
                for charge in cost_breakdown['additional_charges']:
                    total_additional += Decimal(str(charge['amount']))
                data['total_additional_charges'] = total_additional
                
                # Calculate extras_charges
                if 'extras_total' in cost_breakdown:
                    data['extras_charges'] = cost_breakdown['extras_total']
                
                # Set total cost
                data['total_cost'] = cost_breakdown['total_cost']
                
                # Add the cost breakdown to the data for processing by the serializer
                data['cost_breakdown'] = cost_breakdown
            
            # Update serializer with processed data
            serializer = ShipmentRequestSerializer(
                shipment,
                data=data
            )
            
            if serializer.is_valid():
                # Add tracking history entry for the update
                old_status = shipment.status
                updated_shipment = serializer.save()
                
                # Explicitly regenerate the receipt to ensure it's updated
                updated_shipment.regenerate_receipt()
                
                if old_status != updated_shipment.status:
                    updated_shipment.tracking_history.append({
                        'status': updated_shipment.get_status_display(),
                        'location': updated_shipment.current_location,
                        'timestamp': timezone.now().isoformat(),
                        'description': f'Status updated by staff: {request.user.email}',
                        'staff_id': str(request.user.id)
                    })
                    updated_shipment.save()
                
                return Response(serializer.data)
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
            
        except PermissionError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Partial update shipment",
        description="Partially update shipment details (staff only)"
    )
    def patch(self, request, pk):
        """Partial update of a shipment"""
        # Check staff permission
        error_response = self.check_staff_permission(request)
        if error_response:
            return error_response
            
        try:
            shipment = self.get_shipment(pk, request.user)
            
            # Make a copy of the request data
            data = request.data.copy()
            
            # Handle city update separately since it's marked as read_only in serializer
            city_id = data.get('city')
            if city_id and city_id != str(shipment.city_id if shipment.city else ''):
                try:
                    from accounts.models import City
                    city = City.objects.get(id=city_id)
                    shipment.city = city
                    shipment.save(update_fields=['city'])
                except City.DoesNotExist:
                    return Response(
                        {'error': f'City with ID {city_id} does not exist'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Calculate shipping cost if relevant fields are being updated
            recalculate_prices = any(field in data for field in [
                'weight', 'length', 'width', 'height', 'sender_country', 
                'recipient_country', 'service_type', 'city', 'additional_charges'
            ])
            
            if recalculate_prices:
                # Prepare dimensions if they exist
                dimensions = None
                if all(key in data for key in ['length', 'width', 'height']):
                    dimensions = {
                        'length': data.get('length', shipment.length),
                        'width': data.get('width', shipment.width),
                        'height': data.get('height', shipment.height)
                    }
                elif all(hasattr(shipment, key) for key in ['length', 'width', 'height']):
                    dimensions = {
                        'length': shipment.length,
                        'width': shipment.width,
                        'height': shipment.height
                    }
                
                # Extract extras data from request if provided
                extras_data = data.get('additional_charges', None)
                
                # Get current values for fields not in the request data
                sender_country_id = data.get('sender_country', shipment.sender_country_id)
                recipient_country_id = data.get('recipient_country', shipment.recipient_country_id)
                service_type_id = data.get('service_type', shipment.service_type_id)
                weight = data.get('weight', shipment.weight)
                city_id = data.get('city', shipment.city_id if shipment.city else None)
                
                # Calculate shipping cost
                cost_breakdown = calculate_shipping_cost(
                    sender_country_id=sender_country_id,
                    recipient_country_id=recipient_country_id,
                    service_type_id=service_type_id,
                    weight=weight,
                    dimensions=dimensions,
                    city_id=city_id,
                    extras_data=extras_data
                )
                
                # Check for errors
                if cost_breakdown.get('errors'):
                    return Response(
                        {'errors': cost_breakdown['errors']},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Update data with calculated values
                data['weight_charge'] = cost_breakdown['weight_charge']
                data['service_charge'] = cost_breakdown['service_price']
                data['delivery_charge'] = cost_breakdown['city_delivery_charge']
                data['per_kg_rate'] = cost_breakdown.get('per_kg_rate', 0)
                
                # Calculate total_additional_charges from cost_breakdown
                total_additional = Decimal('0.00')
                for charge in cost_breakdown['additional_charges']:
                    total_additional += Decimal(str(charge['amount']))
                data['total_additional_charges'] = total_additional
                
                # Calculate extras_charges
                if 'extras_total' in cost_breakdown:
                    data['extras_charges'] = cost_breakdown['extras_total']
                
                # Set total cost
                data['total_cost'] = cost_breakdown['total_cost']
                
                # Add the cost breakdown to the data for processing by the serializer
                data['cost_breakdown'] = cost_breakdown
            
            # Update serializer with processed data
            serializer = ShipmentRequestSerializer(
                shipment,
                data=data,
                partial=True
            )
            
            if serializer.is_valid():
                # Add tracking history entry if status is being updated
                old_status = shipment.status
                updated_shipment = serializer.save()
                
                # Explicitly regenerate the receipt to ensure it's updated
                updated_shipment.regenerate_receipt()
                
                if 'status' in request.data and old_status != updated_shipment.status:
                    updated_shipment.tracking_history.append({
                        'status': updated_shipment.get_status_display(),
                        'location': updated_shipment.current_location,
                        'timestamp': timezone.now().isoformat(),
                        'description': f'Status updated by staff: {request.user.email}',
                        'staff_id': str(request.user.id)
                    })
                    updated_shipment.save()
                
                return Response(serializer.data)
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
            
        except PermissionError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Delete shipment",
        description="Delete a shipment (staff only, restricted to certain statuses)"
    )
    def delete(self, request, pk):
        """Delete a shipment"""
        # Check staff permission
        error_response = self.check_staff_permission(request)
        if error_response:
            return error_response
            
        try:
            shipment = self.get_shipment(pk, request.user)
            
            # Only allow deletion of shipments in certain statuses
            allowed_statuses = [
                ShipmentRequest.Status.PENDING,
                ShipmentRequest.Status.CANCELLED
            ]
            
            if shipment.status not in allowed_statuses:
                return Response(
                    {
                        'error': 'Can only delete shipments in PENDING or CANCELLED status'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            shipment.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except PermissionError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

@extend_schema(tags=['shipments'])
class AssignStaffToShipmentView(APIView):
    """
    View for assigning a staff member to a shipment
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        summary="Assign staff to shipment",
        description="Assign a staff member to handle a specific shipment",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'shipment_id': {
                        'type': 'string',
                        'description': 'ID of the shipment to assign'
                    },
                    'staff_id': {
                        'type': 'string',
                        'description': 'ID of the staff member to assign'
                    }
                },
                'required': ['shipment_id', 'staff_id']
            }
        }
    )
    def post(self, request):
        """Assign a staff member to a shipment"""
        shipment_id = request.data.get('shipment_id')
        staff_id = request.data.get('staff_id')
        
        if not shipment_id or not staff_id:
            return Response(
                {'error': 'Both shipment_id and staff_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            # Check if the shipment exists
            shipment = get_object_or_404(ShipmentRequest, id=shipment_id)
            
            # Check if the staff user exists and is actually staff
            
            User = get_user_model()
            
            try:
                staff_user = User.objects.get(id=staff_id)
                if not hasattr(staff_user, 'is_staff') or not staff_user.is_staff:
                    return Response(
                        {'error': 'The specified user is not a staff member'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except User.DoesNotExist:
                return Response(
                    {'error': 'Staff user not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Assign the staff member to the shipment
            shipment.staff = staff_user
            shipment.save()
            
            serializer = ShipmentRequestSerializer(shipment)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

@extend_schema(tags=['shipments'])
class ShipmentStatusLocationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing available status locations for shipment updates.
    Only accessible by staff members.
    """
    queryset = ShipmentStatusLocation.objects.filter(is_active=True)
    serializer_class = ShipmentStatusLocationSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]
    
    def get_queryset(self):
        """Filter status locations based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by status type if provided
        status_type = self.request.query_params.get('status_type')
        if status_type:
            queryset = queryset.filter(status_type=status_type)
            
        return queryset.order_by('display_order', 'status_type')

@extend_schema(tags=['shipments'])
class StaffShipmentStatusUpdateView(APIView):
    """
    View for staff to update shipment status using available status locations.
    Any staff member can view and update shipment statuses.
    """
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]
    
    def get_shipment(self, shipment_id, staff_user):
        """Get shipment and verify it exists"""
        return get_object_or_404(
            ShipmentRequest.objects.select_related(
                'sender_country',
                'recipient_country',
                'service_type',
                'user',
                'staff'
            ),
            pk=shipment_id
        )
    
    @extend_schema(
        summary="Get available status locations",
        description="Get all available status locations for updating shipment status",
        parameters=[
            OpenApiParameter(
                name='shipment_id',
                type=str,
                location=OpenApiParameter.PATH,
                description='ID of the shipment to update'
            ),
            OpenApiParameter(
                name='status_type',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Filter by status type (e.g., PROCESSING, IN_TRANSIT)'
            )
        ]
    )
    def get(self, request, shipment_id):
        """Get available status locations for updating a shipment"""
        # Get the shipment
        shipment = self.get_shipment(shipment_id, request.user)
        
        # Get status locations filtered by status type if provided
        status_type = request.query_params.get('status_type')
        locations = ShipmentStatusLocation.objects.filter(is_active=True)
        
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
                'current_location': shipment.current_location,
                'staff': shipment.staff.email if shipment.staff else None
            },
            'available_status_locations': serializer.data
        })
    
    @extend_schema(
        summary="Update shipment status",
        description="Update shipment status using a status location",
        request=StatusUpdateSerializer
    )
    def post(self, request, shipment_id):
        """Update shipment status"""
        # Get the shipment
        shipment = self.get_shipment(shipment_id, request.user)
        
        # Validate the request data
        serializer = StatusUpdateSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            try:
                # Update the shipment status
                updated_shipment = serializer.update(shipment, serializer.validated_data)
                
                # Explicitly regenerate the receipt to ensure it's updated
                updated_shipment.regenerate_receipt()
                
                # If the shipment doesn't have a staff member assigned, assign the current user
                if not updated_shipment.staff:
                    updated_shipment.staff = request.user
                    updated_shipment.save()
                
                # Return the updated shipment
                return Response({
                    'success': True,
                    'message': f"Shipment status updated to {updated_shipment.get_status_display()}",
                    'shipment': {
                        'id': updated_shipment.id,
                        'tracking_number': updated_shipment.tracking_number,
                        'status': updated_shipment.status,
                        'current_location': updated_shipment.current_location,
                        'updated_at': updated_shipment.updated_at,
                        'staff': updated_shipment.staff.email if updated_shipment.staff else None
                    },
                    'tracking_update': updated_shipment.tracking_history[-1] if updated_shipment.tracking_history else None
                })
            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(tags=['shipments'])
class ShipmentMessageGeneratorView(APIView):
    """
    View for generating professional messages for shipments.
    This can be used to create standardized messages for shipment notifications.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self, pk):
        # For user access
        return get_object_or_404(
            ShipmentRequest.objects.select_related(
                'sender_country',
                'recipient_country',
                'service_type'
            ),
            pk=pk,
            user=self.request.user
        )
    
    def get_shipment_for_staff(self, pk, staff_user):
        # For staff access
        if not staff_user.is_staff and not staff_user.groups.filter(name='Staff').exists():
            raise PermissionDenied("Staff access required")
        
        # Staff can access any shipment
        return get_object_or_404(
            ShipmentRequest.objects.select_related(
                'sender_country',
                'recipient_country',
                'service_type'
            ),
            pk=pk
        )
    
    @extend_schema(
        summary="Generate shipment message",
        description="Generate a professional message for a shipment with sender details",
        request=ShipmentMessageSerializer,
        responses={200: {"type": "object", "properties": {"message": {"type": "string"}}}}
    )
    def post(self, request, pk):
        """Generate a professional message for a shipment"""
        # Check if user is staff or regular user
        if request.user.is_staff or request.user.groups.filter(name='Staff').exists():
            shipment = self.get_shipment_for_staff(pk, request.user)
        else:
            shipment = self.get_object(pk)
        
        # Create a copy of the data and add user_id if not present
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        
        # If include_credentials is True and user_id is not provided, use the shipment's user ID
        if data.get('include_credentials') and 'user_id' not in data and shipment.user:
            data['user_id'] = str(shipment.user.id)
            
        serializer = ShipmentMessageSerializer(data=data)
        
        if serializer.is_valid():
            try:
                # Generate message text
                message = serializer.generate_message(shipment)
                return Response({"message": message}, status=status.HTTP_200_OK)
            except Exception as e:
                return Response(
                    {"error": f"Error generating message: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(tags=['shipments'])
class UserShipmentHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    
    @extend_schema(
        summary="Get user's shipment history",
        description="Get a list of all shipments for a specific user (staff only)"
    )
    def get(self, request, user_id):
        """Get all shipments for a specific user"""
        try:
            user = get_user_model().objects.get(id=user_id)
            shipments = ShipmentRequest.objects.filter(
                user=user
            ).select_related(
                'sender_country',
                'recipient_country',
                'service_type'
            ).order_by('-created_at')
            
            serializer = ShipmentRequestSerializer(shipments, many=True)
            return Response(serializer.data)
        except get_user_model().DoesNotExist:
            return Response(
                {"error": "User not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

@extend_schema(tags=['shipments'])
class StaffShipmentAWBView(APIView):
    """
    View for generating AWB (Air Waybill) for shipments.
    Only accessible by staff members.
    """
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]
    
    def generate_awb(self, shipment):
        """Generate AWB PDF for a shipment"""
        # Import QrCodeWidget for QR code generation
        from reportlab.graphics import renderPDF
        from reportlab.graphics.barcode.qr import QrCodeWidget
        from reportlab.graphics.shapes import Drawing
        
        buffer = io.BytesIO()
        # Change to a smaller page size suitable for receipt printers (80mm width)
        receipt_width = 226  # ~80mm in points
        receipt_height = 600  # Taller receipt
        p = canvas.Canvas(buffer, pagesize=(receipt_width, receipt_height))
        
        # Define common measurements
        left_margin = 10
        right_margin = receipt_width - 10
        top_margin = receipt_height - 20
        
        # Draw border around the page
        p.rect(left_margin, 20, receipt_width - 20, receipt_height - 40)
        
        # Header section
        p.setFont("Helvetica-Bold", 14)  # Increased font size
        p.drawCentredString(receipt_width/2, top_margin - 20, "Grade-A Express")
        p.setFont("Helvetica-Bold", 12)  # Increased font size
        # p.drawString(left_margin + 10, top_margin - 40, "Description:")
        p.setFont("Helvetica", 12)
        # if shipment.description:
        #     p.drawString(left_margin + 80, top_margin - 40, shipment.description)
        
        # AWB number section
        p.setFont("Helvetica-Bold", 12)
        p.drawCentredString(receipt_width/2, top_margin - 60, shipment.tracking_number)
        
        # Generate and draw QR code instead of barcode
        qr_code = QrCodeWidget("https://www.gradeaexpress.com/public/shipment/"+str(shipment.id)+"/update-status")
        bounds = qr_code.getBounds()
        qr_width = bounds[2] - bounds[0]
        qr_height = bounds[3] - bounds[1]
        qr_size = 100  # Size of QR code in points
        drawing = Drawing(qr_size, qr_size, transform=[qr_size/qr_width, 0, 0, qr_size/qr_height, 0, 0])
        drawing.add(qr_code)
        
        # Position QR code in the center
        qr_x = (receipt_width - qr_size) / 2
        qr_y = top_margin - 170
        renderPDF.draw(drawing, p, qr_x, qr_y)
        
        # Content sections - FROM
        y = top_margin - 180
        # Title
        p.setFillColor(colors.lightgrey)
        p.rect(left_margin + 5, y, right_margin - left_margin - 10, 18, fill=1)
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 11)
        p.drawCentredString(receipt_width/2, y + 5, "FROM")
        
        # FROM details
        y -= 25
        p.setFont("Helvetica-Bold", 10)
        p.drawString(left_margin + 10, y, "Name:")
        p.setFont("Helvetica", 10)
        p.drawString(left_margin + 60, y, shipment.sender_name)
        
        y -= 18
        p.setFont("Helvetica-Bold", 10)
        p.drawString(left_margin + 10, y, "Phone:")
        p.setFont("Helvetica", 10)
        p.drawString(left_margin + 60, y, shipment.sender_phone)
        
        y -= 18
        p.setFont("Helvetica-Bold", 10)
        p.drawString(left_margin + 10, y, "Country:")
        p.setFont("Helvetica", 10)
        p.drawString(left_margin + 60, y, shipment.sender_country.name)
        
        # TO section
        y -= 25
        p.setFillColor(colors.lightgrey)
        p.rect(left_margin + 5, y, right_margin - left_margin - 10, 18, fill=1)
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 11)
        p.drawCentredString(receipt_width/2, y + 5, "TO")
        
        # TO details
        y -= 25
        p.setFont("Helvetica-Bold", 10)
        p.drawString(left_margin + 10, y, "Name:")
        p.setFont("Helvetica", 10)
        p.drawString(left_margin + 60, y, shipment.recipient_name)
        
        y -= 18
        p.setFont("Helvetica-Bold", 10)
        p.drawString(left_margin + 10, y, "Phone:")
        p.setFont("Helvetica", 10)
        p.drawString(left_margin + 60, y, shipment.recipient_phone)
        
        y -= 18
        p.setFont("Helvetica-Bold", 10)
        p.drawString(left_margin + 10, y, "Country:")
        p.setFont("Helvetica", 10)
        p.drawString(left_margin + 60, y, shipment.recipient_country.name)
        
        # SHIPMENT DETAILS
        y -= 25
        p.setFillColor(colors.lightgrey)
        p.rect(left_margin + 5, y, right_margin - left_margin - 10, 18, fill=1)
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 11)
        p.drawCentredString(receipt_width/2, y + 5, "SHIPMENT DETAILS")
        
        # Details
        y -= 25
        p.setFont("Helvetica-Bold", 10)
        p.drawString(left_margin + 10, y, "Service:")
        p.setFont("Helvetica", 10)
        p.drawString(left_margin + 60, y, shipment.service_type.name)
        
        y -= 18
        p.setFont("Helvetica-Bold", 10)
        p.drawString(left_margin + 10, y, "Package:")
        p.setFont("Helvetica", 10)
        p.drawString(left_margin + 60, y, shipment.package_type)
        
        y -= 18
        p.setFont("Helvetica-Bold", 10)
        p.drawString(left_margin + 10, y, "Weight:")
        p.setFont("Helvetica", 10)
        p.drawString(left_margin + 60, y, f"{shipment.weight} kg")
        
        # SPECIAL INSTRUCTIONS - No space between this and footer
        y -= 25
        p.setFillColor(colors.lightgrey)
        p.rect(left_margin + 5, y, right_margin - left_margin - 10, 18, fill=1)
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 11)
        p.drawCentredString(receipt_width/2, y + 5, "SPECIAL INSTRUCTIONS")
        
        # Instructions content
        y -= 25
        p.setFont("Helvetica", 10)
        instructions = []
        if shipment.description:
            instructions.append(f"Description: {shipment.description}")
        if shipment.insurance_required:
            instructions.append("Insurance Required")
        if shipment.signature_required:
            instructions.append("Signature Required")
        
        if instructions:
            # For longer descriptions, wrap text to fit width
            instruction_text = " | ".join(instructions)
            if len(instruction_text) > 30:  # If text is long
                lines = []
                current_line = ""
                for word in instruction_text.split():
                    if len(current_line + " " + word) <= 30:
                        current_line += " " + word if current_line else word
                    else:
                        lines.append(current_line)
                        current_line = word
                if current_line:
                    lines.append(current_line)
                
                for line in lines:
                    p.drawString(left_margin + 10, y, line)
                    y -= 15
            else:
                p.drawString(left_margin + 10, y, instruction_text)
        else:
            p.drawString(left_margin + 10, y, "None")
            y -= 15
        
        # Footer - position at absolute bottom of receipt instead of directly after instructions
        footer_y = 60  # Fixed position at bottom of receipt
        
        p.setFillColor(colors.lightgrey)
        p.rect(left_margin + 5, footer_y - 30, right_margin - left_margin - 10, 30, fill=1)
        p.setFillColor(colors.black)
        
        # Footer content with larger fonts
        p.setFont("Helvetica-Bold", 9)
        p.drawString(left_margin + 10, footer_y - 10, "COURIER COPY")
        p.drawString(right_margin - 90, footer_y - 10, "RECEIVER COPY")
        
        # Timestamp and AWB
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        p.setFont("Helvetica", 8)
        p.drawCentredString(receipt_width/2, footer_y - 20, f"Generated: {timestamp}")
        p.drawCentredString(receipt_width/2, footer_y - 30, f"AWB: {shipment.tracking_number}")
        
        # Close the PDF object
        p.showPage()
        p.save()
        buffer.seek(0)
        return buffer
    
    def get(self, request, shipment_id):
        """Generate AWB for a shipment"""
        try:
            # Get the shipment
            shipment = get_object_or_404(
                ShipmentRequest.objects.select_related(
                    'sender_country',
                    'recipient_country',
                    'service_type'
                ),
                pk=shipment_id
            )
            
            # Check if AWB already exists and delete it
            if shipment.awb:
                if os.path.exists(shipment.awb.path):
                    os.remove(shipment.awb.path)
            
            # Generate new AWB
            pdf_buffer = self.generate_awb(shipment)
            
            # Create filename
            filename = f"awb_{shipment.tracking_number}.pdf"
            
            # Save the PDF to the shipment's AWB field
            from django.core.files.base import ContentFile
            shipment.awb.save(filename, ContentFile(pdf_buffer.getvalue()), save=True)
            
            # Return the URL to the PDF file
            if request.query_params.get('download') == 'true':
                # Return the file for direct download
                response = FileResponse(
                    open(shipment.awb.path, 'rb'),
                    content_type='application/pdf'
                )
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response
            else:
                # Return the URL and other metadata
                return Response({
                    'awb_url': request.build_absolute_uri(shipment.awb.url),
                    'filename': filename,
                    'generated_at': timezone.now().isoformat(),
                    'tracking_number': shipment.tracking_number
                })
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(tags=['shipments'])
class BulkPackageStatusUpdateView(APIView):
    """API view for updating status of multiple packages at once"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get_packages(self, package_ids, user):
        """Get packages by their IDs and validate permissions"""
        if not isinstance(package_ids, list):
            raise ValueError("package_ids must be a list")
            
        # Get all packages at once for efficiency
        packages = ShipmentPackage.objects.select_related('shipment').filter(id__in=package_ids)
        
        if not packages:
            raise Http404("No packages found with the provided IDs")
            
        # Check permissions - only staff or shipment owner can update
        if not user.is_staff:
            # For non-staff users, ensure they own all shipments
            unauthorized_packages = packages.exclude(shipment__user=user)
            if unauthorized_packages.exists():
                raise PermissionDenied("You don't have permission to update some of the packages")
                
        return packages
    
    @extend_schema(
        summary="Update multiple package statuses",
        description="Update the status of multiple packages at once",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'package_ids': {
                        'type': 'array',
                        'items': {'type': 'integer'},
                        'description': 'List of package IDs to update'
                    },
                    'status_location_id': {
                        'type': 'integer',
                        'description': 'ID of the status location to use'
                    },
                    'custom_description': {
                        'type': 'string',
                        'description': 'Optional custom description'
                    }
                },
                'required': ['package_ids', 'status_location_id']
            }
        }
    )
    
    def post(self, request):
        """Update status for multiple packages"""
        # Validate input
        package_ids = request.data.get('package_ids')
        status_location_id = request.data.get('status_location_id')
        
        if not package_ids:
            return Response(
                {'error': 'package_ids is required and must be a non-empty list'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if not status_location_id:
            return Response(
                {'error': 'status_location_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            # Get all packages
            packages = self.get_packages(package_ids, request.user)
            
            # Get the status location
            try:
                status_location = ShipmentStatusLocation.objects.get(
                    id=status_location_id, is_active=True
                )
            except ShipmentStatusLocation.DoesNotExist:
                return Response(
                    {"error": "Status location not found or is inactive"},
                    status=status.HTTP_404_NOT_FOUND
                )
                
            # Get custom description if provided
            custom_description = request.data.get('custom_description')
            
            # Get the corresponding ShipmentRequest.Status
            status_mapping = ShipmentStatusLocation.get_status_mapping()
            package_status = status_mapping.get(status_location.status_type)
            
            # Description to use
            description = custom_description or status_location.description
            
            # Track successful and failed updates
            results = {
                'success': [],
                'failed': []
            }
            
            # Update each package
            for package in packages:
                try:
                    # Update the package tracking
                    old_status = package.status
                    package.update_tracking(
                        package_status,
                        status_location.location_name,
                        description
                    )
                    
                    # Add to successful updates
                    results['success'].append({
                        'id': package.id,
                        'number': package.number,
                        'status': package.status,
                        'status_display': dict(ShipmentPackage.Status.choices)[package.status],
                        'old_status': old_status,
                        'shipment_tracking': package.shipment.tracking_number
                    })
                except Exception as e:
                    # Add to failed updates
                    results['failed'].append({
                        'id': package.id,
                        'number': package.number,
                        'error': str(e)
                    })
            
            # Prepare response message
            success_count = len(results['success'])
            failed_count = len(results['failed'])
            
            if success_count > 0 and failed_count == 0:
                message = f"Successfully updated {success_count} package(s)"
                response_status = status.HTTP_200_OK
            elif success_count > 0 and failed_count > 0:
                message = f"Partially updated packages. {success_count} successful, {failed_count} failed."
                response_status = status.HTTP_207_MULTI_STATUS
            else:
                message = "Failed to update any packages"
                response_status = status.HTTP_400_BAD_REQUEST
            
            return Response({
                'message': message,
                'results': results,
                'status_update': {
                    'status': package_status,
                    'status_display': dict(ShipmentPackage.Status.choices)[package_status],
                    'location': status_location.location_name,
                    'description': description,
                    'timestamp': timezone.now().isoformat()
                }
            }, status=response_status)
                
        except PermissionDenied as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        except Http404 as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f"An unexpected error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

