from django.conf import settings
import stripe
from .models import Payment, Invoice

stripe.api_key = settings.STRIPE_SECRET_KEY

class PaymentService:
    def initiate_payment(self, invoice, payment_method, return_url=None):
        if payment_method == Payment.PaymentMethod.STRIPE:
            return self._initiate_stripe_payment(invoice, return_url)
        elif payment_method == Payment.PaymentMethod.PAYPAL:
            return self._initiate_paypal_payment(invoice, return_url)
        # Add other payment methods as needed
        
    def _initiate_stripe_payment(self, invoice, return_url):
        try:
            payment_intent = stripe.PaymentIntent.create(
                amount=int(invoice.total * 100),  # Convert to cents
                currency='usd',
                metadata={
                    'invoice_id': invoice.id,
                    'user_id': invoice.user.id
                }
            )
            
            # Create payment record
            payment = Payment.objects.create(
                invoice=invoice,
                amount=invoice.total,
                payment_method=Payment.PaymentMethod.STRIPE,
                transaction_id=payment_intent.id,
                payment_details={
                    'client_secret': payment_intent.client_secret
                }
            )
            
            return {
                'payment_id': payment.id,
                'client_secret': payment_intent.client_secret,
                'public_key': settings.STRIPE_PUBLISHABLE_KEY
            }
            
        except stripe.error.StripeError as e:
            # Handle stripe errors
            return {
                'error': str(e)
            }
    
    def _initiate_paypal_payment(self, invoice, return_url):
        # Implement PayPal payment initiation
        pass
    
    def verify_payment(self, payment):
        if payment.payment_method == Payment.PaymentMethod.STRIPE:
            return self._verify_stripe_payment(payment)
        # Add other payment methods
    
    def _verify_stripe_payment(self, payment):
        try:
            payment_intent = stripe.PaymentIntent.retrieve(
                payment.transaction_id
            )
            
            if payment_intent.status == 'succeeded':
                payment.status = Payment.Status.COMPLETED
                payment.save()
                
                # Update invoice status
                payment.invoice.status = Invoice.Status.PAID
                payment.invoice.save()
                
                return {'status': 'success'}
            
            return {'status': payment_intent.status}
            
        except stripe.error.StripeError as e:
            return {'error': str(e)}
    
    def process_refund(self, refund):
        payment = refund.payment
        
        if payment.payment_method == Payment.PaymentMethod.STRIPE:
            return self._process_stripe_refund(refund)
        # Add other payment methods
    
    def _process_stripe_refund(self, refund):
        try:
            stripe_refund = stripe.Refund.create(
                payment_intent=refund.payment.transaction_id,
                amount=int(refund.amount * 100)  # Convert to cents
            )
            
            refund.status = Refund.Status.COMPLETED
            refund.refund_transaction_id = stripe_refund.id
            refund.save()
            
            # Update payment and invoice status
            refund.payment.status = Payment.Status.REFUNDED
            refund.payment.save()
            
            refund.payment.invoice.status = Invoice.Status.REFUNDED
            refund.payment.invoice.save()
            
            return {'status': 'success'}
            
        except stripe.error.StripeError as e:
            return {'error': str(e)} 