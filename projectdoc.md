# Backend Specification for Logistics & Buy4Me Services

This document provides an in-depth overview of all the backend modules and functionalities required for a logistics and "Buy4Me" service platform. The goal is to ensure clarity on **what** must be built and **how** each piece of functionality ties together in a Django/Django REST Framework (DRF) environment.

---

## Table of Contents
1. [Overview](#overview)
2. [Core Technologies](#core-technologies)
3. [System Architecture](#system-architecture)
4. [Data Models](#data-models)
   1. [User & Role Models](#user--role-models)
   2. [Shipment Models](#shipment-models)
   3. [Buy4Me Models](#buy4me-models)
   4. [Payment & Invoice Models](#payment--invoice-models)
   5. [Others](#others)
5. [API Endpoints & Modules](#api-endpoints--modules)
   1. [Authentication & Authorization](#authentication--authorization)
   2. [User Management](#user-management)
   3. [Shipment Management](#shipment-management)
   4. [Buy4Me Management](#buy4me-management)
   5. [Payment & Invoicing](#payment--invoicing)
   6. [Admin & Super Admin Management](#admin--super-admin-management)
   7. [Reporting & Analytics](#reporting--analytics)
   8. [Live Chat & Support](#live-chat--support)
6. [Multilingual & Multi-Currency Integration](#multilingual--multi-currency-integration)
7. [Notifications & Real-Time Updates](#notifications--real-time-updates)
8. [Security & Compliance](#security--compliance)
9. [Deployment & Environment Setup](#deployment--environment-setup)
10. [Future Enhancements](#future-enhancements)

---

## 1. Overview

This backend will power a **logistics and Buy4Me** platform with features like:
- **Walk-In Shipping Services** (shipment tracking, invoicing)
- **Buy4Me** embedded shopping experience (item requests, order placement, shipping)
- **Role-Based Dashboards** for Customers (Walk-In and Buy4Me), Admins, and Super Admins
- **Payment & Invoicing** with multiple gateways
- **Reports & Analytics** for admins and super admins
- **Live Chat & Support** integration

The platform must be scalable, secure, and extensible.

---

## 2. Core Technologies

1. **Django** (5.1.x+ recommended)
   - Core framework for models, views, and admin functionality.
2. **Django REST Framework (DRF)**
   - Provides the RESTful API structure for communication with the frontend.
3. **PostgreSQL** (or MySQL)
   - Recommended for relational data storage.
4. **Celery / RQ (Optional for Async Tasks)**
   - For handling background tasks such as sending emails, currency updates, etc.
5. **Redis (Optional)** 
   - For caching, sessions, and Celery broker.
6. **DRF Token / JWT / OAuth2** (for authentication)
   - A secure token-based authentication system, typically JWT.

---

## 3. System Architecture

A high-level flow would be:
1. **Users** (Walk-In or Buy4Me) → **Frontend (Next.js or any)** → **Backend API (Django/DRF)** → **Database**.
2. **Admins/Super Admins** manage **Users, Orders, Shipments** etc. via dedicated endpoints.
3. **Payment Gateways** integrated with the backend for transaction processing.
4. **External APIs** (e.g., currency exchange rates, shipping carriers, embedded vendor sites) might be consumed by the backend.

## Folder Structure 
    logistics_project/
    ├── core/ 
    │   ├── settings/
    │   │   ├── base.py
    │   │   ├── local.py
    │   │   └── production.py
    │   ├── init.py
    │   ├── asgi.py
    │   ├── settings.py
    │   ├── urls.py
    │   └── wsgi.py
    ├── accounts/
    ├── shipments/
    ├── buy4me/
    ├── vendors/
    ├── support/
    ├── notifications/
    ├── reports/
    ├── static/
    ├── media/
    ├── templates/
    ├── requirements/
    │   ├── base.txt
    │   ├── local.txt
    │   └── production.txt
    └── manage.py
    └── projectdoc.md
    └── .cursorrules.md
    └── venv
    └── .env
    └── .env.example
    └── .gitignore
    └── db.sqlte3
    └── static
    └── media
    └── media

---

## 4. Data Models

### 4.1 User & Role Models

**User**  
- **Fields**:
  - `id (UUID or AutoField)`
  - `username` (or `email`, unique)
  - `password` (hashed)
  - `first_name`
  - `last_name`
  - `phone_number`
  - `address` (optional or separate Address model)
  - `role` (choices: `WALK_IN`, `BUY4ME`, `ADMIN`, `SUPER_ADMIN`)
  - `is_active` (bool)
  - Timestamps: `date_joined`, `updated_at`
- **Relationships**:
  - Could link to one or more addresses if needed.

**Role** (Optional if not using a `role` field)
- A separate model or a Django Group. 
- Manages permission sets (e.g., `CAN_VIEW_ALL_ORDERS`, `CAN_MANAGE_SHIPMENTS`).

---

### 4.2 Shipment Models

**ShipmentRequest**  
- **Fields**:
  - `id`
  - `user` (FK to `User`, typically Walk-In or Buy4Me user)
  - `package_details` (JSON or structured fields: weight, dimensions, content description)
  - `delivery_address` (could be a ForeignKey to an Address model)
  - `status` (choices: `PENDING`, `PROCESSING`, `IN_TRANSIT`, `DELIVERED`)
  - `tracking_number`
  - `cost` (decimal)
  - `invoice` (FK to `Invoice` once generated)
  - `created_at`, `updated_at`

---

### 4.3 Buy4Me Models

**Buy4MeRequest**  
- **Fields**:
  - `id`
  - `user` (FK to `User` with role=BUY4ME)
  - `status` (choices: `DRAFT`, `SUBMITTED`, `ORDER_PLACED`, `IN_TRANSIT`, `WAREHOUSE_ARRIVED`, `SHIPPED_TO_CUSTOMER`, `COMPLETED`)
  - `total_cost` (decimal, includes item cost + fees)
  - `created_at`, `updated_at`

**Buy4MeItem**  
- **Fields**:
  - `id`
  - `buy4me_request` (FK to `Buy4MeRequest`)
  - `product_name`
  - `product_url`
  - `quantity`
  - `color` (optional)
  - `size` (optional)
  - `unit_price` (calculated or input from external site)
  - `currency` (to handle multi-currency if needed)
  - `status` (could mimic parent or have a separate status, but typically replicate the request's status for clarity)
  - `created_at`, `updated_at`

---

### 4.4 Payment & Invoice Models

**Invoice**  
- **Fields**:
  - `id`
  - `invoice_number` (unique, e.g., formatted with prefix + auto-increment)
  - `user` (FK to `User`)
  - `amount`
  - `currency`
  - `payment_status` (choices: `UNPAID`, `PAID`, `PARTIALLY_PAID`, `REFUNDED`)
  - `payment_method` (choices: `CREDIT_CARD`, `PAYPAL`, `STRIPE`, etc.)
  - `related_shipment` (optional, if shipment invoice)
  - `related_buy4me_request` (optional, if Buy4Me invoice)
  - `created_at`, `updated_at`

**PaymentTransaction**  
- **Fields**:
  - `id`
  - `invoice` (FK to `Invoice`)
  - `transaction_reference` (from payment gateway)
  - `status` (choices: `SUCCESS`, `FAILED`, `PENDING`)
  - `response_data` (JSON for storing gateway response)
  - `created_at`, `updated_at`

---

### 4.5 Others

**Vendor**  
- **Fields**:
  - `id`
  - `name` (e.g., "Amazon", "eBay")
  - `url`
  - `active` (boolean)
  - `logo` (optional)
  - `created_at`, `updated_at`

**ExchangeRate**  
- **Fields**:
  - `id`
  - `base_currency` (e.g., "USD")
  - `target_currency` (e.g., "EUR")
  - `rate` (decimal)
  - `updated_at`

**Feedback**  
- **Fields**:
  - `id`
  - `user` (FK to `User`)
  - `message`
  - `rating` (1-5)
  - `created_at`

**SupportTicket**  
- **Fields**:
  - `id`
  - `user` (FK to `User`)
  - `subject`
  - `description`
  - `status` (choices: `OPEN`, `IN_PROGRESS`, `RESOLVED`, `CLOSED`)
  - `created_at`, `updated_at`

---

## 5. API Endpoints & Modules

The following sections describe the main modules, their endpoints, and their functionality.

### 5.1 Authentication & Authorization
1. **POST** `/api/auth/login/`
   - Request body: `username`, `password`
   - Response: Auth token (JWT or session-based)

2. **POST** `/api/auth/logout/`
   - Invalidates the current token/session.

3. **POST** `/api/auth/register/` *(If needed for Buy4Me)* or Admin-only creation endpoint
   - Creates a new user. 
   - For **Walk-In** users, typically an Admin manually creates.

4. **GET** `/api/auth/user/`
   - Returns the currently authenticated user profile.

**Implementation Notes**:
- Use DRF permissions. 
- For multi-factor authentication (optional), implement an additional verification step.

---

### 5.2 User Management

#### Admin-Facing
1. **GET** `/api/admin/users/`
   - Lists all users (filter by role, status).
2. **GET** `/api/admin/users/{user_id}/`
   - Retrieve a specific user's details.
3. **POST** `/api/admin/users/`
   - Create a new user (Walk-In or Buy4Me).
4. **PUT/PATCH** `/api/admin/users/{user_id}/`
   - Update user's information.
5. **DELETE** `/api/admin/users/{user_id}/`
   - Deactivate or delete a user.

#### User-Facing
1. **GET** `/api/users/me/`
   - Retrieves the logged-in user's profile.
2. **PATCH** `/api/users/me/`
   - Updates personal profile info (phone, address, etc.).

---

### 5.3 Shipment Management

1. **POST** `/api/shipments/`
   - Create a new shipment request (Walk-In or Buy4Me).
2. **GET** `/api/shipments/`
   - List all shipments for the authenticated user (or all shipments if admin).
3. **GET** `/api/shipments/{shipment_id}/`
   - Retrieve shipment details (tracking info, cost, status).
4. **PATCH** `/api/shipments/{shipment_id}/status/`
   - Update shipment status (admin only).
5. **PATCH** `/api/shipments/{shipment_id}/`
   - Update shipping details (e.g., address).
6. **DELETE** `/api/shipments/{shipment_id}/`
   - Cancel or remove a shipment request (subject to business rules).

**Key Points**:
- Once a shipment is confirmed, an **Invoice** can be generated. 
- Payment is then linked to that invoice.

---

### 5.4 Buy4Me Management

#### Buy4Me Requests
1. **POST** `/api/buy4me/requests/`
   - Create a new Buy4Me request with **Draft** status.
2. **GET** `/api/buy4me/requests/`
   - List all requests for the logged-in Buy4Me user (admin sees all).
3. **GET** `/api/buy4me/requests/{request_id}/`
   - Retrieve details (status, items, cost).
4. **PATCH** `/api/buy4me/requests/{request_id}/`
   - Update request status (admin or user in some cases).
   - Add shipping instructions once items arrive at the warehouse.

#### Buy4Me Items
1. **POST** `/api/buy4me/requests/{request_id}/items/`
   - Add a new item (auto from embedded site or manual).
2. **GET** `/api/buy4me/requests/{request_id}/items/`
   - List items in a Buy4Me request.
3. **PATCH** `/api/buy4me/items/{item_id}/`
   - Update item details (quantity, color, etc.).
4. **DELETE** `/api/buy4me/items/{item_id}/`
   - Remove an item from the request.

#### Logic
- When **submitted**, the system calculates total cost (product + service fee).
- Payment triggers an invoice. 
- Once items are purchased, status changes to **ORDER_PLACED**.
- When items reach warehouse, user can initiate shipment to final address.

---

### 5.5 Payment & Invoicing

1. **POST** `/api/invoices/`
   - Generate an invoice (admin or automatically upon a purchase/shipment).
2. **GET** `/api/invoices/`
   - List all invoices for an authenticated user (admin sees all).
3. **GET** `/api/invoices/{invoice_id}/`
   - Retrieve invoice details (items, amounts, status).
4. **POST** `/api/invoices/{invoice_id}/pay/`
   - Initiate payment (connect to a payment gateway).

**Integration**:
- Payment gateway modules (Stripe, PayPal, etc.) may require separate endpoints or hosted pages. 
- Webhooks from payment gateways handle success/failure updates.

---

### 5.6 Admin & Super Admin Management

Admin actions are generally covered above. However, **Super Admin** has extended privileges:

1. **System Configuration**
   - `/api/superadmin/settings/` (POST/PUT) – Exchange rates, service fees, etc.
2. **Vendor Management**
   - `/api/superadmin/vendors/` – Add, list, update, remove embedded websites.
3. **Admin Management**
   - `/api/superadmin/admins/` – CRUD for admin accounts.

---

### 5.7 Reporting & Analytics

1. **GET** `/api/admin/reports/`
   - Filter by date range, customer type, vendor, region, etc.
2. **GET** `/api/admin/reports/export/`
   - Export to CSV, Excel, or PDF.
3. **GET** `/api/superadmin/analytics/`
   - Real-time metrics (active users, revenue, top services, etc.).

**Data**:
- Summaries of shipments, buy4me requests, revenues, etc. 
- Possibly stored in **Analytics** tables or aggregated on-the-fly.

---

### 5.8 Live Chat & Support

1. **POST** `/api/support/tickets/`
   - Create a new support ticket.
2. **GET** `/api/support/tickets/`
   - List user's or admin's open tickets.
3. **PATCH** `/api/support/tickets/{ticket_id}/`
   - Update ticket (status, admin response).
4. **DELETE** `/api/support/tickets/{ticket_id}/`
   - Mark as closed/resolved.

**Live Chat** can be integrated via a third-party service (e.g., Twilio, SendBird, or custom WebSocket).

---

## 6. Multilingual & Multi-Currency Integration

- **Multilingual**:
  - Use Django's `Internationalization (i18n)` and `Localization (l10n)` features.
  - Strings in code wrapped with `ugettext_lazy`.
- **Multi-Currency**:
  - Maintain an **ExchangeRate** model or fetch via external API (e.g., Fixer.io).
  - Convert item costs and shipping fees on the fly or store them in a base currency (e.g., USD).

---

## 7. Notifications & Real-Time Updates

- **Email Notifications**:
  - For order status changes, invoice generation, shipping updates.
- **SMS/Push Notifications** (optional):
  - Integration with Twilio or Firebase Cloud Messaging if needed.
- **WebSocket or Pusher** (optional):
  - Real-time notifications for status changes, live chat updates.

---

## 8. Security & Compliance

1. **SSL/TLS**:
   - All endpoints secured via HTTPS.
2. **Authentication**:
   - Token-based (JWT) or Session-based with potential 2FA for high-security areas.
3. **Permissions**:
   - DRF permissions ensuring that only users with correct roles can access or modify data.
4. **Data Validation**:
   - Strict validation on inputs, especially for shipping addresses, product data, payments.
5. **Logging & Auditing**:
   - Keep logs of all admin actions, especially changes in statuses or user data.

---

## 9. Deployment & Environment Setup

### 9.1 Environment Variables
- `SECRET_KEY` for Django
- `DATABASE_URL` (or separate DB config)
- `DEBUG` flag
- Payment Gateway keys (Stripe secret, PayPal client IDs, etc.)
- Email/SMS service credentials

### 9.2 Deployment Steps
1. **Install** dependencies: `pip install -r requirements.txt`
2. **Migrate**: `python manage.py migrate`
3. **Collect static**: `python manage.py collectstatic`
4. **Run server**: `gunicorn wsgi:application` or `daphne` (if using async).
5. **Scaling**:
   - Use multiple workers, load balancers, caching layers as traffic grows.

---

## 10. Future Enhancements
- **Warehouse Management** module for item location, auto-check in/out.
- **Automated Currency Updates** via Celery scheduled tasks.
- **Automated Email Reminders** for unpaid invoices.
- **AI-driven** shipping cost optimization or vendor recommendations.
- **Multi-Warehouse** or cross-border logistics expansions.

---

## Conclusion

This document outlines the **backend requirements** for the logistics and Buy4Me platform using Django and DRF. Each module—**User Management**, **Shipment**, **Buy4Me**, **Payments**, **Admin** dashboards, and **Super Admin** reporting—has clear data models and endpoints. 

By adhering to these specifications, developers and stakeholders should have a solid blueprint to implement, test, and deploy a scalable, secure, and user-friendly system.

**End of Document**
