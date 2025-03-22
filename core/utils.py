import base64
import os
import random
import re

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.conf import settings
from django.db import models
from django.utils import timezone


# Encryption key management
def get_encryption_key():
    """
    Get or generate the encryption key for sensitive data.
    The key is derived from SECRET_KEY for simplicity, but in production
    it would be better to use a separate environment variable.
    """
    # In a production environment, this should come from environment variables
    # or a secure key management system, not derived from SECRET_KEY
    if not hasattr(settings, 'ENCRYPTION_KEY'):
        # Generate a key using PBKDF2
        salt = b'grade_a_express_salt'  # This should ideally be stored securely
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(settings.SECRET_KEY.encode()))
        settings.ENCRYPTION_KEY = key
    
    return settings.ENCRYPTION_KEY

def encrypt_text(text):
    """
    Encrypt a text string using Fernet symmetric encryption.
    Returns a base64 encoded string that can be stored in the database.
    """
    if not text:
        return ""
    
    key = get_encryption_key()
    cipher = Fernet(key)
    encrypted_data = cipher.encrypt(text.encode())
    return base64.urlsafe_b64encode(encrypted_data).decode()

def decrypt_text(encrypted_text):
    """
    Decrypt an encrypted text string using Fernet symmetric encryption.
    Returns the original plaintext or an empty string if decryption fails.
    """
    if not encrypted_text:
        return ""
    
    try:
        key = get_encryption_key()
        cipher = Fernet(key)
        decoded_data = base64.urlsafe_b64decode(encrypted_text)
        return cipher.decrypt(decoded_data).decode()
    except Exception as e:
        # Log error here if needed
        return ""

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

def generate_unique_id(prefix):
    """
    Generate a unique ID with format: PREFIX + YY + 4 random digits
    Example: USR231234
    """
    year = str(timezone.now().year)[-2:]
    sequence = str(random.randint(1000, 9999))
    return f"{prefix}{year}{sequence}" 