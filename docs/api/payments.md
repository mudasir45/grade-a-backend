# Payments & Invoices API Documentation

## Base URL
```
https://api.example.com/api/
```

## Authentication
All payment endpoints require JWT authentication.
```http
Authorization: Bearer <token>
```

## TypeScript Common Interfaces

```typescript
// Payment status types
type PaymentStatus = 
  | 'PENDING'     // Payment initiated but not completed
  | 'PROCESSING'  // Payment being processed
  | 'COMPLETED'   // Payment successfully completed
  | 'FAILED'      // Payment failed
  | 'REFUNDED'    // Payment refunded
  | 'CANCELLED';  // Payment cancelled

// Payment method types
type PaymentMethod =
  | 'CREDIT_CARD'  // Credit/Debit card
  | 'BANK_TRANSFER' // Bank transfer
  | 'WALLET'       // Digital wallet
  | 'CASH'         // Cash on delivery
  | 'CRYPTO';      // Cryptocurrency

// Invoice status types
type InvoiceStatus =
  | 'DRAFT'      // Invoice created but not finalized
  | 'ISSUED'     // Invoice issued to customer
  | 'PAID'       // Invoice fully paid
  | 'OVERDUE'    // Invoice past due date
  | 'CANCELLED'  // Invoice cancelled
  | 'VOID';      // Invoice voided

interface PaymentDetails {
  amount: number;           // Payment amount
  currency: string;         // 3-letter currency code (e.g., "USD")
  method: PaymentMethod;    // Payment method used
  status: PaymentStatus;    // Current payment status
  reference: string;        // Unique payment reference
  description?: string;     // Payment description
}

interface InvoiceItem {
  description: string;      // Item description
  quantity: number;         // Quantity
  unit_price: number;      // Price per unit
  amount: number;          // Total amount (quantity * unit_price)
  tax_rate?: number;       // Tax rate as percentage
  tax_amount?: number;     // Calculated tax amount
}
```

## Endpoints

### 1. Create Payment

Create a new payment for a shipment or invoice.

#### Request
```http
POST /payments/
```

#### Request Type
```typescript
interface CreatePaymentRequest {
  // Required fields
  amount: number;           // Payment amount
  currency: string;         // Currency code (e.g., "USD")
  method: PaymentMethod;    // Payment method
  description?: string;     // Payment description
  
  // Reference fields (at least one required)
  shipment_id?: string;     // Shipment ID if paying for shipment
  invoice_id?: string;      // Invoice ID if paying for invoice
  
  // Payment method specific fields
  card?: {
    number: string;         // Card number
    expiry_month: string;   // MM
    expiry_year: string;    // YYYY
    cvv: string;           // Security code
    holder_name: string;    // Card holder name
  };
  bank_transfer?: {
    account_name: string;   // Account holder name
    account_number: string; // Account number
    bank_code: string;      // Bank routing code
  };
  wallet?: {
    wallet_type: string;    // e.g., "Apple Pay", "Google Pay"
    token: string;         // Wallet payment token
  };
}
```

#### Success Response (201 Created)
```typescript
interface PaymentResponse extends BaseResponse {
  data: {
    id: string;                    // Payment ID
    reference: string;             // Payment reference number
    amount: number;                // Payment amount
    currency: string;              // Currency code
    status: PaymentStatus;         // Payment status
    method: PaymentMethod;         // Payment method used
    description?: string;          // Payment description
    
    // Related resources
    shipment?: {
      id: string;
      tracking_number: string;
    };
    invoice?: {
      id: string;
      number: string;
    };
    
    // Payment processing details
    processor_reference?: string;   // Payment processor reference
    authorization_code?: string;    // Authorization code
    
    // Timestamps
    created_at: string;            // ISO 8601 date
    updated_at: string;            // ISO 8601 date
    completed_at?: string;         // ISO 8601 date
  };
}
```

### 2. Create Invoice

Generate a new invoice.

#### Request
```http
POST /invoices/
```

