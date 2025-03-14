import re

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import capfirst

User = get_user_model()

class Command(BaseCommand):
    help = 'Create a superuser with a phone number'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--phone_number',
            dest='phone_number',
            default=None,
            help='Specifies the phone number for the superuser.',
        )
        parser.add_argument(
            '--email',
            dest='email',
            default=None,
            help='Specifies the email for the superuser.',
        )
        parser.add_argument(
            '--password',
            dest='password',
            default=None,
            help='Specifies the password for the superuser.',
        )
    
    def handle(self, *args, **options):
        phone_number = options['phone_number']
        email = options['email']
        password = options['password']
        
        # Validate phone number
        if phone_number:
            if not re.match(r'^\d+$', phone_number):
                raise CommandError('Phone number must contain only digits.')
            
            if User.objects.filter(phone_number=phone_number).exists():
                raise CommandError('A user with this phone number already exists.')
        else:
            phone_number = self._get_input('Phone number')
            
            # Validate phone number
            while not re.match(r'^\d+$', phone_number) or User.objects.filter(phone_number=phone_number).exists():
                if not re.match(r'^\d+$', phone_number):
                    self.stderr.write('Phone number must contain only digits.')
                else:
                    self.stderr.write('A user with this phone number already exists.')
                phone_number = self._get_input('Phone number')
        
        # Get email if not provided, but make it optional
        if not email:
            email = input('Email address (optional, press enter to skip): ') or None
        
        # Get password if not provided
        if not password:
            password = self._get_password()
        
        # Create the superuser with phone number
        user = User.objects.create_superuser(
            email=email,
            password=password,
            phone_number=phone_number,
        )
        
        self.stdout.write(self.style.SUCCESS(f'Superuser created successfully with phone number {phone_number}'))
    
    def _get_input(self, field_name):
        """Get input from the user for a field."""
        return input(f'{capfirst(field_name)}: ')
    
    def _get_password(self):
        """Get password input from the user."""
        import getpass
        
        password = getpass.getpass()
        password_confirmation = getpass.getpass('Password (again): ')
        
        if password != password_confirmation:
            self.stderr.write('Error: Your passwords didn\'t match.')
            return self._get_password()
        
        if password.strip() == '':
            self.stderr.write('Error: Blank passwords aren\'t allowed.')
            return self._get_password()
        
        return password 