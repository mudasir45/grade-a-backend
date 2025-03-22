from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User
from core.utils import encrypt_text


class Command(BaseCommand):
    help = 'Encrypts any plain text passwords in the User model'

    def handle(self, *args, **options):
        users_with_plaintext = User.objects.filter(plain_password__isnull=False).exclude(plain_password='')
        updated_count = 0
        
        with transaction.atomic():
            for user in users_with_plaintext:
                try:
                    # Check if the password is already encrypted
                    # (A simple heuristic - encrypted passwords tend to be longer and contain specific characters)
                    if len(user.plain_password) < 100 and '==' not in user.plain_password:
                        # This is likely a plaintext password - encrypt it
                        original_password = user.plain_password
                        user.plain_password = encrypt_text(original_password)
                        user.save(update_fields=['plain_password'])
                        updated_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f"Encrypted password for user: {user.id}")
                        )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"Error encrypting password for user {user.id}: {str(e)}")
                    )
        
        if updated_count == 0:
            self.stdout.write(self.style.WARNING("No plain text passwords found to encrypt."))
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Successfully encrypted {updated_count} passwords.")
            ) 