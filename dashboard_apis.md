# Analytics Dashboard API Documentation

## Common Information for All Endpoints

- **Authentication**: JWT authentication required with admin privileges
- **Method**: GET
- **Response Format**: JSON
- **Error Responses**:
  - `401 Unauthorized`: Authentication credentials were not provided or are invalid
  - `403 Forbidden`: User does not have admin privileges
  - `500 Internal Server Error`: Server-side error

## 1. Overview Statistics

**Endpoint**: `/api/reports/analytics/overview/`

**Description**: Provides high-level metrics about the system, including user counts, request counts, and revenue information.

**Sample Response**:

```json
{
  "total_users": 156,
  "total_shipments": 342,
  "total_buy4me_requests": 98,
  "total_revenue": "25840.75",
  "pending_shipments": 24,
  "pending_buy4me_requests": 12,
  "active_users": 87
}
```

**Response Fields**:
| Field | Type | Description |
|-------|------|-------------|
| total_users | integer | Total number of registered users |
| total_shipments | integer | Total number of shipment requests |
| total_buy4me_requests | integer | Total number of Buy4Me requests |
| total_revenue | decimal | Total revenue from all paid invoices |
| pending_shipments | integer | Number of pending shipment requests |
| pending_buy4me_requests | integer | Number of pending Buy4Me requests |
| active_users | integer | Number of users active in the last 30 days |

## 2. User Analytics

**Endpoint**: `/api/reports/analytics/users/`

**Description**: Provides detailed breakdown of user statistics, including user types and geographical distribution.

**Sample Response**:

```json
{
  "walk_in_users": 98,
  "buy4me_users": 42,
  "drivers": 12,
  "admins": 4,
  "users_by_country": [
    {
      "name": "United States",
      "value": 65
    },
    {
      "name": "Canada",
      "value": 32
    }
  ],
  "user_growth": [
    {
      "name": "January",
      "value": 12
    },
    {
      "name": "February",
      "value": 18
    }
  ]
}
```

**Response Fields**:
| Field | Type | Description |
|-------|------|-------------|
| walk_in_users | integer | Number of users with Walk-In type |
| buy4me_users | integer | Number of users with Buy4Me type |
| drivers | integer | Number of drivers |
| admins | integer | Number of admin users (includes super admins) |
| users_by_country | array | Distribution of users by country |
| users_by_country[].name | string | Country name |
| users_by_country[].value | integer | Number of users in that country |
| user_growth | array | User registration growth by month for current year |
| user_growth[].name | string | Month name |
| user_growth[].value | integer | Number of new users registered in that month |

## 3. Shipment Analytics

**Endpoint**: `/api/reports/analytics/shipments/`

**Description**: Provides analytics on shipment requests, including status distribution, delivery times, and popular destinations.

**Sample Response**:

```json
{
  "shipments_by_status": {
    "PENDING": 24,
    "PROCESSING": 36,
    "IN_TRANSIT": 48,
    "DELIVERED": 230,
    "CANCELLED": 4
  },
  "shipments_by_month": [
    {
      "name": "January",
      "value": 42
    },
    {
      "name": "February",
      "value": 56
    }
  ],
  "avg_delivery_time": 3.5,
  "total_shipment_value": "18950.25",
  "popular_destinations": [
    {
      "name": "United States",
      "value": 120
    },
    {
      "name": "Canada",
      "value": 85
    }
  ],
  "shipment_weight_distribution": [
    {
      "name": "Under 1kg",
      "value": 76
    },
    {
      "name": "1-5kg",
      "value": 158
    },
    {
      "name": "5-10kg",
      "value": 83
    },
    {
      "name": "10-20kg",
      "value": 22
    },
    {
      "name": "Over 20kg",
      "value": 3
    }
  ]
}
```

**Response Fields**:
| Field | Type | Description |
|-------|------|-------------|
| shipments_by_status | object | Count of shipments by status |
| shipments_by_status.PENDING | integer | Number of pending shipments |
| shipments_by_status.PROCESSING | integer | Number of processing shipments |
| shipments_by_status.IN_TRANSIT | integer | Number of in-transit shipments |
| shipments_by_status.DELIVERED | integer | Number of delivered shipments |
| shipments_by_status.CANCELLED | integer | Number of cancelled shipments |
| shipments_by_month | array | Shipment counts by month for current year |
| shipments_by_month[].name | string | Month name |
| shipments_by_month[].value | integer | Number of shipments in that month |
| avg_delivery_time | float | Average delivery time in days |
| total_shipment_value | decimal | Total value of all shipments |
| popular_destinations | array | Most popular shipment destinations |
| popular_destinations[].name | string | Destination country name |
| popular_destinations[].value | integer | Number of shipments to that destination |
| shipment_weight_distribution | array | Distribution of shipments by weight range |
| shipment_weight_distribution[].name | string | Weight range label |
| shipment_weight_distribution[].value | integer | Number of shipments in that weight range |

