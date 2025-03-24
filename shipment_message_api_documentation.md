# Shipment Message Generation API Documentation

This documentation explains how to use the Shipment Message Generator API to generate different types of professional messages for shipments in the Grade-A Express system.

## Endpoint

```
POST /shipments/message/{shipment_id}/
```

Where `{shipment_id}` is the ID of the shipment for which you want to generate a message.

## Authentication Requirements

- All requests require authentication
- Regular users can only generate messages for their own shipments
- Staff users can generate messages for any shipment

## Request Parameters

| Parameter                | Type    | Required | Default        | Description                                                               |
| ------------------------ | ------- | -------- | -------------- | ------------------------------------------------------------------------- |
| `message_type`           | string  | No       | `confirmation` | Type of message to generate                                               |
| `include_tracking`       | boolean | No       | `true`         | Whether to include tracking information                                   |
| `include_sender_details` | boolean | No       | `true`         | Whether to include sender details                                         |
| `include_credentials`    | boolean | No       | `false`        | Whether to include user login credentials                                 |
| `user_id`                | string  | No       | -              | User ID to fetch credentials from (only needed if not the shipment owner) |
| `additional_notes`       | string  | No       | -              | Additional notes to include in the message                                |

### Message Types

- `confirmation` - Shipment Confirmation message
- `notification` - Shipment Notification message
- `delivery` - Delivery Notification message
- `sender_notification` - Sender Notification message (with optional credentials)
- `custom` - Custom message

## Response Format

### Success Response (200 OK)

```json
{
  "message": "Complete message text with all substitutions applied"
}
```

### Error Response (400 Bad Request)

```json
{
  "message_type": ["This field is required."],
  "include_tracking": ["This field is required."]
}
```

## Example Usage

### 1. Generate a Shipment Confirmation Message

```
POST /shipments/message/SHP23XXXX/
Content-Type: application/json

{
  "message_type": "confirmation",
  "include_tracking": true,
  "include_sender_details": true
}
```

Response:

```json
{
  "message": "Dear John,\n\nYour shipment has been confirmed and is now being processed. You can track your shipment using tracking number: TRK123456789. \n\nShipment Details:\n- Sender: ABC Company\n- From: United States\n- Package Type: Package\n- Weight: 2.5 kg\n- Dimensions: 30 × 20 × 15 cm\n\nEstimated delivery date: 15 January 2024.\n\nThank you for choosing Grade-A Express for your shipping needs.\n\nBest regards,\nThe Grade-A Express Team"
}
```

### 2. Generate a Notification Message (In-Transit Updates)

```
POST /shipments/message/SHP23XXXX/
Content-Type: application/json

{
  "message_type": "notification",
  "include_tracking": true,
  "include_sender_details": false,
  "additional_notes": "Please ensure someone is available to receive the package."
}
```

Response:

```json
{
  "message": "Dear John,\n\nWe'd like to inform you that a package from ABC Company in United States is on its way to you. The tracking number for this shipment is: TRK123456789.\n\nCurrent Status: In Transit\nCurrent Location: Distribution Center, New York\n\nOur delivery team will contact you prior to delivery. Please ensure someone is available to receive the package.\n\nAdditional Notes: Please ensure someone is available to receive the package.\n\nThank you for choosing Grade-A Express for your shipping needs.\n\nBest regards,\nThe Grade-A Express Team"
}
```

### 3. Generate a Delivery Notification Message

```
POST /shipments/message/SHP23XXXX/
Content-Type: application/json

{
  "message_type": "delivery",
  "include_tracking": true
}
```

Response:

```json
{
  "message": "Dear John,\n\nGood news! Your package from ABC Company in United States is out for delivery today. Please ensure someone is available at the delivery address to receive the package.\n\nTracking Number: TRK123456789\n\nIf you have any special delivery instructions, please contact our customer service team immediately.\n\nThank you for choosing Grade-A Express for your shipping needs.\n\nBest regards,\nThe Grade-A Express Team"
}
```

### 4. Generate a Sender Notification with Credentials

```
POST /shipments/message/SHP23XXXX/
Content-Type: application/json

{
  "message_type": "sender_notification",
  "include_credentials": true,
  "user_id": "USRF3AB3A4D8"
}
```

Response:

```json
{
  "message": "Dear ABC Company,\n\nThank you for creating a shipment with Grade-A Express. Your shipment has been successfully registered in our system and is awaiting payment.\n\nShipment Details:\n- Tracking Number: TRK123456789\n- Package Type: Package\n- Weight: 2.5 kg\n- Dimensions: 30 × 20 × 15 cm\n- Declared Value: $150.00\n- Total Cost: $45.00\n\nRecipient Information:\n- Name: John Doe\n- Country: Germany\n- Address: 123 Main St, Berlin\n- Phone: +49123456789\n\nPayment Information:\n- Payment Method: Online Payment\n- Payment Status: Pending\n\nTo complete your payment and proceed with shipping, please log in to your shipping panel using the following credentials:\n- Phone Number/Username: 030586895\n- Password: 123\n\nYou can access your shipping panel at: https://www.gradeaexpress.com/login\n\nIf you have already received your login details, please use those to access the system. Once logged in, navigate to \"My Shipments\" and select this shipment to complete the payment process.\n\nIf you have any questions or need assistance, please contact our customer support team.\n\nThank you for choosing Grade-A Express for your shipping needs.\n\nBest regards,\nThe Grade-A Express Team"
}
```

