# -*- coding: utf-8 -*-
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

# Stuff necessary for basic Flask
import os
import yaml
from flask import redirect, request, jsonify, render_template, url_for, make_response
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import hashlib
import httplib2
import datetime
import time
import string
import simplejson as json

# Stuff for CLI
import click

# For sending mails
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# For visacky generation
import cloudconvert

# For communication with Google API
from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

# Flask constants
__dir__ = os.path.dirname(__file__)

# Google API constants
SCOPES = 'https://www.googleapis.com/auth/spreadsheets'
CLIENT_SECRET_FILE = os.path.join(__dir__, 'client_secret.json')
APPLICATION_NAME = 'Wikiconference'

class CredentialsConfig():
    def __init__(self, noauth_local_webserver=False, logging_level="DEBUG"):
        self.noauth_local_webserver = noauth_local_webserver
        self.logging_level = logging_level
        self.auth_host_port = [10256]
        self.auth_host_name = '127.0.0.1'

def get_credentials(credential_config):
    credential_dir = __dir__
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir, 'google_creds.json')

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        credentials = tools.run_flow(flow, store, credential_config)
        print('Storing credentials to ' + credential_path)
    return credentials

app = Flask(__name__, static_folder='../static')

# Load configuration from YAML file
config = yaml.safe_load(open(os.path.join(__dir__, os.environ.get('FLASK_CONFIG_FILE', 'config.yaml'))))
app.config.update(config)

# Init DB clients
db = SQLAlchemy(app)
migrate = Migrate(app, db)

@app.cli.command()
def initdb():
    db.drop_all()
    db.create_all()

column_map = {
    "timestamp": "Časová značka",
    "first_name": "Jméno",
    "last_name": "Příjmení",
    "sex": "Pohlaví",
    "email": "E-mailová adresa",
    "username": "Uživatelské jméno na Wikipedii",
    "display_on_card": "Na jmenovce bych chtěl/a mít uvedeno",
    "place": "Místo, kde žijete",
    "activity": "Moje aktivita na Wikipedii",
    "expectations": "S čím byste z Wikikonference rád/a odcházel/a? Co byste se rád/a dozvěděl/a?",
    "newsletter_bool": "Odebíráte náš newsletter?",
    "newsletter_topics": "Jaké oblasti vás zajímají?",
    "lunch": "Chcete, abychom vám zajistili oběd?",
    "other": "Prostor pro cokoli, co byste nám chtěli sdělit",
    "verified": "Stav ověření registrace"
}

def order_query_by_variable(query, variable):
    ordering_dict = {}
    for obj in query.all():
        ordering_dict[obj.id] = obj.get_value(variable)
    for id in sorted(ordering_dict, key=ordering_dict.get):
        yield type(query.first()).query.get(id)

class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    form = db.Column(db.String(255), nullable=False)
    sheet_data = db.Column(db.Text, nullable=False, default={})
    verified = db.Column(db.Boolean, nullable=False, default=False)
    row = db.Column(db.Integer, nullable=False, default=-1)

    def verification_link(self):
        return "https://events.wikimedia.cz/verify/%s/%s/%s" % (self.form, self.get_value("email"), self.verification_token())

    def verification_token(self):
        return hashlib.md5((self.get_value('email') + app.config.get('SECRET_KEY')).encode('utf-8')).hexdigest()
    
    @property
    def data(self):
        return json.loads(self.sheet_data)
    
    @data.setter
    def data(self, value):
        self.sheet_data = json.dumps(value)
    
    def get_value(self, variable):
        return self.data.get(column_map[variable])

    def verified_string(self):
        if self.verified:
            return "Ověřeno"
        else:
            return "Neověřeno"

    def greeting(self):
        if self.get_value("sex") == "Muž":
            return "Vážený pane %s," % self.get_value('last_name')
        elif self.get_value("sex") == "Žena":
            return "Vážená paní %s," % self.get_value('last_name')
        else:
            return "Vážená paní, vážený pane,"

    def switch_on_sex(self, male, female, universal=None):
        if self.get_value("sex") == "Muž":
            return male
        elif self.get_value("sex") == "Žena":
            return female
        elif universal == None:
            return male
        else:
            return universal

    def big_name(self):
        if self.get_value("display_on_card") == "občanské jméno" or self.get_value("display_on_card") == "občanské jméno i uživatelské jméno na Wikipedii":
            return "%s %s" % (self.get_value("first_name"), self.get_value("last_name"))
        elif self.get_value("display_on_card") == "uživatelské jméno na Wikipedii":
            username = self.get_value("username")[0].upper() + self.get_value("username")[1:]
            return "Wikipedista:%s" % username
        else:
            return " "

    def small_name(self):
        if self.get_value("display_on_card") == "občanské jméno i uživatelské jméno na Wikipedii":
            username = self.get_value("username")[0].upper() + self.get_value("username")[1:]
            return "Wikipedista:%s" % username
        else:
            return " "
    
    def allow_realname(self):
        if "občanské jméno" in self.get_value("display_on_card"):
            return True
        else:
            return False
    
    def allow_username(self):
        if "uživatelské jméno" in self.get_value("display_on_card"):
            return True
        else:
            return False

