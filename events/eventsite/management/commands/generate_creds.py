from django.core.management.base import BaseCommand
from eventsite import google

class Command(BaseCommand):
    help = "Maintenance command to force regenerating of credentials"

    def handle(self, **options):
        google.get_google_service('sheets', 'v4')