## Message Content and Placeholders

Messages are generated using templates stored in the database. If no template is found, the system uses default templates. The following placeholders are available:

| Placeholder            | Description                                      |
| ---------------------- | ------------------------------------------------ |
| `{recipient_name}`     | Recipient's name                                 |
| `{recipient_email}`    | Recipient's email                                |
| `{recipient_phone}`    | Recipient's phone number                         |
| `{recipient_address}`  | Recipient's address                              |
| `{recipient_country}`  | Recipient's country                              |
| `{sender_name}`        | Sender's name                                    |
| `{sender_email}`       | Sender's email                                   |
| `{sender_phone}`       | Sender's phone number                            |
| `{sender_address}`     | Sender's address                                 |
| `{sender_country}`     | Sender's country                                 |
| `{tracking_number}`    | Shipment tracking number                         |
| `{package_type}`       | Type of package                                  |
| `{weight}`             | Package weight                                   |
| `{dimensions}`         | Package dimensions                               |
| `{declared_value}`     | Declared value of shipment                       |
| `{total_cost}`         | Total shipping cost                              |
| `{status}`             | Current shipment status                          |
| `{payment_method}`     | Payment method                                   |
| `{payment_status}`     | Payment status                                   |
| `{current_location}`   | Current package location                         |
| `{estimated_delivery}` | Estimated delivery date                          |
| `{description}`        | Package description                              |
| `{user_phone}`         | User phone number (only for sender_notification) |
| `{user_password}`      | User password (only for sender_notification)     |

## Notes on Message Types

1. **Confirmation Messages** (`confirmation`):

   - Sent after a shipment is confirmed
   - Includes basic shipment details and tracking information
   - Best used immediately after shipment creation

2. **Notification Messages** (`notification`):

   - Used for general shipment status updates
   - Includes current status and location
   - Good for keeping recipients informed during transit

3. **Delivery Notifications** (`delivery`):

   - Sent when a package is out for delivery
   - Focuses on delivery details and any special instructions
   - Best used on the day of delivery

4. **Sender Notifications** (`sender_notification`):

   - Sent to the shipping party
   - Can include login credentials for the shipping portal
   - Contains detailed shipment and payment information
   - Best used after initial shipment registration

5. **Custom Messages** (`custom`):
   - Generic message format with basic information
   - Useful for special circumstances not covered by other types

## Security Considerations

- User passwords are only included when specifically requested with `include_credentials=true`
- Only encrypted passwords can be retrieved and decrypted
- Staff users can request credentials for any user, regular users only for themselves

## Customizing Templates

Administrators can customize message templates in the admin panel under "Shipment Message Templates". Each template can include any of the placeholders listed above.

## Code Sample: How to Call the API

### Python Example

```python
import requests

# API URL for a specific shipment
url = "https://api.gradeaexpress.com/shipments/message/SHP23XXXX/"

# Authentication headers with token
headers = {
    "Content-Type": "application/json",
    "Authorization": "Token YOUR_AUTH_TOKEN"
}

# Request payload
payload = {
    "message_type": "confirmation",
    "include_tracking": True,
    "include_sender_details": True,
    "additional_notes": "Important delivery - please handle with care."
}

# Make the API request
response = requests.post(url, json=payload, headers=headers)

# Check if request was successful
if response.status_code == 200:
    # Get the generated message
    message = response.json()["message"]
    print("Generated message:")
    print(message)
else:
    print(f"Error: {response.status_code}")
    print(response.json())
```

### JavaScript/Fetch Example

```javascript
// API URL for a specific shipment
const url = "https://api.gradeaexpress.com/shipments/message/SHP23XXXX/";

// Authentication headers with token
const headers = {
  "Content-Type": "application/json",
  Authorization: "Token YOUR_AUTH_TOKEN",
};

// Request payload
const payload = {
  message_type: "notification",
  include_tracking: true,
  include_sender_details: false,
  additional_notes: "Package contains fragile items.",
};

// Make the API request
fetch(url, {
  method: "POST",
  headers: headers,
  body: JSON.stringify(payload),
})
  .then((response) => response.json())
  .then((data) => {
    console.log("Generated message:");
    console.log(data.message);
  })
  .catch((error) => {
    console.error("Error:", error);
  });
```
