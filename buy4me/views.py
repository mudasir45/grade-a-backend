from typing import Any, TypeVar, cast

from django.contrib.auth import get_user_model
from django.db.models import Prefetch
from django.shortcuts import render
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Buy4MeItem, Buy4MeRequest
from .serializers import (Buy4MeItemSerializer, Buy4MeRequestCreateSerializer,
                          Buy4MeRequestSerializer,
                          Buy4MeRequestUpdateSerializer)

User = get_user_model()
T = TypeVar('T')

# Create your views here.

@extend_schema(tags=['buy4me'])
class Buy4MeRequestViewSet(viewsets.ModelViewSet):
    queryset = Buy4MeRequest.objects.all()
    serializer_class = Buy4MeRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return Buy4MeRequestCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return Buy4MeRequestUpdateSerializer
        return Buy4MeRequestSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_queryset(self):
        queryset = super().get_queryset()
        user: User = self.request.user  # type: ignore
        if user.is_staff:
            return queryset
        return queryset.filter(user=self.request.user)

    def perform_update(self, serializer):
        """
        Update a Buy4Me request
        """
        # Save the updated instance
        instance = serializer.save()
        
        # Recalculate total cost
        instance.calculate_total_cost()
        
        return instance

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
        
    def perform_update(self, serializer):
        """Recalculate total cost after item update"""
        serializer.save()
        # Get the parent request and recalculate cost
        buy4me_request = serializer.instance.buy4me_request
        buy4me_request.calculate_total_cost()
        
    def perform_destroy(self, instance):
        """Recalculate total cost after item deletion"""
        # Get the parent request before deleting
        buy4me_request = instance.buy4me_request
        # Delete the item
        instance.delete()
        # Recalculate the cost
        buy4me_request.calculate_total_cost()


class GetActiveBuy4MeRequest(APIView):
    def get(self, request):
        active_request, created = Buy4MeRequest.objects.get_or_create(
            user=request.user,
            status=Buy4MeRequest.Status.DRAFT
        )
        serializer = Buy4MeRequestSerializer(active_request)
        return Response(serializer.data)
        