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

# Stuff for CLI
import click

# For sending mails
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# For communication with Google API
from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

# Flask constants
__dir__ = os.path.dirname(__file__)

# Google API constants
SCOPES = 'https://www.googleapis.com/auth/drive.readonly'
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

app = Flask(__name__)

# Load configuration from YAML file
app.config.update(
    yaml.safe_load(open(os.path.join(__dir__, os.environ.get('FLASK_CONFIG_FILE', 'config.yaml')))))

# Init DB clients
db = SQLAlchemy(app)
migrate = Migrate(app, db)

class Registration(db.Model):
    email = db.Column(db.String(255), nullable=False, primary_key=True)
    verified = db.Column(db.Boolean, nullable=False, default=False)

    def verification_token(self):
        return hashlib.md5((self.email + app.config.get('SECRET_KEY')).encode('utf-8')).hexdigest()

@app.cli.command()
def initdb():
    db.drop_all()
    db.create_all()

def emails(table_id, list, email_column, noauth_local_webserver, logging_level):
    """
    This yields participant's email addresses
    """
    credentials = get_credentials(CredentialsConfig(noauth_local_webserver, logging_level))
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('sheets', 'v4', http=http)
    i = 2
    while True:
        values = service.spreadsheets().values().get(spreadsheetId=table_id, range="'%s'!%s%s" % (list, email_column, str(i))).execute().get('values')
        i += 1
        if values is not None:
            yield values[0][0]
        else:
            break

def sendmail(s, from_address, from_name, to, subject, mail_text_file, debug_to=None):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = "%s <%s>" % (from_name, from_address)
    msg['To'] = to
    html = open(mail_text_file).read()
    html_part = MIMEText(html, 'html')
    msg.attach(html_part)
    if debug_to is not None:
        actual_mail = debug_to
    else:
        actual_mail = to
    s.sendmail(from_address, actual_mail, msg.as_string())


@app.cli.command()
@click.option('--table-id', required=True, help='ID of Google Spreadsheet containing your participants')
@click.option('--list', required=True, help='Name of list containing your participants; please use its full name')
@click.option('--email-column', required=True, help='Letter of column containing email addresses of your participants; please use A for first column, B for second etc.')
@click.option('--mail-text-file', required=True, help='Path to file containing HTML email that will be send to your participants')
@click.option('--subject', default="[Wikikonference] Potvrzení registrace", help='Subject of your mails', show_default=True)
@click.option('--from-address', default='wikikonference@wikimedia.cz', help='Address the mails will be coming from', show_default=True)
@click.option('--from-name', default='Wikikonference', help='Display name that will see participants next to from address', show_default=True)
@click.option('--smtp-server', default='smtp-relay.gmail.com', help='Hostname of your mail server', show_default=True)
@click.option('--debug-to', default=None, help='[debug] This will force all mails to come to specified mailbox')
@click.option('--noauth_local_webserver', is_flag=True, help='Use this on headless machine')
@click.option('--logging-level', default='DEBUG')
def request_registration_confirm(**kwargs):
    s = smtplib.SMTP(kwargs.get('smtp_server'))
    for email in emails(kwargs.get('table_id'), kwargs.get('list'), kwargs.get('email_column'), kwargs.get('noauth_local_webserver'), kwargs.get('logging_level')):
        sendmail(s, kwargs.get('from_address'), kwargs.get('from_name'), email, kwargs.get('subject'), kwargs.get('mail_text_file'), kwargs.get('debug_to'))
        break
    s.quit()

def confirm_registration(email, token):
    try:
        r = Registration.query.filter_by(email=email, verified=False).one()
    except:
        return False
    if r.verification_token() == token or token == True:
        r.verified = True
        db.session.add(r)
        return True
    else:
        return False

@app.cli.command()
@click.option('--email', required=True, help='Email address you want to confirm')
def confirm(email):
    confirm_registration(email, True)

@app.cli.command()
@click.option('--display', default='all', show_default=True, type=click.Choice(('all', 'unverified', 'verified')))
def list_registrations(display):
    if display == 'all':
        rs = Registration.query.all()
    elif display == 'unverified':
        rs = Registration.query.filter_by(verified=False)
    elif display == 'verified':
        rs = Registration.query.filter_by(verified=True)
    for r in rs:
        click.echo("* %s" % r.email)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/verify/<email>/<token>')
def verify(email, token):
    result = confirm_registration(email, token)
    if result:
        return render_template('verified.html')
    else:
        return render_template('unverified.html')

if __name__ == "__main__":
    app.run(debug=True, threaded=True)
