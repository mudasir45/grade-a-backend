# Shipping Rates Management System Documentation

## Overview
The shipping rates system allows flexible configuration of shipping costs based on multiple factors:
- Origin and destination countries
- Package weight and dimensions
- Service types (e.g., Express, Standard)
- Zone-based pricing
- Additional charges (fixed or percentage)

## 1. Basic Concepts

### 1.1 Countries
Countries are categorized into two types:
- **Departure Countries**: Where shipments originate from
- **Destination Countries**: Where shipments are delivered to

Example:
```
Departure Countries: UAE (AE), Saudi Arabia (SA)
Destination Countries: India (IN), Pakistan (PK), Bangladesh (BD)
```

### 1.2 Shipping Zones
Zones group departure and destination countries to apply specific rates. This allows for flexible pricing strategies.

Example Zone Structure:
```
Zone: Middle East to South Asia
- Departure Countries: UAE, Saudi Arabia
- Destination Countries: India, Pakistan, Bangladesh

Zone: Middle East Express
- Departure Countries: UAE
- Destination Countries: India
- (Higher rates for express service)
```

### 1.3 Service Types
Different shipping speed and handling options:
```
1. Express Delivery
   - Delivery Time: 1-2 business days
   - Higher rates, faster service

2. Standard Delivery
   - Delivery Time: 3-5 business days
   - Regular rates, normal service

3. Economy Delivery
   - Delivery Time: 5-7 business days
   - Lower rates, slower service
```

## 2. Rate Calculation Components

### 2.1 Weight-Based Rates
Rates are defined per zone and service type with weight ranges:

Example:
```
Zone: Middle East to South Asia
Service: Standard Delivery
Weight Range: 0-5 kg
- Base Rate: $20
- Per KG Rate: $4

Weight Range: 5.1-10 kg
- Base Rate: $35
- Per KG Rate: $3.5
```

### 2.2 Dimensional Weight
Package dimensions affect the shipping cost:
```
Dimensional Weight = (Length × Width × Height) ÷ Dimensional Factor

Example:
- Package: 40cm × 30cm × 20cm = 24,000 cm³
- Dimensional Factor: 5000
- Dimensional Weight: 24,000 ÷ 5000 = 4.8 kg

The higher of actual weight and dimensional weight is used for pricing.
```

### 2.3 Additional Charges
Extra fees that can be applied:

```
1. Fixed Charges:
   - Fuel Surcharge: $5 per shipment
   - Remote Area Fee: $10 per shipment

2. Percentage Charges:
   - Insurance: 1% of base rate
   - Peak Season Surcharge: 5% of base rate
```

## 3. Practical Examples

### 3.1 Simple Shipment
```
Scenario:
- From: UAE (Dubai)
- To: India (Mumbai)
- Weight: 3 kg
- Dimensions: 20cm × 15cm × 10cm
- Service: Standard Delivery

Calculation:
1. Base Rate: $20
2. Weight Cost: 3 kg × $4 = $12
3. Dimensional Weight: (20×15×10) ÷ 5000 = 0.6 kg (actual weight used)
4. Additional Charges:
   - Fuel Surcharge: $5
   - Insurance (1%): $0.32

Total Cost: $37.32
```

### 3.2 Heavy Shipment with Dimensional Weight
```
Scenario:
- From: Saudi Arabia
- To: Pakistan
- Actual Weight: 8 kg
- Dimensions: 50cm × 40cm × 30cm
- Service: Express Delivery

Calculation:
1. Dimensional Weight: (50×40×30) ÷ 5000 = 12 kg
2. Base Rate: $35
3. Weight Cost: 12 kg × $3.5 = $42 (dimensional weight used)
4. Additional Charges:
   - Fuel Surcharge: $5
   - Express Handling: $15
   - Insurance (1%): $0.77

Total Cost: $97.77
```

## 4. Managing Rates in Admin Panel

### 4.1 Setting Up Countries
1. Go to Countries in admin panel
2. Add countries with proper codes and types
3. Mark them as active/inactive

### 4.2 Creating Shipping Zones
1. Create a new zone
2. Select departure and destination countries
3. Add description for reference

### 4.3 Configuring Rates
1. Go to Weight Based Rates
2. Select zone and service type
3. Define weight ranges and rates
4. Set base rate and per kg rate

### 4.4 Additional Charges
1. Create charges (fixed or percentage)
2. Assign to specific zones and service types
3. Set values and activate/deactivate as needed

## 5. Best Practices

1. **Zone Planning**
   - Create logical groupings of countries
   - Consider service levels per zone
   - Account for regional variations

2. **Rate Structure**
   - Start with broader weight ranges
   - Adjust based on actual shipping patterns
   - Consider competitive pricing

3. **Additional Charges**
   - Keep charges transparent
   - Use percentage-based charges for value-based fees
   - Use fixed charges for constant costs

4. **Regular Maintenance**
   - Review and update rates periodically
   - Monitor zone effectiveness
   - Adjust dimensional factors based on carrier changes

## 6. Troubleshooting

Common issues and solutions:

1. **Rates Not Appearing**
   - Check if countries are correctly assigned to zones
   - Verify weight ranges cover the package weight
   - Ensure service type is active

2. **Unexpected Costs**
   - Review dimensional weight calculation
   - Check additional charges
   - Verify weight range assignments

3. **Zone Issues**
   - Confirm country assignments
   - Check zone active status
   - Verify service type availability

## 7. API Integration

The shipping rate calculator is available via API:

```http
POST /api/shipping-rates/calculate/

{
    "origin_country": "AE",
    "destination_country": "IN",
    "weight": 5.5,
    "length": 40,
    "width": 30,
    "height": 20,
    "service_type": "EXPRESS"
}
```

Response includes all available rates and detailed breakdown of costs. 