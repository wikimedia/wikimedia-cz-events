from eventsite.models import Event
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Allow you to mail participants"

    def add_arguments(self, parser):
        parser.add_argument('--mail-type', dest='mail_type', help="What mail type you want us to send?", required=True)
        parser.add_argument('--event', dest='event', help='Name/ID of event you want to mail participants of', required=True)
        parser.add_argument('--debug-to', dest='debug_to', help='[DEBUG] You can use this to force all mails to come to this mail')

    def handle(self, **options):
        try:
            event = Event.objects.get(id=int(options["event"]))
        except:
            event = Event.objects.get(name=options["event"])
        event.mail_participants(options['mail_type'], debug_to=options["debug_to"])