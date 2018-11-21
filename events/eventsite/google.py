from django.conf import settings
import os

# For communication with Google API
from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage
import httplib2

column_map = {
    "Časová značka": "timestamp",
    "Jméno": "first_name",
    "Příjmení": "last_name",
    "Pohlaví": "sex",
    "E-mailová adresa": "email",
    "Uživatelské jméno na Wikipedii": "username",
    "Na jmenovce bych chtěl/a mít uvedeno": "display_on_card",
    "Místo, kde žijete": "place",
    "Moje aktivita na Wikipedii": "activity",
    "S čím byste z Wikikonference rád/a odcházel/a? Co byste se rád/a dozvěděl/a?": "expectations",
    "Odebíráte náš newsletter?": "newsletter_bool",
    "Jaké oblasti vás zajímají?": "newsletter_topics",
    "Chcete, abychom vám zajistili oběd?": "lunch",
    "Prostor pro cokoli, co byste nám chtěli sdělit": "other",
    "Stav ověření registrace": "verified",
    "Chcete si objednat WikiTričko?": "tshirt",
    "Velikost": "tshirt_size",
    "Střih": "tshirt_type",
}

SCOPES = 'https://www.googleapis.com/auth/spreadsheets'
APPLICATION_NAME = "Wikimedia Events"

class CredentialsConfig():
    def __init__(self, noauth_local_webserver=False, logging_level="DEBUG"):
        self.noauth_local_webserver = noauth_local_webserver
        self.logging_level = logging_level
        self.auth_host_port = [10256]
        self.auth_host_name = '127.0.0.1'

def get_credentials(credential_config):
    credential_dir = os.path.join(settings.BASE_DIR, 'events')
    credential_path = os.path.join(credential_dir, 'google_creds.json')

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(os.path.join(credential_dir, 'client_secret.json'), SCOPES)
        flow.user_agent = APPLICATION_NAME
        credentials = tools.run_flow(flow, store, credential_config)
        print('Storing credentials to ' + credential_path)
    return credentials

def get_google_service(type, version):
    credentials = get_credentials(CredentialsConfig(True, 'DEBUG'))
    http = credentials.authorize(httplib2.Http())
    return discovery.build(type, version, http=http)

def get_range_from_spreadsheet(table_id, list, range, service):
    return service.spreadsheets().values().get(spreadsheetId=table_id, range="'%s'!%s" % (list, range)).execute().get('values')