## 4. Buy4Me Analytics

**Endpoint**: `/api/reports/analytics/buy4me/`

**Description**: Provides analytics on Buy4Me requests, including status distribution, processing times, and popular items.

**Sample Response**:

```json
{
  "requests_by_status": {
    "DRAFT": 8,
    "SUBMITTED": 12,
    "ORDER_PLACED": 18,
    "IN_TRANSIT": 15,
    "WAREHOUSE_ARRIVED": 10,
    "SHIPPED_TO_CUSTOMER": 12,
    "COMPLETED": 20,
    "CANCELLED": 3
  },
  "requests_by_month": [
    {
      "name": "January",
      "value": 15
    },
    {
      "name": "February",
      "value": 22
    }
  ],
  "avg_processing_time": 8.2,
  "total_buy4me_value": "6890.50",
  "popular_items": [
    {
      "name": "Apple iPhone 14 Pro",
      "value": 12
    },
    {
      "name": "Samsung Galaxy S22",
      "value": 10
    }
  ]
}
```

**Response Fields**:
| Field | Type | Description |
|-------|------|-------------|
| requests_by_status | object | Count of Buy4Me requests by status |
| requests_by_status.DRAFT | integer | Number of draft requests |
| requests_by_status.SUBMITTED | integer | Number of submitted requests |
| requests_by_status.ORDER_PLACED | integer | Number of requests with orders placed |
| requests_by_status.IN_TRANSIT | integer | Number of requests in transit |
| requests_by_status.WAREHOUSE_ARRIVED | integer | Number of requests arrived at warehouse |
| requests_by_status.SHIPPED_TO_CUSTOMER | integer | Number of requests shipped to customer |
| requests_by_status.COMPLETED | integer | Number of completed requests |
| requests_by_status.CANCELLED | integer | Number of cancelled requests |
| requests_by_month | array | Buy4Me request counts by month for current year |
| requests_by_month[].name | string | Month name |
| requests_by_month[].value | integer | Number of requests in that month |
| avg_processing_time | float | Average processing time in days (from submission to completion) |
| total_buy4me_value | decimal | Total value of all Buy4Me requests |
| popular_items | array | Most frequently requested items |
| popular_items[].name | string | Item name |
| popular_items[].value | integer | Number of requests for that item |

## 5. Revenue Analytics

**Endpoint**: `/api/reports/analytics/revenue/`

**Description**: Provides analytics on revenue, including trends, service breakdown, and payment method distribution.

**Sample Response**:

```json
{
  "revenue_by_month": [
    {
      "name": "January",
      "value": 3560.75
    },
    {
      "name": "February",
      "value": 4830.25
    }
  ],
  "revenue_by_service": {
    "Shipment": "18950.25",
    "Buy4Me": "6890.50"
  },
  "payment_method_distribution": {
    "STRIPE": 156,
    "PAYPAL": 98,
    "BANK_TRANSFER": 45,
    "CASH": 43
  },
  "average_order_value": "75.55",
  "refund_rate": 2.3
}
```

**Response Fields**:
| Field | Type | Description |
|-------|------|-------------|
| revenue_by_month | array | Revenue by month for current year |
| revenue_by_month[].name | string | Month name |
| revenue_by_month[].value | float | Revenue for that month |
| revenue_by_service | object | Revenue breakdown by service type |
| revenue_by_service.Shipment | decimal | Revenue from shipment services |
| revenue_by_service.Buy4Me | decimal | Revenue from Buy4Me services |
| payment_method_distribution | object | Count of payments by method |
| payment_method_distribution.STRIPE | integer | Number of Stripe payments |
| payment_method_distribution.PAYPAL | integer | Number of PayPal payments |
| payment_method_distribution.BANK_TRANSFER | integer | Number of bank transfer payments |
| payment_method_distribution.CASH | integer | Number of cash payments |
| average_order_value | decimal | Average value per order |
| refund_rate | float | Percentage of orders that were refunded |

## 6. Driver Analytics

**Endpoint**: `/api/reports/analytics/drivers/`

**Description**: Provides analytics on driver performance, including delivery counts, earnings, and on-time delivery rates.

**Sample Response**:

