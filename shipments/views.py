import string

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, render
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ShipmentRequest
from .serializers import ShipmentCreateSerializer, ShipmentRequestSerializer

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
        
        # Only allow updating certain fields
        allowed_fields = {'notes', 'recipient_address', 'recipient_phone'}
        data = {
            k: v for k, v in request.data.items() 
            if k in allowed_fields
        }
        
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
    
    @extend_schema(
        summary="Get staff shipments",
        description="Get all shipments assigned to a specific staff member",
        parameters=[
            OpenApiParameter(
                name='staff_id',
                type=str,
                location=OpenApiParameter.QUERY,
                description='ID of the staff member to get shipments for'
            )
        ]
    )
    def get(self, request, staff_id=None):
        """Get shipments assigned to a specific staff member"""
        # If staff_id is not in the URL path, try to get it from query parameters
        if not staff_id:
            staff_id = request.query_params.get('staff_id')
        
        # If still no staff_id and the user is staff, use their ID
        if not staff_id and hasattr(request.user, 'is_staff') and request.user.is_staff:
            staff_id = request.user.id
            
        if not staff_id:
            return Response(
                {'error': 'staff_id is required as a URL parameter or query parameter'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            # Get all shipments assigned to the staff member
            shipments = ShipmentRequest.objects.filter(
                staff_id=staff_id
            ).select_related(
                'sender_country',
                'recipient_country',
                'service_type',
                'user',
                'staff'
            ).order_by('-created_at')
            
            if not shipments.exists():
                return Response(
                    {'message': 'No shipments found for this staff member'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            serializer = ShipmentRequestSerializer(shipments, many=True)
            return Response(serializer.data)
            
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
            from django.contrib.auth import get_user_model
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
