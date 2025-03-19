import string

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django_filters import rest_framework as filters
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User

from .models import ShipmentRequest, ShipmentStatusLocation, SupportTicket
from .permissions import IsStaffUser
from .serializers import (ShipmentCreateSerializer, ShipmentRequestSerializer,
                          ShipmentStatusLocationSerializer,
                          StatusUpdateSerializer, SupportTicketSerializer)

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
        # allowed_fields = {'notes', 'recipient_address', 'recipient_phone'}
        # data = {
        #     k: v for k, v in request.data.items() 
        #     if k in allowed_fields
        # }
        
        serializer = ShipmentRequestSerializer(
            shipment,
            data=request.data,
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
        data = request.data
        data['staff'] = request.user.id
        extras = []
        print(data.get("additional_charges"))
        for item in data.get('additional_charges'):
            extras.append(item.get('id'))
        data['extras'] = extras        
        serializer = ShipmentCreateSerializer(data=request.data)
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        if serializer.is_valid():
            serializer.save(user=user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    
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
            serializer = ShipmentRequestSerializer(
                shipment,
                data=request.data
            )
            
            if serializer.is_valid():
                # Add tracking history entry for the update
                old_status = shipment.status
                updated_shipment = serializer.save()
                
                if old_status != updated_shipment.status:
                    updated_shipment.tracking_history.append({
                        'status': updated_shipment.status,
                        'location': updated_shipment.current_location,
                        'timestamp': timezone.now().isoformat(),
                        'description': f'Status updated by staff: {request.user.email}',
                        'staff_id': request.user.id
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
            serializer = ShipmentRequestSerializer(
                shipment,
                data=request.data,
                partial=True
            )
            
            if serializer.is_valid():
                # Add tracking history entry if status is being updated
                old_status = shipment.status
                updated_shipment = serializer.save()
                
                if 'status' in request.data and old_status != updated_shipment.status:
                    updated_shipment.tracking_history.append({
                        'status': updated_shipment.status,
                        'location': updated_shipment.current_location,
                        'timestamp': timezone.now().isoformat(),
                        'description': f'Status updated by staff: {request.user.email}',
                        'staff_id': request.user.id
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



class SupportTicketFilter(filters.FilterSet):
    status = filters.CharFilter(field_name="status", lookup_expr='iexact')
    category = filters.CharFilter(field_name="category", lookup_expr='iexact')
    assigned_to = filters.NumberFilter(field_name="assigned_to")
    created_at_min = filters.DateTimeFilter(field_name="created_at", lookup_expr='gte')
    created_at_max = filters.DateTimeFilter(field_name="created_at", lookup_expr='lte')

    class Meta:
        model = SupportTicket
        fields = ['status', 'category', 'assigned_to', 'created_at_min', 'created_at_max']

class SupportTicketListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Filtering support tickets based on parameters
        tickets = SupportTicket.objects.filter(user=request.user)
        
        # Applying filters
        filter_backends = (filters.DjangoFilterBackend,)
        filterset = SupportTicketFilter(request.GET, queryset=tickets)
        
        if filterset.is_valid():
            tickets = filterset.qs
        else:
            return Response(filterset.errors, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = SupportTicketSerializer(tickets, many=True)
        return Response(serializer.data)

    def post(self, request):
        # Creating a new ticket
        serializer = SupportTicketSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)  # Set the user automatically
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class SupportTicketDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, ticket_number):
        try:
            return SupportTicket.objects.get(ticket_number=ticket_number, user=self.request.user)
        except SupportTicket.DoesNotExist:
            return None

    def get(self, request, ticket_number):
        ticket = self.get_object(ticket_number)
        if ticket is None:
            return Response({'detail': 'Ticket not found or access denied.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = SupportTicketSerializer(ticket)
        return Response(serializer.data)

    def put(self, request, ticket_number):
        ticket = self.get_object(ticket_number)
        if ticket is None:
            return Response({'detail': 'Ticket not found or access denied.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = SupportTicketSerializer(ticket, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, ticket_number):
        ticket = self.get_object(ticket_number)
        if ticket is None:
            return Response({'detail': 'Ticket not found or access denied.'}, status=status.HTTP_404_NOT_FOUND)

        ticket.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
