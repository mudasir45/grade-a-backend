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
        elif self.action in ['update', 'partial_update']:
            return Buy4MeRequestUpdateSerializer
        return Buy4MeRequestSerializer

    def perform_create(self, serializer):
        """
        Create a Buy4Me request with the current user and set city delivery charge if city is provided
        """
        # Create the request with the current user
        instance = serializer.save(user=self.request.user)
        
        # If a city was provided, the save method in the model will already set the 
        # city_delivery_charge based on the city, but we need to calculate the total cost
        if instance.city:
            instance.calculate_total_cost()
        
        return instance

    def perform_update(self, serializer):
        """
        Update a Buy4Me request and handle city changes
        """
        # Get the old city (if any) before saving
        instance = self.get_object()
        old_city = instance.city
        
        # Save the updated instance
        instance = serializer.save()
        
        # If city has changed, update the city_delivery_charge and recalculate total cost
        if instance.city != old_city:
            # The save method in the model will set the city_delivery_charge
            # based on the new city, but we need to recalculate the total cost
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
        