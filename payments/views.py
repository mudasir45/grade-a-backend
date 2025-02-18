from django.shortcuts import render
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter
from .models import Invoice, Payment, Refund
from .serializers import (
    InvoiceSerializer, PaymentSerializer, RefundSerializer,
    PaymentInitiateSerializer
)
from .services import PaymentService

# Create your views here.

@extend_schema(tags=['payments'])
class InvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Invoice.objects.all()
        return Invoice.objects.filter(user=user)

    @extend_schema(
        summary="Generate PDF",
        description="Generate PDF version of the invoice"
    )
    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        invoice = self.get_object()
        # Add PDF generation logic here
        return Response({'pdf_url': 'url_to_pdf'})

@extend_schema(tags=['payments'])
class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Payment.objects.all()
        return Payment.objects.filter(invoice__user=user)

    @extend_schema(
        summary="Initiate payment",
        request=PaymentInitiateSerializer
    )
    @action(detail=False, methods=['post'])
    def initiate(self, request):
        serializer = PaymentInitiateSerializer(data=request.data)
        if serializer.is_valid():
            invoice = get_object_or_404(
                Invoice, 
                id=serializer.validated_data['invoice_id']
            )
            
            # Check if user has permission to pay this invoice
            if not request.user.is_staff and invoice.user != request.user:
                return Response(
                    {'error': 'Not authorized'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            payment_service = PaymentService()
            result = payment_service.initiate_payment(
                invoice=invoice,
                payment_method=serializer.validated_data['payment_method'],
                return_url=serializer.validated_data.get('return_url')
            )
            
            return Response(result)
            
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    @extend_schema(
        summary="Verify payment",
        description="Verify payment status with payment gateway"
    )
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        payment = self.get_object()
        payment_service = PaymentService()
        result = payment_service.verify_payment(payment)
        return Response(result)

@extend_schema(tags=['payments'])
class RefundViewSet(viewsets.ModelViewSet):
    serializer_class = RefundSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = Refund.objects.all()

    def perform_create(self, serializer):
        serializer.save(processed_by=self.request.user)

    @extend_schema(
        summary="Process refund",
        description="Process the refund through payment gateway"
    )
    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        refund = self.get_object()
        payment_service = PaymentService()
        result = payment_service.process_refund(refund)
        return Response(result)
