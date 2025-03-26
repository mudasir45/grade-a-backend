# Support Tickets API Documentation

## Overview

The Support Tickets API provides endpoints for managing customer support tickets. Users can create, view, update, and delete their support tickets. The API includes filtering capabilities and proper authentication.

## Authentication

All endpoints require authentication using JWT tokens. Include the token in the Authorization header:

```
Authorization: Bearer <your_jwt_token>
```

## Endpoints

### 1. List and Create Tickets

```http
GET/POST /api/accounts/tickets/
```

#### GET /api/accounts/tickets/

Lists all support tickets for the authenticated user with optional filtering.

**Query Parameters:**

- `status` (string): Filter by ticket status (OPEN, IN_PROGRESS, RESOLVED, CLOSED)
- `category` (string): Filter by ticket category (SHIPPING, PAYMENT, TRACKING, DELIVERY, OTHER)
- `assigned_to` (number): Filter by assigned staff member ID
- `created_at_min` (datetime): Filter tickets created after this date
- `created_at_max` (datetime): Filter tickets created before this date

**Response (200 OK):**

```json
[
  {
    "ticket_number": "TKT123456789",
    "subject": "Shipping Delay",
    "message": "My shipment is delayed...",
    "category": "SHIPPING",
    "status": "OPEN",
    "user": 1,
    "assigned_to": null,
    "shipment": null,
    "created_at": "2024-03-26T10:00:00Z",
    "updated_at": "2024-03-26T10:00:00Z",
    "resolved_at": null,
    "comments": []
  }
]
```

#### POST /api/accounts/tickets/

Creates a new support ticket.

**Request Body:**

```json
{
  "subject": "Shipping Delay",
  "message": "My shipment is delayed...",
  "category": "SHIPPING"
}
```

**Required Fields:**

- `subject` (string): Brief description of the issue
- `message` (string): Detailed description of the issue
- `category` (string): One of the predefined categories

**Response (201 Created):**

```json
{
  "ticket_number": "TKT123456789",
  "subject": "Shipping Delay",
  "message": "My shipment is delayed...",
  "category": "SHIPPING",
  "status": "OPEN",
  "user": 1,
  "assigned_to": null,
  "shipment": null,
  "created_at": "2024-03-26T10:00:00Z",
  "updated_at": "2024-03-26T10:00:00Z",
  "resolved_at": null,
  "comments": []
}
```

### 2. Ticket Detail, Update, and Delete

```http
GET/PATCH/PUT/DELETE /api/accounts/tickets/<ticket_number>/
```

#### GET /api/accounts/tickets/<ticket_number>/

Retrieves details of a specific ticket.

**Response (200 OK):**

```json
{
  "ticket_number": "TKT123456789",
  "subject": "Shipping Delay",
  "message": "My shipment is delayed...",
  "category": "SHIPPING",
  "status": "OPEN",
  "user": 1,
  "assigned_to": null,
  "shipment": null,
  "created_at": "2024-03-26T10:00:00Z",
  "updated_at": "2024-03-26T10:00:00Z",
  "resolved_at": null,
  "comments": []
}
```

#### PATCH/PUT /api/accounts/tickets/<ticket_number>/

Updates a specific ticket. Both PATCH and PUT methods support partial updates.

**Request Body:**

```json
{
  "subject": "Updated Subject",
  "message": "Updated message...",
  "category": "PAYMENT",
  "status": "IN_PROGRESS"
}
```

**Response (200 OK):**

```json
{
  "ticket_number": "TKT123456789",
  "subject": "Updated Subject",
  "message": "Updated message...",
  "category": "PAYMENT",
  "status": "IN_PROGRESS",
  "user": 1,
  "assigned_to": null,
  "shipment": null,
  "created_at": "2024-03-26T10:00:00Z",
  "updated_at": "2024-03-26T10:30:00Z",
  "resolved_at": null,
  "comments": []
}
```

#### DELETE /api/accounts/tickets/<ticket_number>/

Deletes a specific ticket.

**Response (204 No Content):**
Empty response with status code 204.

## Error Responses

### 400 Bad Request

```json
{
  "detail": "Invalid data provided",
  "field_errors": {
    "subject": ["This field is required."],
    "category": ["Invalid category."]
  }
}
```

### 401 Unauthorized

```json
{
  "detail": "Authentication credentials were not provided."
}
```

### 403 Forbidden

```json
{
  "detail": "You do not have permission to perform this action."
}
```

### 404 Not Found

```json
{
  "detail": "Ticket not found or access denied."
}
```

## Ticket Categories

- `SHIPPING`: Shipping Issue
- `PAYMENT`: Payment Issue
- `TRACKING`: Tracking Issue
- `DELIVERY`: Delivery Issue
- `OTHER`: Other Issues

## Ticket Statuses

- `OPEN`: Initial status when ticket is created
- `IN_PROGRESS`: Ticket is being handled
- `RESOLVED`: Issue has been resolved
- `CLOSED`: Ticket has been closed

## Notes

1. Users can only access their own tickets
2. Ticket numbers are automatically generated with format: TKT + 9 random digits
3. The `user` field is automatically set to the authenticated user
4. The `created_at` and `updated_at` timestamps are automatically managed
5. The `resolved_at` timestamp is automatically set when status changes to RESOLVED
