
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class PhoneNumberBackend(ModelBackend):
    """
    Custom authentication backend that uses phone number to authenticate.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        # The phone number may be passed as username or explicitly in kwargs.
        phone_number = username or kwargs.get('phone_number')
        if phone_number is None or password is None:
            return None
        try:
            user = User.objects.get(phone_number=phone_number)
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            return None
