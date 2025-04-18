from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.db.models import Count, Q
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django_filters import rest_framework as filters
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (OpenApiParameter, extend_schema,
                                   inline_serializer)
from rest_framework import generics, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.models import City, Contact, DriverPayment, Store, UserCountry
from buy4me.models import Buy4MeRequest
from shipments.models import ShipmentRequest, SupportTicket
from shipments.serializers import (ShipmentRequestSerializer,
                                   SupportTicketSerializer)
from shipping_rates.models import Country

from .serializers import (CitySerializer, ContactSerializer,
                          DriverPaymentSerializer,
                          PhoneTokenObtainPairSerializer, StoreSerializer,
                          UserCountrySerializer, UserCreateSerializer,
                          UserSerializer)

User = get_user_model()


@extend_schema(tags=['auth'])
class PhoneTokenObtainPairView(TokenObtainPairView):
    """
    Takes a set of user credentials (phone_number and password) and returns an access
    and refresh JSON web token pair to prove the authentication of those credentials.
    """
    serializer_class = PhoneTokenObtainPairSerializer

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
    pagination_class = None  # Disable pagination completely

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer
    
    def get_queryset(self):
        """
        Filter users based on query parameters.
        """
        queryset = User.objects.all()
        
        # Filter by user_type if provided
        user_type = self.request.query_params.get('user_type', None)
        if user_type:
            queryset = queryset.filter(user_type=user_type)
            
        return queryset
        
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
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

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
            status__in=['DRAFT', 'SUBMITTED', 'PROCESSING'],
            # also check if the request have at least one item
            # check if the request have at least one item
            items__isnull=False
        ).count()
        
        # Pending payments
        pending_payments_count = user_requests.filter(
            payment_status='PENDING',
            # also check if the request have at least one item
            items__isnull=False
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
        
        # total Support Tickets
        support_tickets_count = SupportTicket.objects.filter(user=request.user).count()
        
        return Response({
            'active_shipments': active_count,
            'in_transit': in_transit_count,
            'completed': completed_count,
            'support_tickets': support_tickets_count
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


# create the singup view 

@extend_schema(
    tags=['users'],
    summary="Register a new user",
    description="Create a new user account with phone number as the primary identifier. Username is automatically set to the phone number. Email is optional.",
    responses={
        201: UserSerializer,
        400: inline_serializer(
            name='SignupError',
            fields={
                'error': serializers.CharField(),
                'phone_number': serializers.ListField(child=serializers.CharField(), required=False),
                'email': serializers.ListField(child=serializers.CharField(), required=False),
            }
        )
    }
)

class SignUpView(generics.CreateAPIView):
    serializer_class = UserCreateSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        """Create a new user account with phone number authentication"""
        return super().post(request, *args, **kwargs)
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Return the user data along with a success message
        return Response(
            {
                "message": "User registered successfully. You can now log in with your phone number and password.",
                "user": UserSerializer(user).data
            },
            status=status.HTTP_201_CREATED
        )
    
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
        serializer = StoreSerializer(stores, many=True, context={'request': request})
        return Response(serializer.data)
    
    

class CheckStaffUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        if request.user.is_staff and request.user.user_type == 'ADMIN':
            return Response({'is_staff': True})
        return Response({'is_staff': False})


class CheckDriverUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    

    def get(self, request):
        if request.user.is_staff and request.user.driver_profile and request.user.user_type == 'DRIVER':
            return Response({'is_driver': True})
        return Response({'is_driver': False})


class CitiesView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        cities = City.objects.filter(is_active=True)
        serializer = CitySerializer(cities, many=True)
        return Response(serializer.data)
    
class DriverPaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        driver_payments = DriverPayment.objects.filter(driver=request.user)
        serializer = DriverPaymentSerializer(driver_payments, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        serializer = DriverPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    

class StaffAssociatedUsersView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        # check the user is staff
        if not request.user.is_staff:
            return Response(
                {'error': 'Only staff members can access this endpoint'},
                status=status.HTTP_403_FORBIDDEN
            )
            
        # Get staff_id from query params or use current user's ID
        staff_id = request.query_params.get('staff_id')
        if not staff_id:
            staff_id = request.user.id
            
        try:
            # Get staff user
            staff_user = User.objects.get(id=staff_id)
            if not staff_user.is_staff:
                return Response(
                    {'error': 'The specified user is not a staff member'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # Get unique users from shipments
            users = User.objects.filter(shipments__staff=staff_user).distinct()
            
            # Annotate users with shipment counts
            users = users.annotate(
                total_shipments=Count('shipments', filter=Q(shipments__staff=staff_user)),
                active_shipments=Count('shipments', filter=Q(shipments__staff=staff_user, shipments__status__in=['PENDING', 'PROCESSING', 'IN_TRANSIT']))
            )
            
            # Serialize users
            user_serializer = UserSerializer(users, many=True)
            
            return Response({
                'message': f'Found {users.count()} users associated with staff member',
                'users': user_serializer.data
            })
            
        except User.DoesNotExist:
            return Response(
                {'error': 'Staff user not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"Error in StaffAssociatedUsersView: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )   
        
       

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

    def patch(self, request, ticket_number):
        ticket = self.get_object(ticket_number)
        if ticket is None:
            return Response({'detail': 'Ticket not found or access denied.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = SupportTicketSerializer(ticket, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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