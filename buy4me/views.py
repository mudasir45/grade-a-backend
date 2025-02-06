from django.shortcuts import render
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema, OpenApiParameter
from .models import Buy4MeRequest, Buy4MeItem
from .serializers import (
    Buy4MeRequestSerializer,
    Buy4MeRequestCreateSerializer,
    Buy4MeItemSerializer
)

# Create your views here.

@extend_schema(tags=['buy4me'])
class Buy4MeRequestViewSet(viewsets.ModelViewSet):
    serializer_class = Buy4MeRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Optimize queryset with prefetch_related for items
        Filter requests based on user role
        """
        queryset = Buy4MeRequest.objects.prefetch_related(
            Prefetch('items', queryset=Buy4MeItem.objects.order_by('created_at'))
        )
        
        user = self.request.user
        if not user.is_staff:
            queryset = queryset.filter(user=user)
        
        return queryset.order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'create':
            return Buy4MeRequestCreateSerializer
        return Buy4MeRequestSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @extend_schema(
        summary="Update request status",
        description="Update the status of a Buy4Me request"
    )
    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        instance = self.get_object()
        new_status = request.data.get('status')
        
        if new_status not in dict(Buy4MeRequest.Status.choices):
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )

        instance.status = new_status
        instance.save()
        return Response(self.get_serializer(instance).data)

@extend_schema(tags=['buy4me'])
class Buy4MeItemViewSet(viewsets.ModelViewSet):
    serializer_class = Buy4MeItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Buy4MeItem.objects.filter(
            buy4me_request_id=self.kwargs['request_pk']
        )

    def perform_create(self, serializer):
        buy4me_request = Buy4MeRequest.objects.get(
            id=self.kwargs['request_pk']
        )
        serializer.save(buy4me_request=buy4me_request)
        buy4me_request.calculate_total_cost()
