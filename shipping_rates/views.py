from decimal import Decimal

from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import City

from .models import (AdditionalCharge, Country, Currency, DimensionalFactor,
                     Extras, ServiceType, ShippingZone, WeightBasedRate)
from .serializers import (AdditionalChargeSerializer, CountrySerializer,
                          CurrencyConversionSerializer, CurrencySerializer,
                          DimensionalFactorSerializer, ExtrasSerializer,
                          ServiceTypeSerializer, ShippingCalculatorSerializer,
                          ShippingZoneSerializer, WeightBasedRateSerializer)


@extend_schema(tags=['shipping-rates'])
class ShippingRateViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAdminUser]
    
    @extend_schema(
        summary="Calculate shipping rate (not used)",
        request=ShippingCalculatorSerializer,
    )
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def calculate(self, request):
        serializer = ShippingCalculatorSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            print("data", data)
            
            try:
                # Get origin and destination countries
                origin = Country.objects.get(
                    id=data['origin_country'],
                    country_type=Country.CountryType.DEPARTURE
                )   
                destination = Country.objects.get(
                    id=data['destination_country'],
                    country_type=Country.CountryType.DESTINATION
                )
                
                # Find applicable zones
                zones = ShippingZone.objects.filter(
                    departure_countries=origin,
                    destination_countries=destination,
                    is_active=True
                )
                
                if not zones.exists():
                    return Response(
                        {'error': 'No shipping zone found for this route'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Calculate volumetric weight
                volume = data['length'] * data['width'] * data['height']
                
                results = []
                for zone in zones:
                    # Get rates for all service types or specific service type
                    rates = WeightBasedRate.objects.filter(
                        zone=zone,
                        is_active=True,
                        min_weight__lte=data['weight'],
                        max_weight__gte=data['weight']
                    )
                    
                    if 'service_type' in data:
                        rates = rates.filter(service_type_id=data['service_type'])
                    
                    for rate in rates:
                        # Get dimensional factor for volumetric weight
                        dim_factor = DimensionalFactor.objects.filter(
                            service_type=rate.service_type,
                            is_active=True
                        ).first()
                        
                        # Calculate chargeable weight
                        chargeable_weight = data['weight']
                        if dim_factor:
                            vol_weight = volume / dim_factor.factor
                            chargeable_weight = max(data['weight'], vol_weight)
                        
                        # Calculate base cost
                        base_cost = (chargeable_weight * rate.per_kg_rate)
                        
                        # Get additional charges
                        additional_charges = AdditionalCharge.objects.filter(
                            zones=zone,
                            service_types=rate.service_type,
                            is_active=True
                        )
                        
                        total_additional = 0
                        charge_details = []
                        for charge in additional_charges:
                            charge_amount = 0
                            if charge.charge_type == AdditionalCharge.ChargeType.FIXED:
                                charge_amount = charge.value
                            else:  # PERCENTAGE
                                charge_amount = (base_cost * charge.value / 100)
                            
                            total_additional += charge_amount
                            charge_details.append({
                                'name': charge.name,
                                'amount': charge_amount,
                                'type': charge.get_charge_type_display()
                            })
                        
                        total_cost = base_cost + total_additional
                        
                        results.append({
                            'zone': zone.name,
                            'service_type': rate.service_type.name,
                            'delivery_time': rate.service_type.delivery_time,
                            'weight': {
                                'actual': float(data['weight']),
                                'volumetric': float(vol_weight) if dim_factor else None,
                                'chargeable': float(chargeable_weight)
                            },
                            'costs': {
                                'base_cost': float(base_cost),
                                'additional_charges': charge_details,
                                'total_additional': float(total_additional),
                                'total_cost': float(total_cost)
                            }
                        })
                
                # Sort results by total cost
                results.sort(key=lambda x: x['costs']['total_cost'])
                return Response(results)
                
            except Country.DoesNotExist:
                return Response(
                    {'error': 'Invalid country code'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

# we need to create the views for the countries, shipping zones, and service types
class CountryViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    def get_queryset(self):
        country_type = self.request.query_params.get('country_type')
        if country_type:
            return Country.objects.filter(country_type=country_type)
        return Country.objects.all()
    serializer_class = CountrySerializer

class ShippingZoneViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    queryset = ShippingZone.objects.all()
    serializer_class = ShippingZoneSerializer

class ServiceTypeViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    queryset = ServiceType.objects.all()
    serializer_class = ServiceTypeSerializer

@extend_schema(tags=['shipping-rates'])
class ShippingRateCalculatorView(APIView):
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(
        summary="Calculate shipping rate",
        description="Calculate shipping rate with detailed breakdown",
        request=ShippingCalculatorSerializer
    )
    def post(self, request):
        """Calculate shipping rate with detailed cost breakdown"""
        from shipments.utils import calculate_shipping_cost
        
        serializer = ShippingCalculatorSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        data = serializer.validated_data
        
        # Prepare dimensions if provided
        dimensions = None
        if all(key in data for key in ['length', 'width', 'height']):
            dimensions = {
                'length': data['length'],
                'width': data['width'],
                'height': data['height']
            }
        
        # Extract extras data from request if provided
        extras_data = request.data.get('additional_charges', None)
        
        # Call our utility function to calculate shipping cost
        cost_breakdown = calculate_shipping_cost(
            sender_country_id=data['origin_country'],
            recipient_country_id=data['destination_country'],
            service_type_id=data['service_type'],
            weight=data.get('weight'),
            dimensions=dimensions,
            city_id=request.data.get('city'),
            extras_data=extras_data
        )
        
        # Check for errors
        if cost_breakdown['errors']:
            return Response(
                {'errors': cost_breakdown['errors']},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get route and service details for response
        try:
            from shipping_rates.models import (Country, ServiceType,
                                               ShippingZone)
            
            origin = Country.objects.get(id=data['origin_country'])
            destination = Country.objects.get(id=data['destination_country'])
            service_type = ServiceType.objects.get(id=data['service_type'])
            
            # Find shipping zone
            zone = ShippingZone.objects.filter(
                departure_countries=origin,
                destination_countries=destination,
                is_active=True
            ).first()
            
            # Build response with route and service details
            response_data = {
                'route': {
                    'origin': {
                        'id': origin.id,
                        'name': origin.name,
                        'code': origin.code
                    },
                    'destination': {
                        'id': destination.id,
                        'name': destination.name,
                        'code': destination.code
                    }
                },
                'service': {
                    'id': service_type.id,
                    'name': service_type.name,
                    'delivery_time': service_type.delivery_time,
                    'price': float(cost_breakdown['service_price'])
                },
                'weight': {
                    'actual': float(data.get('weight', 0) or 0),
                    'volumetric': float(cost_breakdown.get('volumetric_weight', 0) or 0),
                    'chargeable': float(cost_breakdown.get('chargeable_weight', 0) or 0)
                }
            }
            
            if zone:
                response_data['route']['zone'] = {
                    'id': zone.id,
                    'name': zone.name
                }
            
            # Include volumetric details if available
            if 'volumetric' in cost_breakdown:
                response_data['weight_calculation'] = cost_breakdown['volumetric']
            
            # Add rate details
            if 'per_kg_rate' in cost_breakdown:
                response_data['rate_details'] = {
                    'per_kg_rate': float(cost_breakdown['per_kg_rate']),
                    'weight_charge': float(cost_breakdown['weight_charge'])
                }
            
            # Add cost breakdown to response
            response_data['cost_breakdown'] = {
                'weight_charge': float(cost_breakdown['weight_charge']),
                'service_price': float(cost_breakdown['service_price']),
                'city_delivery_charge': float(cost_breakdown['city_delivery_charge']),
                'additional_charges': cost_breakdown['additional_charges'],
                'extras': cost_breakdown['extras'],
                'total_cost': float(cost_breakdown['total_cost'])
            }
            
            # Add extras total if available
            if 'extras_total' in cost_breakdown:
                response_data['cost_breakdown']['extras_total'] = float(cost_breakdown['extras_total'])
            
            return Response(response_data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    
class ExtrasView(APIView):
    permission_classes = [permissions.AllowAny]
    def get(self, request):
        extras = Extras.objects.all()
        serializer = ExtrasSerializer(extras, many=True)
        return Response(serializer.data)

class CurrencyConversionAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request, format=None):
        serializer = CurrencyConversionSerializer(data=request.data)
        if serializer.is_valid():
            from_currency_code = serializer.validated_data['from_currency'].upper()
            to_currency_code = serializer.validated_data['to_currency'].upper()
            from_amount = serializer.validated_data['from_amount']

            # Check for existence of both currencies in the database
            try:
                from_currency = Currency.objects.get(code=from_currency_code)
                to_currency = Currency.objects.get(code=to_currency_code)
            except Currency.DoesNotExist:
                return Response(
                    {"error": "One or both of the specified currencies were not found."},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Convert from the source currency to MYR, then MYR to the target currency.
            # If rate is defined as: 1 MYR = X Currency, then:
            # 1. Convert source amount to MYR by dividing by from_currency.conversion_rate
            # 2. Convert MYR to target currency by multiplying by to_currency.conversion_rate
            amount_in_myr = from_amount / from_currency.conversion_rate
            converted_amount = amount_in_myr * to_currency.conversion_rate

            return Response({
                "from_currency": from_currency_code,
                "to_currency": to_currency_code,
                "from_amount": str(from_amount),
                "converted_amount": str(round(converted_amount, 2))
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class CurrencyAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    def get(self, request):
        currencies = Currency.objects.all()
        serializer = CurrencySerializer(currencies, many=True)
        return Response(serializer.data)    
