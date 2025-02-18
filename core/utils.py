import random
import re
from django.db import models
from django.utils import timezone

class SixDigitIDMixin(models.Model):
    id = models.CharField(primary_key=True, max_length=12, editable=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = self.generate_unique_id()
        super().save(*args, **kwargs)

    def generate_unique_id(self):
        prefix = self.get_prefix()
        year = str(timezone.now().year)[-2:]
        while True:
            sequence = str(random.randint(1000, 9999))
            new_id = f"{prefix}{year}{sequence}"
            if not self.__class__.objects.filter(id=new_id).exists():
                return new_id

    def get_prefix(self):
        """
        Automatically generate 3-letter prefix from model name.
        Examples:
        - Buy4MeRequest -> BUY
        - ShipmentTracking -> SHP
        - UserProfile -> USR
        - PaymentTransaction -> PAY
        """
        model_name = self.__class__.__name__
        
        # Handle special cases first
        if model_name.startswith('Buy4Me'):
            return 'BUY' if 'Request' in model_name else 'ITM'
            
        # Extract capital letters
        capitals = ''.join(c for c in model_name if c.isupper())
        if len(capitals) >= 3:
            return capitals[:3]
            
        # If not enough capitals, extract first letter of each word
        words = re.findall('[A-Z][^A-Z]*', model_name)
        if words:
            prefix = ''.join(word[0] for word in words)
            return (prefix + model_name[0] * (3 - len(prefix)))[:3]
            
        # Fallback: first 3 letters of model name
        return model_name[:3].upper() 