class Event(db.Model):
    id = db.Column(db.String(255), primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    list = db.Column(db.String(255), nullable=False)
    sheet_header = db.Column(db.Text, nullable=False, default="[]")

    @property
    def header(self):
        return json.loads(self.sheet_header)
    
    @header.setter
    def header(self, value):
        self.sheet_header = json.dumps(value)

    def variable_to_letter(self, variable):
        return string.ascii_uppercase[self.header.index(column_map[variable])]

def year():
    return datetime.date.today().year

@app.cli.command()
@click.option('--name', required=True, help="Event name")
@click.option('--table-id', required=True, help='ID of your Google Spreadsheet table containing participants')
@click.option('--list', required=True, help='Name of list containing your participants; please use its full name')
def new_event(name, table_id, list):
    e = Event(id=table_id, name=name, list=list)
    db.session.add(e)
    db.session.commit()

@app.cli.command()
def list_events():
    es = Event.query.all()
    for e in es:
        print("* %s" % e.name)

def get_google_service(type, version, noauth_local_webserver, logging_level):
    credentials = get_credentials(CredentialsConfig(noauth_local_webserver, logging_level))
    http = credentials.authorize(httplib2.Http())
    return discovery.build(type, version, http=http)

def get_range_from_spreadsheet(table_id, list, range, service):
    return service.spreadsheets().values().get(spreadsheetId=table_id, range="'%s'!%s" % (list, range)).execute().get('values')

@app.cli.command()
@click.option('--event', required=True, help="Event name")
@click.option('--skip-rows', default=0, type=int, help='This allows you to skip some rows if you want to start with later than second row')
@click.option('--download-at-time', default=30, type=int, help='Use this if you want to download less or more rows from the table at a time.')
@click.option('--noauth_local_webserver', is_flag=True, help='Use this on headless machine')
@click.option('--logging-level', default='DEBUG')
def pull(event, skip_rows, download_at_time, noauth_local_webserver, logging_level):
    service = get_google_service('sheets', 'v4', noauth_local_webserver, logging_level)
    event = Event.query.filter_by(name=event).one()
    Registration.query.filter_by(form=event.id).delete()
    db.session.commit()
    header = get_range_from_spreadsheet(event.id, event.list, 'A1:T1', service)[0]
    if header is None:
        return # TODO: Raise error
    if event.header == []:
        event.header = header
        db.session.commit()
    row_num = 2 + skip_rows
    while True:
        rows = get_range_from_spreadsheet(event.id, event.list, 'A%s:T%s' % (str(row_num), str(row_num + download_at_time)), service)
        if rows is None:
            break
        for row in rows:
            reg_data = {}
            i = 0
            for item in row:
                if i >= len(header):
                    break # we are out of header, which always mean notes we won't need
                reg_data[header[i]] = item
                i += 1
            reg = Registration(form=event.id, data=reg_data, row=row_num)
            db.session.add(reg)
            db.session.commit()
            row_num += 1
    return

# TODO: Rewrite to addapt to new pull method
@app.cli.command()
@click.option('--event', required=True, help="Event name")
@click.option('--noauth_local_webserver', is_flag=True, help='Use this on headless machine')
@click.option('--logging-level', default='DEBUG')
def push(event, noauth_local_webserver, logging_level):
    service = get_google_service('sheets', 'v4', noauth_local_webserver, logging_level)
    event = Event.query.filter_by(name=event).one()
    verified_column = event.variable_to_letter('verified')
    for r in Registration.query.filter_by(form=event.id).all():
        payload = {
            "range": "'%s'!%s%s" % (event.list, verified_column, str(r.row)),
            "values": [
                [
                    r.verified_string()
                ]
            ]
        }
        service.spreadsheets().values().update(spreadsheetId=event.id, range=payload["range"], valueInputOption="RAW", body=payload).execute()

def sendmail(s, from_address, from_name, to, subject, mail_text_file, debug_to=None, variables={}):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = "%s <%s>" % (from_name, from_address)
    msg['To'] = to
    html = open(mail_text_file).read()
    for variable in variables:
        html = html.replace('{{%s}}' % variable.upper(), variables[variable])
    html_part = MIMEText(html, 'html')
    msg.attach(html_part)
    if debug_to is not None:
        actual_mail = debug_to
    else:
        actual_mail = to
    s.sendmail(from_address, actual_mail, msg.as_string())


@app.cli.command()
@click.option('--event', required=True, help='Event name')
@click.option('--subject', default="[Wikikonference] Zúčastníte se Wikikonference?", help='Subject of your mails', show_default=True)
@click.option('--from-address', default='wikikonference@wikimedia.cz', help='Address the mails will be coming from', show_default=True)
@click.option('--from-name', default='Wikikonference', help='Display name that will see participants next to from address', show_default=True)
@click.option('--smtp-server', default='smtp-relay.gmail.com', help='Hostname of your mail server', show_default=True)
@click.option('--debug-to', default=None, help='[debug] This will force all mails to come to specified mailbox')
def request_registration_confirm(**kwargs):
    table_id = Event.query.filter_by(name=kwargs.get('event')).one().id
    s = smtplib.SMTP(kwargs.get('smtp_server'))
    for r in Registration.query.filter_by(form=table_id).all():
        print("Processing %s" % r.get_value('email'))
        sendmail(
            s,
            kwargs.get('from_address'),
            kwargs.get('from_name'),
            r.get_value('email'),
            kwargs.get('subject'),
            os.path.join(__dir__, 'templates', 'email', 'verify.html'),
            kwargs.get('debug_to'),
            {
                "verify_link": r.verification_link(),
                "greeting": r.greeting(),
                "vyplnil": r.switch_on_sex("vyplnil", "vyplnila", "vyplnil(a)")
            }
        )
    s.quit()

@app.cli.command()
@click.option('--event', required=True, help='Event name')
@click.option('--subject', default="[Wikikonference] Informace pro účastníky", help='Subject of your mails', show_default=True)
@click.option('--from-address', default='wikikonference@wikimedia.cz', help='Address the mails will be coming from', show_default=True)
@click.option('--from-name', default='Wikikonference', help='Display name that will see participants next to from address', show_default=True)
@click.option('--email-file', required=True, help='Path to HTML that will be distributed to your participants via mail', show_default=True)
@click.option('--smtp-server', default='smtp-relay.gmail.com', help='Hostname of your mail server', show_default=True)
@click.option('--debug-to', default=None, help='[debug] This will force all mails to come to specified mailbox')
def mailall(**kwargs):
    table_id = Event.query.filter_by(name=kwargs.get('event')).one().id
    s = smtplib.SMTP(kwargs.get('smtp_server'))
    for r in Registration.query.filter_by(form=table_id).all():
        print("Processing %s" % r.get_value("email"))
        sendmail(
            s,
            kwargs.get('from_address'),
            kwargs.get('from_name'),
            r.get_value('email'),
            kwargs.get('subject'),
            kwargs.get('email_file'),
            kwargs.get('debug_to'),
            {
                "greeting": r.greeting()
            }
        )
    s.quit()

@app.cli.command()
@click.option('--event', required=True, help='Event name')
@click.option('--subtopic', default='Wikimedia Česká republika', help='Subtopic of your event')
def generate_visacky(event, subtopic):
    cloudconvert_api = cloudconvert.Api(config.get('CLOUDCONVERT_API_KEY'))
    event = Event.query.filter_by(name=event).one()
    i = 0
    page = 0
    cloudconvert_data = []
    for r in order_query_by_variable(Registration.query.filter_by(form=event.id), "last_name"):
        if i % 9 == 0:
            i = 0
            cloudconvert_data.append({
                "subtopic": subtopic,
                "event": event.name,
                "year": str(year())
            })
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
            "file": "https://events.wikimedia.cz/static/visacky.docx",
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
    process.download('/var/www/events.wikimedia.cz/deploy/pdfs/visacky.pdf')
    click.echo('Browse to https://events.wikimedia.cz/pdfs/visacky.pdf and download your visackas')

@app.cli.command()
@click.option('--event', required=True, help='Event name')
@click.option('--email', default="info@wikimedia.cz", help='E-mail you want to be on prezenčka')
def generate_prezencka(event, email):
    cloudconvert_api = cloudconvert.Api(config.get('CLOUDCONVERT_API_KEY'))
    event = Event.query.filter_by(name=event).one()
    participants = []
    for r in order_query_by_variable(Registration.query.filter_by(form=event.id), "last_name"):
        if r.allow_realname():
            last_name = r.get_value("last_name")
            first_name = r.get_value("first_name")
        else:
            last_name = "(nechce uvést)"
            first_name = "(nechce uvést)"
        if r.allow_username():
            username = r.get_value("username")
        else:
            username = "(nemá/nechce uvést)"
        participants.append({
            "surname": last_name, # TODO: Replace surname with last_name in template and fix it here
            "first_name": first_name,
            "username": username,
            "email": r.get_value("email")
        })
    process = cloudconvert_api.convert({
        "inputformat": "docx",
        "outputformat": "pdf",
        "input": "download",
        "file": "https://events.wikimedia.cz/static/prezencka.docx",
        "converteroptions": {
            "page_range": None,
            "optimize_print": True,
            "pdf_a": None,
            "input_password": None,
            "templating": {
                "event": event.name,
                "year": year(),
                "email": email,
                "participants": participants
            }
        },
        "wait": True
    })
    process.download('/var/www/events.wikimedia.cz/deploy/pdfs/prezencka.pdf')
    click.echo('Browse to https://events.wikimedia.cz/pdfs/prezencka.pdf and download your visackas')


def confirm_registration(event, email, token):
    try:
        e = Event.query.filter_by(name=event).one()
        r = Registration.query.filter_by(email=email, form=e.id).one()
    except:
        return "unverified"
    if not r.verified:
        if r.verification_token() == token or token == True:
            r.verified = True
            db.session.add(r)
            db.session.commit()
            return "verified"
        else:
            return "unverified"
    else:
        return "already-verified"

@app.cli.command()
@click.option('--event', required=True, help='Event name')
@click.option('--email', required=True, help='Email address you want to confirm')
def confirm(event, email):
    confirm_registration(event, email, True)

@app.cli.command()
@click.option('--event', required=True, help='Event name')
@click.option('--display', default='all', show_default=True, type=click.Choice(('all', 'unverified', 'verified')))
def list_registrations(event, display):
    e = Event.query.filter_by(name=event).one()
    rs = Registration.query.filter_by(form=e.id)
    if display == 'unverified':
        rs = rs.query.filter_by(verified=False)
    elif display == 'verified':
        rs = rs.query.filter_by(verified=True)
    for r in rs.all():
        click.echo("* %s" % r.email)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/verify/<form>/<email>/<token>')
def verify(form, email, token):
    e_name = Event.query.get(form).name
    result = confirm_registration(e_name, email, token)
    if result == "verified":
        return redirect("https://cs.wikipedia.org/wiki/Wikipedie:%s/Registrace_ověřena" % e_name)
    elif result == "already-verified":
        return redirect("https://cs.wikipedia.org/wiki/Wikipedie:%s/Registrace_již_ověřena" % e_name)
    else:
        return redirect("https://cs.wikipedia.org/wiki/Wikipedie:%s/Registrace_neověřena" % e_name)

if __name__ == "__main__":
    app.run(debug=True, threaded=True)
