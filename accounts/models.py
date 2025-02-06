from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

class User(AbstractUser):
    """
    Custom user model that extends Django's AbstractUser
    """
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')

    def __str__(self):
        return self.email 