from django.core.management.base import BaseCommand

from accounts.models import User
from core.utils import decrypt_text


class Command(BaseCommand):
    help = 'Decrypts and displays a user password for testing purposes'

    def add_arguments(self, parser):
        parser.add_argument('user_id', type=str, help='The ID of the user whose password to decrypt')

    def handle(self, *args, **options):
        user_id = options['user_id']
        
        try:
            user = User.objects.get(id=user_id)
            
            if not user.plain_password:
                self.stdout.write(
                    self.style.ERROR(f"User {user_id} has no stored encrypted password.")
                )
                return
                
            try:
                # Try to use the get_plain_password method if it exists
                if hasattr(user, 'get_plain_password'):
                    decrypted = user.get_plain_password()
                else:
                    # Fall back to manual decryption
                    decrypted = decrypt_text(user.plain_password)
                
                self.stdout.write(
                    self.style.SUCCESS(f"User ID: {user_id}")
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Phone: {user.phone_number}")
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Decrypted password: {decrypted}")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error decrypting password: {str(e)}")
                )
                
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"No user found with ID: {user_id}")
            ) 