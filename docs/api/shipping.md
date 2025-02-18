# Shipping API Documentation

## Base URL
```
https://api.example.com/api/
```

## Authentication
All endpoints except tracking require JWT authentication.
```http
Authorization: Bearer <token>
```

## TypeScript Common Interfaces

```typescript
// Common response types used across endpoints
interface BaseResponse {
  success: boolean;
  message?: string;
  error?: string;
}

interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// Shipping status types
type ShipmentStatus = 
  | 'PENDING'    // Initial state when created
  | 'PROCESSING' // Being processed at facility
  | 'IN_TRANSIT' // In transit to destination
  | 'DELIVERED'  // Successfully delivered
  | 'CANCELLED'; // Cancelled by user/admin

// Common shipping types
interface Address {
  name: string;      // Full name
  email: string;     // Email address
  phone: string;     // Phone number with country code
  address: string;   // Full address
  country_id: string; // Country ID (e.g., "AE123")
}

interface Dimensions {
  length: number; // in centimeters
  width: number;  // in centimeters
  height: number; // in centimeters
}

interface TrackingUpdate {
  status: ShipmentStatus;
  location: string;
  timestamp: string; // ISO 8601 format
  description: string;
}
```

## Endpoints

### 1. Calculate Shipping Rates

Calculate shipping rates for a package before creating a shipment.

#### Request
```http
POST /shipping-rates/calculate/
```

#### Request Type
```typescript
interface CalculateRateRequest {
  origin_country: string;      // Country ID
  destination_country: string; // Country ID
  weight: number;             // Weight in kg
  length: number;             // Length in cm
  width: number;              // Width in cm
  height: number;             // Height in cm
  service_type: string;      // Service Type ID
}
```

#### Success Response (200 OK)
```typescript
interface CalculateRateResponse extends BaseResponse {
  data: {
    route: {
      origin: {
        id: string;
        name: string;    // Country name
        code: string;    // 2-letter country code
      };
      destination: {
        id: string;
        name: string;
        code: string;
      };
      zone: {
        id: string;
        name: string;    // Zone name (e.g., "UAE-India Zone")
      };
    };
    service: {
      id: string;
      name: string;           // Service name (e.g., "Express")
      delivery_time: string;  // e.g., "2-3 business days"
      price: number;         // Service charge
    };
    weight_calculation: {
      dimensions: {
        length: number;
        width: number;
        height: number;
        volume: number;      // length * width * height
      };
      actual_weight: number;
      dimensional_factor: number;
      volumetric_weight: number;
      chargeable_weight: number;
      weight_calculation: 'Actual' | 'Volumetric';
    };
    rate_details: {
      base_rate: number;     // Base shipping cost
      per_kg_rate: number;   // Cost per kg
      weight_charge: number; // per_kg_rate * chargeable_weight
    };
    cost_breakdown: {
      base_cost: number;    // Base cost for shipping
      service_charge: number; // Service type charge
      additional_charges: Array<{
        name: string;       // Charge name
        type: 'Fixed' | 'Percentage';
        value: number;      // Rate/Percentage
        amount: number;     // Calculated amount
        description: string;
      }>;
      total_additional: number; // Sum of additional charges
      total_cost: number;      // Final total cost
    };
  };
}
```

### 2. Create Shipment

#### Request
```http
POST /shipments/
```

#### Request Type
```typescript
interface CreateShipmentRequest {
  // Sender details
  sender_name: string;
  sender_email: string;
  sender_phone: string;
  sender_address: string;
  sender_country: string; // Country ID

  // Recipient details
  recipient_name: string;
  recipient_email: string;
  recipient_phone: string;
  recipient_address: string;
  recipient_country: string; // Country ID

  // Package details
  package_type: string;    // e.g., "Parcel", "Document"
  weight: number;          // in kg
  length: number;          // in cm
  width: number;           // in cm
  height: number;          // in cm
  description: string;     // Package contents
  declared_value: number;  // Value in USD

  // Service options
  service_type: string;    // Service Type ID
  insurance_required: boolean;
  signature_required: boolean;

  notes?: string;         // Optional notes
}
```

