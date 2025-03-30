# Driver Panel Documentation

## Overview

The Driver Panel is a dedicated interface for delivery drivers in the Grade-A Express system. It provides functionality for managing deliveries, tracking earnings, and updating shipment statuses. This document outlines the complete implementation details for both backend APIs and frontend components.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Backend API Endpoints](#backend-api-endpoints)
3. [Frontend Implementation](#frontend-implementation)
4. [Authentication & Authorization](#authentication--authorization)
5. [Data Models](#data-models)
6. [Error Handling](#error-handling)
7. [Testing Guidelines](#testing-guidelines)

## Architecture Overview

### Tech Stack

- **Backend**: Django REST Framework
- **Frontend**: Next.js 14 with TypeScript
- **Styling**: TailwindCSS
- **State Management**: React Query / TanStack Query
- **Authentication**: JWT with HTTP-only cookies

### Key Features

- Driver Dashboard with real-time statistics
- Shipment and Buy4Me request management
- Status updates with location tracking
- Earnings tracking and commission calculation
- Profile management
- Bulk payment processing for shipments and Buy4Me requests

## Backend API Endpoints

### 1. Driver Dashboard

**Endpoint**: `GET /api/driver/dashboard/`
**Permission**: Authenticated Driver

**Response**:

```json
{
  "driver_profile": {
    "id": "string",
    "user": {
      "email": "string",
      "username": "string"
    },
    "vehicle_type": "string",
    "is_active": boolean,
    "commission_rate": "decimal",
    "total_deliveries": number,
    "total_earnings": "decimal"
  },
  "pending_deliveries": {
    "shipments": number,
    "buy4me": number,
    "total": number
  },
  "earnings_today": "decimal",
  "recent_commissions": [
    {
      "id": "string",
      "delivery_type": "SHIPMENT|BUY4ME",
      "amount": "decimal",
      "earned_at": "datetime",
      "description": "string"
    }
  ]
}
```

**Error Cases**:

- 404: Driver profile not found
- 401: Unauthorized
- 403: Not a driver

### 2. Shipment List

**Endpoint**: `GET /api/driver/shipments/`
**Permission**: Authenticated Driver

**Query Parameters**:

- `status`: Filter by shipment status
- `active_only`: Boolean to show only active shipments

**Response**:

```json
[
  {
    "id": "string",
    "tracking_number": "string",
    "status": "string",
    "current_location": "string",
    "pickup_address": "string",
    "delivery_address": "string",
    "created_at": "datetime",
    "total_cost": "decimal"
  }
]
```

### 3. Buy4Me List

**Endpoint**: `GET /api/driver/buy4me/`
**Permission**: Authenticated Driver

**Query Parameters**:

- `status`: Filter by request status
- `active_only`: Boolean to show only active requests

**Response**: Similar to Shipment List with Buy4Me specific fields

### 4. Shipment Status Update

**Endpoint**: `POST /api/driver/shipments/{shipment_id}/update/`
**Permission**: Authenticated Driver assigned to shipment

**Request Body**:

```json
{
  "status_location_id": "integer",
  "custom_description": "string (optional)"
}
```

**Response**:

```json
{
  "shipment": {
    // Updated shipment details
  },
  "message": "string"
}
```

**Error Cases**:

- 404: Shipment or status location not found
- 403: Not authorized for this shipment
- 400: Invalid status location

### 5. Buy4Me Status Update

**Endpoint**: `POST /api/driver/buy4me/{request_id}/update/`
**Permission**: Authenticated Driver assigned to request

**Request Body**:

```json
{
  "status": "string",
  "notes": "string (optional)"
}
```

### 6. Driver Earnings

**Endpoint**: `GET /api/driver/earnings/`
**Permission**: Authenticated Driver

**Query Parameters**:

- `start_date`: YYYY-MM-DD
- `end_date`: YYYY-MM-DD

**Response**:

```json
{
  "total_earnings": "decimal",
  "shipment_earnings": "decimal",
  "buy4me_earnings": "decimal",
  "commissions": [
    {
      "id": "string",
      "delivery_type": "string",
      "amount": "decimal",
      "earned_at": "datetime",
      "description": "string"
    }
  ]
}
```

### 7. Bulk Payment Processing

**Endpoint**: `POST /api/driver/bulk-payments/`
**Permission**: Authenticated Driver

**Description**: This endpoint allows drivers to submit multiple shipment or Buy4Me request IDs at once to create payment records and update payment statuses. It's designed for efficiently processing collections made by drivers in the field.

**Request Body**:

```json
{
  "payment_for": "SHIPMENT|BUY4ME",
  "request_ids": ["array of request IDs"]
}
```

**Field Descriptions**:

- `payment_for`: Required. Specifies whether the payment is for shipments or Buy4Me requests. Must be either "SHIPMENT" or "BUY4ME".
- `request_ids`: Required. Array of IDs for the shipments or Buy4Me requests to be processed.

**Response**:

```json
{
  "message": "Successfully created X payments",
  "payments_created": "integer",
  "total_amount": "decimal",
  "failed_requests": [
    {
      "id": "string",
      "reason": "string"
    }
  ]
}
```

**Response Fields**:

- `message`: Summary of the operation result
- `payments_created`: Number of successful payment records created
- `total_amount`: Sum of all payment amounts created
- `failed_requests`: Array of request IDs that could not be processed, with reasons

**Processing Details**:

- The endpoint creates a payment record for each valid request ID
- Payment amount is taken from the request's `total_cost` field
- Payment status is updated to "COD_PAID" after successful creation
- Each payment gets an auto-generated payment ID with prefix "AUTO-"
- Requests that already have payments or are not associated with the driver are reported as failed

**Error Cases**:

- 400: Invalid input data or no valid requests found
- 401: Unauthorized
- 403: Not a driver

**Example Request**:

```json
// For shipments
{
  "payment_for": "SHIPMENT",
  "request_ids": ["SRS123456", "SRS789012", "SRS345678"]
}

// For Buy4Me requests
{
  "payment_for": "BUY4ME",
  "request_ids": ["BMR123456", "BMR789012"]
}
```

**Example Response**:

```json
{
  "message": "Successfully created 2 payments",
  "payments_created": 2,
  "total_amount": 150.0,
  "failed_requests": [
    {
      "id": "SRS345678",
      "reason": "Not found, already has payment, or not associated with this driver"
    }
  ]
}
```

## Frontend Implementation

### Page Structure

```
/app
  /driver
    /dashboard
      page.tsx
      loading.tsx
      error.tsx
    /shipments
      page.tsx
      [id]
        page.tsx
    /buy4me
      page.tsx
      [id]
        page.tsx
    /earnings
      page.tsx
    /profile
      page.tsx
    /payments
      page.tsx
```

### Component Architecture

#### 1. Dashboard Components

```typescript
// DashboardStats.tsx
interface DashboardStatsProps {
  pendingDeliveries: {
    shipments: number;
    buy4me: number;
    total: number;
  };
  earningsToday: number;
}

// RecentCommissions.tsx
interface Commission {
  id: string;
  deliveryType: "SHIPMENT" | "BUY4ME";
  amount: number;
  earnedAt: string;
  description: string;
}
```

#### 2. Shipment Management

```typescript
// ShipmentList.tsx
interface ShipmentFilters {
  status?: string;
  activeOnly: boolean;
}

// ShipmentStatusUpdate.tsx
interface StatusUpdateForm {
  statusLocationId: number;
  customDescription?: string;
}
```

#### 3. Bulk Payment Components

```typescript
// BulkPaymentForm.tsx
interface BulkPaymentFormProps {
  paymentType: "SHIPMENT" | "BUY4ME";
  onSubmit: (data: BulkPaymentData) => Promise<void>;
  isLoading: boolean;
}

interface BulkPaymentData {
  payment_for: "SHIPMENT" | "BUY4ME";
  request_ids: string[];
}

// PaymentResultsDisplay.tsx
interface PaymentResultsProps {
  results: {
    message: string;
    payments_created: number;
    total_amount: number;
    failed_requests: Array<{
      id: string;
      reason: string;
    }>;
  } | null;
}
```

### State Management

Use React Query for API data management:

```typescript
// hooks/useDriverDashboard.ts
export const useDriverDashboard = () => {
  return useQuery({
    queryKey: ["driverDashboard"],
    queryFn: fetchDriverDashboard,
    refetchInterval: 30000, // Refresh every 30 seconds
  });
};

// hooks/useShipments.ts
export const useShipments = (filters: ShipmentFilters) => {
  return useQuery({
    queryKey: ["shipments", filters],
    queryFn: () => fetchShipments(filters),
  });
};

// hooks/useBulkPayment.ts
export const useBulkPayment = () => {
  return useMutation({
    mutationFn: (data: BulkPaymentData) =>
      api.post("/driver/bulk-payments/", data).then((res) => res.data),
  });
};
```

### UI Components

#### 1. Dashboard Layout

```typescript
// components/driver/DashboardLayout.tsx
interface DashboardLayoutProps {
  children: React.ReactNode;
}
```

Implement with a responsive sidebar navigation:

- Dashboard overview
- Active deliveries
- Earnings section
- Payment processing section
- Profile settings

#### 2. Status Update Modal

```typescript
// components/driver/StatusUpdateModal.tsx
interface StatusUpdateModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUpdate: (data: StatusUpdateForm) => Promise<void>;
  availableStatuses: StatusLocation[];
}
```

#### 3. Bulk Payment UI

```typescript
// components/driver/BulkPaymentInterface.tsx
interface BulkPaymentInterfaceProps {
  initialType?: "SHIPMENT" | "BUY4ME";
}
```

The bulk payment interface should include:

- Radio buttons to select payment type (Shipment or Buy4Me)
- Multiple selection interface for available requests
- Summary of selected items and total amount
- Submit button with loading state
- Results display with success and failure information

### Styling Guidelines

Use TailwindCSS with a consistent color scheme:

```typescript
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#f0f9ff",
          // ... other shades
          900: "#0c4a6e",
        },
        secondary: {
          // ... define secondary colors
        },
      },
    },
  },
};
```

## Authentication & Authorization

### JWT Implementation

- Store JWT in HTTP-only cookies
- Include refresh token mechanism
- Handle token expiration gracefully

### Route Protection

```typescript
// middleware.ts
export function middleware(request: NextRequest) {
  // Verify driver role and authentication
}
```

## Error Handling

### Backend Errors

- Use consistent error response format
- Include appropriate HTTP status codes
- Provide detailed error messages for debugging

### Frontend Error Boundaries

```typescript
// components/ErrorBoundary.tsx
class ErrorBoundary extends React.Component<Props, State> {
  // Implement error boundary logic
}
```

## Testing Guidelines

### Backend Tests

- Unit tests for models and serializers
- Integration tests for API endpoints
- Permission testing

### Frontend Tests

- Component testing with React Testing Library
- E2E testing with Cypress
- API mocking with MSW

## Development Setup

### Environment Variables

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api
NEXT_PUBLIC_GOOGLE_MAPS_KEY=your_key_here
```

### API Client Setup

```typescript
// lib/api.ts
export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  withCredentials: true,
});
```

## Deployment Considerations

### Backend

- Configure CORS properly
- Set up proper security headers
- Enable rate limiting

### Frontend

- Implement proper caching strategies
- Configure CDN for static assets
- Set up proper build optimization

## Mobile Responsiveness

Implement responsive design for all screen sizes:

- Mobile-first approach
- Breakpoint system
- Touch-friendly interfaces

## Performance Optimization

### Frontend

- Implement lazy loading
- Use proper image optimization
- Minimize bundle size

### Backend

- Implement proper database indexing
- Cache frequently accessed data
- Optimize database queries

```

```
