import io
import os
import string
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, Prefetch, Q
from django.http import FileResponse
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

from .models import ShipmentRequest, ShipmentStatusLocation, SupportTicket
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
            serializer.save()
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
            shipment = ShipmentRequest.objects.get(
                tracking_number=tracking_number.upper()
            )
            
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
                    }
                },
                'tracking_history': [
                    {
                        'status': update['status'],
                        'location': update['location'],
                        'timestamp': update['timestamp'],
                        'description': update['description']
                    }
                    for update in reversed(shipment.tracking_history)
                ]
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
                data=data
            )
            
            if serializer.is_valid():
                # Add tracking history entry for the update
                old_status = shipment.status
                updated_shipment = serializer.save()
                
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
                # Add tracking history entry if status is being updated
                old_status = shipment.status
                updated_shipment = serializer.save()
                
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
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # Define common measurements
        left_margin = 40
        right_margin = width - 40
        top_margin = height - 30
        
        # Draw border around the page
        p.rect(left_margin - 5, 30, width - 70, height - 60)
        
        # Header section - moved company name lower
        p.setFont("Helvetica-Bold", 22)
        p.drawString(left_margin + 5, top_margin - 25, "Grade-A Express")  # Moved lower
        p.setFont("Helvetica", 11)
        p.drawString(left_margin + 5, top_margin - 45, "International Air Waybill")  # Adjusted
        
        # Draw AWB number box (top right) - adjusted alignment
        p.rect(right_margin - 90, top_margin - 45, 80, 25)  # Adjusted box size and position
        p.setFont("Helvetica-Bold", 14)  # Reduced font size
        p.drawString(right_margin - 80, top_margin - 30, shipment.tracking_number[-7:])  # Better centered
        
        # Draw barcode
        barcode_value = shipment.tracking_number
        barcode = code128.Code128(barcode_value, barHeight=25*mm, barWidth=1.5)
        barcode_width = 250
        barcode_x = (width - barcode_width) / 2
        barcode.drawOn(p, barcode_x, top_margin - 110)
        
        # Draw tracking number below barcode
        p.setFont("Helvetica", 10)
        p.drawString(barcode_x + 60, top_margin - 125, "Tracking Number:")
        p.setFont("Helvetica-Bold", 11)
        p.drawString(barcode_x + 140, top_margin - 125, barcode_value)
        
        # Start content area
        content_top = top_margin - 160
        box_height = 140
        
        # FROM and TO boxes side by side
        box_width = (right_margin - left_margin - 10) / 2
        
        # FROM box
        p.rect(left_margin, content_top - box_height, box_width, box_height)
        # Title bar
        p.setFillColor(colors.lightgrey)
        p.rect(left_margin, content_top - 25, box_width, 25, fill=1)
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 14)
        p.drawString(left_margin + 10, content_top - 17, "FROM")
        
        # Sender details with better spacing and alignment
        y = content_top - 45
        field_pairs = [
            ("Name:", shipment.sender_name),
            ("Phone:", shipment.sender_phone),
            ("Address:", shipment.sender_address),
            ("Country:", shipment.sender_country.name)
        ]
        
        for label, value in field_pairs:
            p.setFont("Helvetica", 10)
            p.drawString(left_margin + 15, y, label)
            p.setFont("Helvetica-Bold", 10)
            if label == "Address:":
                y -= 15  # Move down for address value
                for line in value.split('\n'):
                    p.drawString(left_margin + 75, y, line.strip())
                    y -= 15
                y -= 5  # Extra space after address
            else:
                p.drawString(left_margin + 75, y, value)
                y -= 25  # Space between fields
        
        # TO box
        to_x = left_margin + box_width + 10
        p.rect(to_x, content_top - box_height, box_width, box_height)
        # Title bar
        p.setFillColor(colors.lightgrey)
        p.rect(to_x, content_top - 25, box_width, 25, fill=1)
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 14)
        p.drawString(to_x + 10, content_top - 17, "TO")
        
        # Recipient details with better spacing and alignment
        y = content_top - 45
        field_pairs = [
            ("Name:", shipment.recipient_name),
            ("Phone:", shipment.recipient_phone),
            ("Address:", shipment.recipient_address),
            ("Country:", shipment.recipient_country.name)
        ]
        
        for label, value in field_pairs:
            p.setFont("Helvetica", 10)
            p.drawString(to_x + 15, y, label)
            p.setFont("Helvetica-Bold", 10)
            if label == "Address:":
                y -= 15  # Move down for address value
                for line in value.split('\n'):
                    p.drawString(to_x + 75, y, line.strip())
                    y -= 15
                y -= 5  # Extra space after address
            else:
                p.drawString(to_x + 75, y, value)
                y -= 25  # Space between fields
        
        # Shipment Details section - full width with increased height
        details_top = content_top - box_height - 30  # Increased spacing
        details_height = 100  # Increased height
        p.rect(left_margin, details_top - details_height, right_margin - left_margin, details_height)
        
        # Title bar
        p.setFillColor(colors.lightgrey)
        p.rect(left_margin, details_top - 25, right_margin - left_margin, 25, fill=1)
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 14)
        p.drawString(left_margin + 10, details_top - 17, "SHIPMENT DETAILS")
        
        # Details content in two columns with better alignment and spacing
        y = details_top - 45
        col_width = (right_margin - left_margin - 40) / 2
        
        # Left column
        x = left_margin + 15
        details_left = [
            ("Service:", shipment.service_type.name),
            ("Package:", shipment.package_type),
            ("Weight:", f"{shipment.weight} kg")
        ]
        
        for label, value in details_left:
            p.setFont("Helvetica", 10)
            p.drawString(x, y, label)
            p.setFont("Helvetica-Bold", 10)
            p.drawString(x + 65, y, value)
            y -= 25  # Increased spacing between lines
        
        # Right column
        x = left_margin + col_width + 30
        y = details_top - 45
        details_right = [
            ("Dimensions:", f"{shipment.length}×{shipment.width}×{shipment.height} cm"),
            ("Payment:", shipment.get_payment_method_display())
        ]
        
        for label, value in details_right:
            p.setFont("Helvetica", 10)
            p.drawString(x, y, label)
            p.setFont("Helvetica-Bold", 10)
            p.drawString(x + 75, y, value)
            y -= 25  # Increased spacing between lines
        
        # Special Instructions section - adjusted spacing
        instructions_top = details_top - details_height - 20
        instructions_height = 60
        p.rect(left_margin, instructions_top - instructions_height, 
               right_margin - left_margin, instructions_height)
        
        # Title bar
        p.setFillColor(colors.lightgrey)
        p.rect(left_margin, instructions_top - 25, right_margin - left_margin, 25, fill=1)
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 14)
        p.drawString(left_margin + 10, instructions_top - 17, "SPECIAL INSTRUCTIONS")
        
        # Instructions content with better spacing
        y = instructions_top - 45
        instructions = []
        if shipment.description:
            instructions.append(f"Description: {shipment.description}")
        if shipment.insurance_required:
            instructions.append("Insurance Required")
        if shipment.signature_required:
            instructions.append("Signature Required")
        
        if instructions:
            p.setFont("Helvetica", 10)
            p.drawString(left_margin + 15, y, " | ".join(instructions))
        else:
            p.setFont("Helvetica", 10)
            p.drawString(left_margin + 15, y, "None")
        
        # Footer with better alignment
        footer_top = 60
        p.setFillColor(colors.lightgrey)
        p.rect(left_margin, footer_top - 30, right_margin - left_margin, 30, fill=1)
        p.setFillColor(colors.black)
        
        # Footer content with consistent spacing
        p.setFont("Helvetica-Bold", 8)
        p.drawString(left_margin + 15, footer_top - 12, "COURIER COPY")
        p.drawString(right_margin - 80, footer_top - 12, "RECEIVER COPY")
        
        # Timestamp and AWB with better spacing
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        p.setFont("Helvetica", 7)
        p.drawString(left_margin + 120, footer_top - 12, f"Generated: {timestamp}")
        p.drawString(left_margin + 280, footer_top - 12, f"AWB: {shipment.tracking_number}")
        
        # Terms line with better alignment
        p.setFont("Helvetica", 6)
        p.drawString(left_margin + 15, footer_top - 25, 
                    "By accepting this shipment, the sender agrees to Grade-A Express's terms of service. Additional charges may apply based on actual weight/dimensions.")
        
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

