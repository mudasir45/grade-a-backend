from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.db.models import Count, Q
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (OpenApiParameter, extend_schema,
                                   inline_serializer)
from rest_framework import generics, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Contact, Store, UserCountry
from buy4me.models import Buy4MeRequest
from shipping_rates.models import Country

from .serializers import (ContactSerializer, StoreSerializer,
                          UserCountrySerializer, UserCreateSerializer,
                          UserSerializer)

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

@extend_schema(tags=['contact'])
class ContactView(generics.CreateAPIView):
    """
    API endpoint for submitting contact form
    """
    serializer_class = ContactSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contact = serializer.save()
        
        # Send confirmation email to the user
        self.send_confirmation_email(contact)
        
        # Send notification email to admin
        self.send_admin_notification(contact)
        
        headers = self.get_success_headers(serializer.data)
        return Response(
            {"message": "Your message has been received. We'll get back to you soon."},
            status=status.HTTP_201_CREATED,
            headers=headers
        )
    
    def send_confirmation_email(self, contact):
        """Send confirmation email to the user who submitted the contact form"""
        context = {'contact': contact}
        
        # Render HTML content
        html_content = render_to_string('emails/contact_confirmation.html', context)
        text_content = strip_tags(html_content)
        
        # Create email message
        subject = f'Thank you for contacting Grade-A Express'
        from_email = settings.DEFAULT_FROM_EMAIL
        
        # Send to user
        email = EmailMultiAlternatives(
            subject,
            text_content,
            from_email,
            [contact.email]
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
    
    def send_admin_notification(self, contact):
        """Send notification email to admin about new contact form submission"""
        # Generate admin URL for the contact
        site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        admin_url = f"{site_url}/admin/accounts/contact/{contact.id}/change/"
        
        context = {
            'contact': contact,
            'admin_url': admin_url
        }
        
        # Render HTML content
        html_content = render_to_string('emails/contact_admin_notification.html', context)
        text_content = strip_tags(html_content)
        
        # Create email message
        subject = f'New Contact Form Submission: {contact.subject}'
        from_email = settings.DEFAULT_FROM_EMAIL
        
        # Send to admin
        email = EmailMultiAlternatives(
            subject,
            text_content,
            from_email,
            [settings.ADMIN_EMAIL]
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
        
        
        
        
class StoresView(APIView):

    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        stores = Store.objects.filter(is_active=True)
        serializer = StoreSerializer(stores, many=True)
        return Response(serializer.data)
    
    

class CheckStaffUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        if request.user.is_staff:
            return Response({'is_staff': True})
        return Response({'is_staff': False})