```json
{
  "top_drivers": [
    {
      "id": "USR123456",
      "name": "John Smith",
      "deliveries": 85,
      "earnings": 4250.75
    },
    {
      "id": "USR234567",
      "name": "Jane Doe",
      "deliveries": 76,
      "earnings": 3800.5
    }
  ],
  "deliveries_by_driver": [
    {
      "id": "USR123456",
      "name": "John Smith",
      "value": 85
    },
    {
      "id": "USR234567",
      "name": "Jane Doe",
      "value": 76
    }
  ],
  "driver_earnings": [
    {
      "id": "USR123456",
      "name": "John Smith",
      "value": 4250.75
    },
    {
      "id": "USR234567",
      "name": "Jane Doe",
      "value": 3800.5
    }
  ],
  "driver_performance": [
    {
      "id": "USR123456",
      "name": "John Smith",
      "total_deliveries": 85,
      "on_time_deliveries": 79,
      "on_time_percentage": 92.94
    },
    {
      "id": "USR234567",
      "name": "Jane Doe",
      "total_deliveries": 76,
      "on_time_deliveries": 68,
      "on_time_percentage": 89.47
    }
  ]
}
```

**Response Fields**:
| Field | Type | Description |
|-------|------|-------------|
| top_drivers | array | Top drivers by number of deliveries |
| top_drivers[].id | string | Driver user ID |
| top_drivers[].name | string | Driver name |
| top_drivers[].deliveries | integer | Number of deliveries |
| top_drivers[].earnings | float | Total earnings |
| deliveries_by_driver | array | Number of deliveries by driver |
| deliveries_by_driver[].id | string | Driver user ID |
| deliveries_by_driver[].name | string | Driver name |
| deliveries_by_driver[].value | integer | Number of deliveries |
| driver_earnings | array | Earnings by driver |
| driver_earnings[].id | string | Driver user ID |
| driver_earnings[].name | string | Driver name |
| driver_earnings[].value | float | Total earnings |
| driver_performance | array | Driver performance metrics |
| driver_performance[].id | string | Driver user ID |
| driver_performance[].name | string | Driver name |
| driver_performance[].total_deliveries | integer | Total number of deliveries |
| driver_performance[].on_time_deliveries | integer | Number of on-time deliveries |
| driver_performance[].on_time_percentage | float | Percentage of on-time deliveries |

## 7. Support Analytics

**Endpoint**: `/api/reports/analytics/support/`

**Description**: Provides analytics on support tickets, including status distribution, resolution times, and categories.

**Sample Response**:

```json
{
  "tickets_by_status": {
    "OPEN": 12,
    "IN_PROGRESS": 18,
    "RESOLVED": 65,
    "CLOSED": 43
  },
  "tickets_by_category": {
    "PAYMENT": 24,
    "SHIPMENT": 38,
    "ACCOUNT": 15,
    "TECHNICAL": 22,
    "OTHER": 39
  },
  "avg_resolution_time": 18.5,
  "open_tickets_count": 30
}
```

**Response Fields**:
| Field | Type | Description |
|-------|------|-------------|
| tickets_by_status | object | Count of support tickets by status |
| tickets_by_status.OPEN | integer | Number of open tickets |
| tickets_by_status.IN_PROGRESS | integer | Number of in-progress tickets |
| tickets_by_status.RESOLVED | integer | Number of resolved tickets |
| tickets_by_status.CLOSED | integer | Number of closed tickets |
| tickets_by_category | object | Count of support tickets by category |
| tickets_by_category.PAYMENT | integer | Number of payment-related tickets |
| tickets_by_category.SHIPMENT | integer | Number of shipment-related tickets |
| tickets_by_category.ACCOUNT | integer | Number of account-related tickets |
| tickets_by_category.TECHNICAL | integer | Number of technical tickets |
| tickets_by_category.OTHER | integer | Number of other tickets |
| avg_resolution_time | float | Average resolution time in hours |
| open_tickets_count | integer | Total number of open tickets |

## Implementation Notes

1. **Note on Driver Analytics**: The `driver_performance` calculation has a type issue in the code when comparing delivery dates with estimated delivery dates when the latter is `None`. This should be handled properly to prevent runtime errors.

2. **Data Time Range**: Most of the time-based metrics (like user growth, shipments by month) are calculated for the current year only. For historical data, additional endpoints may be needed.

3. **Chart Data Format**: The data in arrays with `name` and `value` properties is formatted specifically for easy integration with chart libraries like Chart.js, Recharts, or D3.js.

4. **Authentication**: Ensure your frontend sends the JWT token in the Authorization header for all requests.

5. **Error Handling**: Implement robust error handling on both server and client sides. The API will return appropriate status codes for different error scenarios.