#### Request Type
```typescript
interface CreateInvoiceRequest {
  // Customer information
  customer: {
    name: string;
    email: string;
    address: string;
    tax_id?: string;       // VAT/Tax ID if applicable
  };
  
  // Invoice items
  items: InvoiceItem[];
  
  // Optional fields
  currency: string;        // Default: "USD"
  due_date?: string;      // ISO 8601 date
  notes?: string;         // Invoice notes
  shipment_id?: string;   // Related shipment
  
  // Tax settings
  tax_inclusive: boolean;  // Whether prices include tax
  tax_rate?: number;      // Overall tax rate
}
```

#### Success Response (201 Created)
```typescript
interface InvoiceResponse extends BaseResponse {
  data: {
    id: string;                // Invoice ID
    number: string;            // Invoice number (e.g., "INV-2025-0001")
    status: InvoiceStatus;     // Invoice status
    
    // Customer details
    customer: {
      name: string;
      email: string;
      address: string;
      tax_id?: string;
    };
    
    // Financial details
    currency: string;
    subtotal: number;         // Sum of items before tax
    tax_amount: number;       // Total tax amount
    total: number;            // Final total including tax
    
    // Items breakdown
    items: InvoiceItem[];
    
    // Payment status
    amount_paid: number;      // Total amount paid
    amount_due: number;       // Remaining amount to pay
    
    // Dates
    issue_date: string;       // ISO 8601 date
    due_date?: string;        // ISO 8601 date
    created_at: string;       // ISO 8601 date
    updated_at: string;       // ISO 8601 date
  };
}
```

### 3. Get Payment Status

Check the status of a payment.

#### Request
```http
GET /payments/{payment_id}/
```

#### Response Type
```typescript
interface PaymentStatusResponse extends BaseResponse {
  data: {
    id: string;
    status: PaymentStatus;
    amount: number;
    currency: string;
    reference: string;
    processor_status?: string;    // Payment processor status
    failure_reason?: string;      // Reason if payment failed
    refund_status?: string;       // Refund status if applicable
  };
}
```

### 4. List Payments

Get a list of payments with optional filters.

#### Request
```http
GET /payments/
```

#### Query Parameters
```typescript
interface PaymentListParams {
  page?: number;            // Page number
  page_size?: number;       // Items per page
  status?: PaymentStatus;   // Filter by status
  method?: PaymentMethod;   // Filter by payment method
  date_from?: string;       // ISO 8601 date
  date_to?: string;         // ISO 8601 date
  reference?: string;       // Search by reference
}
```

## Error Responses

Payment-specific error types:

```typescript
interface PaymentError extends ErrorResponse {
  code: 
    | 'INSUFFICIENT_FUNDS'
    | 'CARD_DECLINED'
    | 'INVALID_CARD'
    | 'EXPIRED_CARD'
    | 'PROCESSING_ERROR'
    | 'INVALID_AMOUNT'
    | 'CURRENCY_NOT_SUPPORTED'
    | 'METHOD_NOT_SUPPORTED';
  
  processor_message?: string;  // Message from payment processor
  transaction_id?: string;     // Failed transaction ID
}
```

Example error responses:

```json
// 400 Bad Request - Card Declined
{
  "success": false,
  "error": "Payment card was declined",
  "code": "CARD_DECLINED",
  "processor_message": "Insufficient funds",
  "transaction_id": "tx_123456789"
}

// 400 Bad Request - Invalid Amount
{
  "success": false,
  "error": "Invalid payment amount",
  "code": "INVALID_AMOUNT",
  "details": {
    "minimum": 1.00,
    "maximum": 50000.00,
    "currency": "USD"
  }
}
```

## Notes

1. Payment Processing:
   - All amounts are in minor units (cents)
   - Supported currencies: USD, EUR, GBP, AED
   - Card numbers should be PCI-DSS compliant
   - Sensitive data is never logged

2. Security:
   - All endpoints use HTTPS
   - Card data is tokenized
   - 3D Secure is supported
   - Rate limiting applies

3. Invoicing:
   - Invoice numbers are auto-generated
   - Tax calculations are automatic
   - Multiple items per invoice
   - Partial payments supported

4. Status Flows:
   ```
   Payment:
   PENDING → PROCESSING → COMPLETED
           ↘ FAILED
           ↘ CANCELLED
   COMPLETED → REFUNDED

   Invoice:
   DRAFT → ISSUED → PAID
         ↘ CANCELLED
         ↘ VOID
   ISSUED → OVERDUE
   ```

Would you like me to add more details or explain any part further? 