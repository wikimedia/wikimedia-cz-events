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
import yaml
from flask import redirect, request, render_template, url_for, flash, jsonify, session
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import requests
import hashlib
import click
import googleapi

app = Flask(__name__, static_folder='../static')

# Load configuration from YAML file
__dir__ = os.path.dirname(__file__)
app.config.update(
	yaml.safe_load(open(os.path.join(__dir__, os.environ.get(
		'FLASK_CONFIG_FILE', 'config.yaml')))))

db = SQLAlchemy(app)
migrate = Migrate(app, db)

class Event(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	table_id = db.Column(db.String(255))
	name = db.Column(db.String(255))
	contact = db.Column(db.String(255))
	participants = db.relationship('Participant', backref='event', lazy=True)

class Participant(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	event_id = db.Column(db.Integer, db.ForeignKey('event.id'))
	email = db.Column(db.String(255))
	confirmed = db.Column(db.Boolean, default=False, nullable=False)

@app.cli.command('new-event')
@click.argument('name')
@click.option('--contact')
@click.option('--table')
def new_event(name, contact, table):
	event = Event(
		table_id=table,
		name=name,
		contact=contact
	)
	db.session.add(event)
	db.session.commit()
	print('Event added')

@app.cli.command('sync-event')
@click.argument('event_id')
def sync_event(event_id):
	event = Event.query.filter_by(id=int(event_id)).first()
	for participant in event.participants:
		googleapi.confirm_participant(event.table_id, participant.email, participant.confirmed)

@app.route('/')
def index():
	return render_template('index.html')

@app.route('/confirm/<event_id>/<mail>/<token>')
def confirm_registration(event_id, mail, token):
	event = Event.query.filter_by(id=int(event_id)).first()
	participant = Participant.query.filter_by(event_id=int(event_id), email=mail).first()
	if event:
		if not participant or not participant.confirmed:
			verification_string = str(event_id) + mail + app.config.get('TOKEN_KEY')
			correct_token = hashlib.md5(verification_string.encode('utf-8')).hexdigest()
			if correct_token != token:
				return render_template('bad_token.html')
			if not participant:
				participant = Participant(
					event_id=int(event_id),
					email=mail,
					confirmed=True
				)
				db.session.add(participant)
			else:
				participant.confirmed = True
			db.session.commit()
			return render_template('confirmed.html')
		else:
			return render_template('already_confirmed.html')
	else:
		return render_template('bad_token.html') # misleading, but ok

@app.route('/unconfirm/<event_id>/<mail>/<token>')
def unconfirm_registration(event_id, mail, token):
	event = Event.query.filter_by(id=int(event_id)).first()
	participant = Participant.query.filter_by(event_id=int(event_id), email=mail, confirmed=True).first()
	if event:
		if participant:
			verification_string = str(event_id) + mail + app.config.get('TOKEN_KEY')
			correct_token = hashlib.md5(verification_string.encode('utf-8')).hexdigest()
			if correct_token != token:
				return render_template('bad_token.html')
			participant.confirmed = False
			db.session.commit()
			return render_template('unconfirmed.html')
		else:
			return render_template('already_unconfirmed.html')
	else:
		return render_template('bad_token.html') # misleading, but ok

if __name__ == "__main__":
	app.run()