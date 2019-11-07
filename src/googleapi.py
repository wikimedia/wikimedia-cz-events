#!/usr/bin/env python
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

import os
import simplejson as json
import string
from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

CLIENT_SECRET_FILE = 'client_secret.json'
SCOPES = 'https://www.googleapis.com/auth/spreadsheets'

def get_credentials():
	"""Gets valid user credentials from storage.

	If nothing has been stored, or if the stored credentials are invalid,
	the OAuth2 flow is completed to obtain the new credentials.

	Returns:
		Credentials, the obtained credential.
	"""
	credential_dir = '../credentials'
	if not os.path.exists(credential_dir):
		os.makedirs(credential_dir)
	credential_path = os.path.join(credential_dir, 'update_email_list.json')

	store = Storage(credential_path)
	credentials = store.get()
	if not credentials or credentials.invalid:
		flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
		flow.user_agent = 'Wikimedia CZ events'
		flags = None
		credentials = tools.run_flow(flow, store, flags)
		print('Storing credentials to ' + credential_path)
	return credentials

def get_letter(index):
	overflow = -1
	while index > len(string.ascii_uppercase):
		index -= len(string.ascii_uppercase)
		overflow += 1
	res = ""
	if overflow != -1:
		res += string.ascii_uppercase[overflow]
	res += string.ascii_uppercase[index]
	return res


def confirm_participant(table_id, mail, confirmed=True, sheet="Účastníci"):
	credentials = get_credentials()
	service = discovery.build('sheets', 'v4', credentials=credentials)
	spreadsheets = service.spreadsheets()
	header = spreadsheets.values().get(spreadsheetId=table_id, range='%s!A1:AZ1' % sheet).execute().get('values', [])[0]
	email_item = None
	confirmed_item = None
	for i in range(len(header)):
		item = header[i]
		if item == "E-mailová adresa":
			email_item = get_letter(i)
		if item == "Potvrzen?":
			confirmed_item = get_letter(i)
	emails = spreadsheets.values().get(spreadsheetId=table_id, range="%s!%s2:%s300" % (sheet, email_item, email_item)).execute().get('values', [])
	participant_id = None
	for i in range(len(emails)):
		email = emails[i][0]
		if email == mail:
			participant_id = i + 2
			break
	
	participantRange = "%s!%s%s:%s%s" % (sheet, confirmed_item, participant_id, confirmed_item, participant_id)
	if confirmed:
		confirmed_value = "Y"
	else:
		confirmed_value = "N"
	request = spreadsheets.values().update(spreadsheetId=table_id, range=participantRange, valueInputOption="RAW", body={
		"range": participantRange,
		"values": [
			[ confirmed_value ]
		]
	}).execute()

if __name__ == "__main__":
	confirm_participant("1T7EcedxI8NZ9yM_iKMSB1opsPiOlD_bWyXXH6jEiJyQ", "martin.urbanec@wikimedia.cz")