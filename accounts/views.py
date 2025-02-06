from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from .serializers import UserSerializer, UserCreateSerializer

User = get_user_model()

@extend_schema(tags=['users'])
class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for viewing and editing user instances.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

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