from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, OpenApiParameter, inline_serializer
from drf_spectacular.types import OpenApiTypes
from rest_framework import generics, serializers
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser

from accounts.models import UserCountry
from .serializers import UserSerializer, UserCreateSerializer, UserCountrySerializer
from shipping_rates.models import Country
from django.db.models import Count, Q
from buy4me.models import Buy4MeRequest
User = get_user_model()

class PasswordUpdateSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=6)

@extend_schema(tags=['users'])
class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for viewing and editing user instances.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer

    @extend_schema(
        summary="Get current user",
        description="Returns the authenticated user's information",
        responses={200: UserSerializer},
    )
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user's information."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @extend_schema(
        summary="Update user password",
        description="Update the authenticated user's password. New password must be at least 6 characters long.",
        request=PasswordUpdateSerializer,
        responses={
            200: inline_serializer(
                name='PasswordUpdateResponse',
                fields={
                    'message': serializers.CharField()
                }
            ),
            400: inline_serializer(
                name='PasswordUpdateError',
                fields={
                    'error': serializers.CharField()
                }
            )
        }
    )
    @action(detail=False, methods=['post'])
    def update_password(self, request):
        """Update user password."""
        serializer = PasswordUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user
        old_password = serializer.validated_data['old_password']
        new_password = serializer.validated_data['new_password']

        # Check if old password is correct
        if not user.check_password(old_password):
            return Response(
                {'error': 'Current password is incorrect'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Set new password
        user.set_password(new_password)
        user.save()

        return Response({'message': 'Password updated successfully'})

    @extend_schema(
        summary="Get Buy4Me dashboard statistics",
        description="Returns counts of Buy4Me requests in different states",
        responses={200: {
            "type": "object",
            "properties": {
                "active_requests": {"type": "integer"},
                "pending_payments": {"type": "integer"},
                "orders_in_transit": {"type": "integer"},
                "completed_orders": {"type": "integer"}
            }
        }}
    )
    @action(detail=False, methods=['get'])
    def buy4me_dashboard(self, request):
        """Get Buy4Me dashboard statistics."""
        user_requests = request.user.buy4me_requests.all()
        
        # Active requests (DRAFT, SUBMITTED)
        active_count = user_requests.filter(
            status__in=['DRAFT', 'SUBMITTED']
        ).count()
        
        # Pending payments
        pending_payments_count = user_requests.filter(
            payment_status='PENDING'
        ).count()
        
        # Orders in transit (IN_TRANSIT, WAREHOUSE_ARRIVED, SHIPPED_TO_CUSTOMER)
        in_transit_count = user_requests.filter(
            status__in=['IN_TRANSIT', 'WAREHOUSE_ARRIVED', 'SHIPPED_TO_CUSTOMER']
        ).count()
        
        # Completed orders
        completed_count = user_requests.filter(
            status='COMPLETED'
        ).count()
        
        return Response({
            'active_requests': active_count,
            'pending_payments': pending_payments_count,
            'orders_in_transit': in_transit_count,
            'completed_orders': completed_count
        })

    @extend_schema(
        summary="Get shipping dashboard statistics",
        description="Returns counts of shipments in different states",
        responses={200: {
            "type": "object",
            "properties": {
                "active_shipments": {"type": "integer"},
                "in_transit": {"type": "integer"},
                "completed": {"type": "integer"}
            }
        }}
    )
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Get shipping dashboard statistics."""
        user_shipments = request.user.shipments.all()
        
        # Active shipments are those in PENDING or PROCESSING status
        active_count = user_shipments.filter(
            status__in=['PENDING', 'PROCESSING']
        ).count()
        
        # In transit shipments
        in_transit_count = user_shipments.filter(
            status='IN_TRANSIT'
        ).count()
        
        # Completed shipments are those that are DELIVERED
        completed_count = user_shipments.filter(
            status='DELIVERED'
        ).count()
        
        return Response({
            'active_shipments': active_count,
            'in_transit': in_transit_count,
            'completed': completed_count
        })

    @extend_schema(
        summary="Update current user",
        description="Update the authenticated user's information",
        responses={200: UserSerializer},
    )
    @action(detail=False, methods=['patch'])
    def update_me(self, request):
        """Update current user's information."""
        user = request.user
        serializer = self.get_serializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(
        summary="Create user",
        description="Create a new user account",
        request=UserCreateSerializer,
        responses={201: UserSerializer},
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="List users",
        description="Get a list of all users",
        parameters=[
            OpenApiParameter(
                name='user_type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter users by type (WALK_IN, BUY4ME, ADMIN, SUPER_ADMIN)',
                required=False,
            ),
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    
# create the singup view 

@extend_schema(tags=['users'])
class SignUpView(generics.CreateAPIView):
    serializer_class = UserCreateSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
    
# endpoint that  returns the list of all usercountires 
@extend_schema(tags=['users'])
class UserCountryView(generics.ListAPIView):
    serializer_class = UserCountrySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return UserCountry.objects.all()