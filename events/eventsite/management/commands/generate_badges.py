from django.core.management.base import BaseCommand
from django.conf import settings
from eventsite.models import Event, Registration
import cloudconvert
import operator
import datetime
import os

import simplejson as json

class Command(BaseCommand):
    help = "Maintenance command to generate badges"

    def add_arguments(self, parser):
        parser.add_argument('--event', dest='event', help='Name', required=True)

    def handle(self, **options):
        cloudconvert_api = cloudconvert.Api(settings.CLOUDCONVERT_API_KEY)
        event = Event.objects.get(name=options.get('event'))
        ordering_data = {}
        for r in event.registration_set.all():
            ordering_data[r.id] = "%s %s" % (r.data.get('last_name'), r.data.get('first_name'))
        
        sorted_data = sorted(ordering_data.items(), key=operator.itemgetter(1))
        del(ordering_data)
        i = 0
        page = 0
        cloudconvert_data = []
        for id, name in sorted_data:
            r = Registration.objects.get(id=id)
            if i % 9 == 0:
                i = 0
                cloudconvert_data.append({
                    "subtopic": "Wikimedia Česká republika",
                    "event": event.name,
                    "year": str(datetime.date.today().year)
                })
            if r.data.get('display_on_card') == "" or r.data.get('display_on_card') == "nepřeji si mít žádnou visačku":
                continue # this is a blocker for generating a badge
            cloudconvert_data[page]["big_name_%s" % str(i+1)] = r.big_name()
            cloudconvert_data[page]["small_name_%s" % str(i+1)] = r.small_name()
            i += 1
            if i % 9 == 0 and i != 0:
                page += 1
        names = ["big_name_%s" % x for x in range(1, 10)] + ["small_name_%s" % x for x in range(1, 10)]
        i = 0
        if not os.path.exists('/var/www/events.wikimedia.cz/deploy/pdfs'):
            os.mkdir('/var/www/events.wikimedia.cz/deploy/pdfs')
        files = []
        for data in cloudconvert_data:
            for name in names:
                if name not in data:
                    data[name] = " "
            process = cloudconvert_api.convert({
                "inputformat": "docx",
                "outputformat": "pdf",
                "input": "download",
                "file": "https://events.wikimedia.cz/static/badges.docx",
                "converteroptions": {
                    "page_range": None,
                    "optimize_print": True,
                    "pdf_a": None,
                    "input_password": None,
                    "templating": data
                },
                "wait": True
            })
            f = "/var/www/events.wikimedia.cz/deploy/pdfs/%s.pdf" % str(i)
            print(f)
            process.download(f)
            files.append(f.replace('/var/www/', 'https://').replace('/deploy', ''))
            i += 1
        process = cloudconvert_api.createProcess({
            "mode": "combine",
            "inputformat": "pdf",
            "outputformat": "pdf"
        })
        process.start({
            "mode": "combine",
            "input": "download",
            "files": files,
            "outputformat": "pdf",
            'save': True
        })
        process.wait()
        process.download('/var/www/events.wikimedia.cz/deploy/pdfs/badges.pdf')
        print('Browse to https://events.wikimedia.cz/pdfs/badges.pdf and download your badges')