#### Success Response (201 Created)
```typescript
interface ShipmentResponse extends BaseResponse {
  data: {
    id: string;                    // Shipment ID
    tracking_number: string;       // Unique tracking number
    status: ShipmentStatus;        // Current status
    current_location: string;      // Current location
    estimated_delivery?: string;   // ISO 8601 date

    // Sender & Recipient info
    sender: Address;
    recipient: Address;

    // Package info
    package: {
      type: string;
      weight: number;
      dimensions: Dimensions;
      description: string;
      declared_value: number;
    };

    // Service info
    service: {
      type: string;
      insurance_required: boolean;
      signature_required: boolean;
    };

    // Cost breakdown
    costs: {
      base_rate: number;
      per_kg_rate: number;
      weight_charge: number;
      service_charge: number;
      total_additional_charges: number;
      total_cost: number;
    };

    tracking_history: TrackingUpdate[];
    
    created_at: string;    // ISO 8601 date
    updated_at: string;    // ISO 8601 date
  };
}
```

### 3. Track Shipment

#### Request
```http
GET /shipments/track/{tracking_number}/
```

#### Response Type
```typescript
interface TrackingResponse extends BaseResponse {
  data: {
    tracking_number: string;
    status: ShipmentStatus;
    current_location: string;
    estimated_delivery?: string; // ISO 8601 date

    shipment_details: {
      origin: {
        name: string;
        country: string;
      };
      destination: {
        name: string;
        country: string;
      };
      service: string;
      package: {
        weight: number;
        dimensions: Dimensions;
      };
    };

    tracking_history: TrackingUpdate[];
  };
}
```

### 4. List Shipments

#### Request
```http
GET /shipments/
```

#### Query Parameters
```typescript
interface ShipmentListParams {
  page?: number;           // Page number for pagination
  page_size?: number;      // Items per page
  status?: ShipmentStatus; // Filter by status
  search?: string;         // Search tracking number/recipient
}
```

#### Response Type
```typescript
interface ShipmentListResponse extends PaginatedResponse<ShipmentResponse['data']> {
  // Inherits pagination fields and adds results array
}
```

## Error Responses

All endpoints may return these error types:

```typescript
interface ValidationError {
  field_name: string[];  // Array of error messages for the field
}

interface ErrorResponse {
  success: false;
  error: string;
  validation_errors?: {
    [key: string]: ValidationError;
  };
  code?: string;        // Error code for specific errors
  details?: unknown;    // Additional error details
}
```

Example error responses:

```json
// 400 Bad Request - Validation Error
{
  "success": false,
  "error": "Validation failed",
  "validation_errors": {
    "weight": ["Ensure this value is greater than 0."],
    "sender_email": ["Enter a valid email address."]
  }
}

// 404 Not Found
{
  "success": false,
  "error": "Resource not found",
  "code": "NOT_FOUND"
}

// 401 Unauthorized
{
  "success": false,
  "error": "Authentication credentials were not provided."
}
```

## Notes

1. All numeric values:
   - Weights: in kilograms, decimal to 2 places
   - Dimensions: in centimeters, decimal to 2 places
   - Money: in USD, decimal to 2 places

2. Dates and Times:
   - All timestamps are in ISO 8601 format
   - All times are in UTC
   - Format: "YYYY-MM-DDTHH:mm:ssZ"

3. IDs and Codes:
   - Country IDs: 2-letter code + numeric (e.g., "AE123")
   - Tracking numbers: "TRK" + 9 digits
   - Shipment IDs: "SHP" + 6 digits

4. Status Transitions:
   ```
   PENDING → PROCESSING → IN_TRANSIT → DELIVERED
                       ↘ CANCELLED
   ```

Would you like me to add more details or explain any part further?