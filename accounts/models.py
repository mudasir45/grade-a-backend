from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.utils import generate_unique_id
from shipping_rates.models import Country

class User(AbstractUser):
    """
    Custom user model that extends Django's AbstractUser
    """
    id = models.CharField(primary_key=True, max_length=12, editable=False)
    
    class UserType(models.TextChoices):
        WALK_IN = 'WALK_IN', _('Walk In')
        BUY4ME = 'BUY4ME', _('Buy4Me')
        ADMIN = 'ADMIN', _('Admin')
        SUPER_ADMIN = 'SUPER_ADMIN', _('Super Admin')

    user_type = models.CharField(
        max_length=20,
        choices=UserType.choices,
        default=UserType.WALK_IN
    )
    phone_number = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    is_verified = models.BooleanField(default=False)
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True)
    default_shipping_method = models.ForeignKey(
        'shipping_rates.ServiceType',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='default_shipping_method'
    )
    preferred_currency = models.CharField(max_length=10, blank=True, default='USD')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = generate_unique_id('USR')
        super().save(*args, **kwargs) 