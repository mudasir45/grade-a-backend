from rest_framework import serializers
from .models import Invoice, Payment, Refund

class InvoiceSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'user', 'shipment', 'buy4me_request',
            'status', 'status_display', 'due_date',
            'subtotal', 'tax', 'total', 'notes',
            'created_at'
        ]
        read_only_fields = [
            'id', 'user', 'status', 'total',
            'created_at'
        ]

class PaymentSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    payment_method_display = serializers.CharField(
        source='get_payment_method_display',
        read_only=True
    )
    
    class Meta:
        model = Payment
        fields = [
            'id', 'invoice', 'amount', 'payment_method',
            'payment_method_display', 'status', 'status_display',
            'transaction_id', 'payment_details', 'created_at'
        ]
        read_only_fields = [
            'id', 'status', 'transaction_id',
            'payment_details', 'created_at'
        ]

class RefundSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    processed_by_name = serializers.CharField(
        source='processed_by.get_full_name',
        read_only=True
    )
    
    class Meta:
        model = Refund
        fields = [
            'id', 'payment', 'amount', 'reason',
            'status', 'status_display', 'refund_transaction_id',
            'processed_by', 'processed_by_name', 'created_at'
        ]
        read_only_fields = [
            'id', 'status', 'refund_transaction_id',
            'processed_by', 'created_at'
        ]

class PaymentInitiateSerializer(serializers.Serializer):
    invoice_id = serializers.CharField()
    payment_method = serializers.ChoiceField(
        choices=Payment.PaymentMethod.choices
    )
    return_url = serializers.URLField(
        required=False,
        help_text='URL to redirect after payment completion'
    ) 