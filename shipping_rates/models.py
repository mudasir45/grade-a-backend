from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.utils import SixDigitIDMixin


class Country(SixDigitIDMixin, models.Model):
    class CountryType(models.TextChoices):
        DEPARTURE = 'DEPARTURE', _('Departure')
        DESTINATION = 'DESTINATION', _('Destination')

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=2)
    country_type = models.CharField(
        max_length=12, 
        choices=CountryType.choices, 
        default=CountryType.DESTINATION
    )
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name_plural = 'Countries'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['code', 'country_type'],
                name='unique_country_code_type'
            )
        ]
    def save(self, *args, **kwargs):
        self.code = self.code.upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.code}) - {self.get_country_type_display()}"

    def get_zones(self):
        """Get all zones this country belongs to based on its type"""
        if self.country_type == self.CountryType.DEPARTURE:
            return self.departure_zones.all()
        return self.destination_zones.all()

class ShippingZone(SixDigitIDMixin, models.Model):
    name = models.CharField(max_length=100)
    departure_countries = models.ManyToManyField(
        Country, 
        related_name='departure_zones',
        limit_choices_to={'country_type': Country.CountryType.DEPARTURE}
    )
    destination_countries = models.ManyToManyField(
        Country, 
        related_name='destination_zones',
        limit_choices_to={'country_type': Country.CountryType.DESTINATION}
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    def get_rate_for_weight(self, weight, service_type=None):
        """Get applicable rate for given weight and service type"""
        rates = WeightBasedRate.objects.filter(
            zone=self,
            is_active=True,
            min_weight__lte=weight,
            max_weight__gte=weight
        )
        if service_type:
            rates = rates.filter(service_type=service_type)
        return rates.first()

class ServiceType(SixDigitIDMixin, models.Model):
    name = models.CharField(max_length=100)  # e.g., Express, Standard, Economy
    description = models.TextField()
    delivery_time = models.CharField(max_length=50)  # e.g., "2-3 business days"
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class WeightBasedRate(SixDigitIDMixin, models.Model):
    zone = models.ForeignKey(ShippingZone, on_delete=models.CASCADE)
    service_type = models.ForeignKey(ServiceType, on_delete=models.CASCADE)
    min_weight = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    max_weight = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    regulation_charge = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    per_kg_rate = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['zone', 'service_type', 'min_weight', 'max_weight']

    def __str__(self):
        return f"{self.zone} - {self.service_type} ({self.min_weight}kg to {self.max_weight}kg)"

class DimensionalFactor(SixDigitIDMixin, models.Model):
    """For volumetric weight calculation"""
    service_type = models.ForeignKey(ServiceType, on_delete=models.CASCADE)
    factor = models.IntegerField(
        help_text=_("Dimensional factor (e.g., 5000 means length*width*height/5000)"),
        default=5000
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.service_type} - Factor: {self.factor}"

class AdditionalCharge(SixDigitIDMixin, models.Model):
    """Model for additional charges that can be applied to shipments"""
    class ChargeType(models.TextChoices):
        FIXED = 'FIXED', _('Fixed Amount')
        PERCENTAGE = 'PERCENTAGE', _('Percentage of Base Cost')

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    charge_type = models.CharField(
        max_length=20,
        choices=ChargeType.choices,
        default=ChargeType.FIXED
    )
    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    zones = models.ManyToManyField(
        'ShippingZone',
        related_name='additional_charges'
    )
    service_types = models.ManyToManyField(
        'ServiceType',
        related_name='additional_charges'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Additional Charge')
        verbose_name_plural = _('Additional Charges')
        ordering = ['name']

    def __str__(self):
        return self.name 

class Extras(SixDigitIDMixin, models.Model):
    class ChargeType(models.TextChoices):
        FIXED = 'FIXED', _('Fixed Amount')
        PERCENTAGE = 'PERCENTAGE', _('Percentage of Base Cost')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    charge_type = models.CharField(
        max_length=20,
        choices=ChargeType.choices,
        default=ChargeType.FIXED
    )
    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
    
class Currency(models.Model):
    code = models.CharField(max_length=10, unique=True)  # e.g., 'USD', 'EUR', 'MYR'
    name = models.CharField(max_length=100)
    conversion_rate = models.DecimalField(
        max_digits=12, decimal_places=4,
        help_text="Conversion rate relative to MYR (Malaysian Ringgit)"
    )

    def __str__(self):
        return self.code