#-*- coding: utf-8 -*-

from __future__ import unicode_literals

from datetime import timedelta

import frappe
import icalendar
import datetime
from frappe import _
from frappe.core.doctype.communication import email
from frappe.utils import now_datetime, add_to_date, get_datetime
from frappe.utils.file_manager import get_file
from frappe.contacts.doctype.contact.contact import get_default_contact
from html2text import html2text

def get_standard_reply( template_name, doc, language=None, **kwargs  ):
	'''Returns the processed HTML of a standard reply with the given doc'''
	
	kw = doc.as_dict()
	kw.update(kwargs)

	standard_reply = frappe.get_doc('Standard Reply', template_name)
	return {
		'subject': frappe.render_template( _(standard_reply.subject, language), kw ),
		'message': frappe.render_template( _(standard_reply.response, language), kw )
	}
	

def send_appointment( doc, standard_reply , for_update=False):
	'''Sends any appointment communication and attach the communication to the Lead'''

	if doc.doctype != "Lead":
		if not doc.contact_person:
			return
		email_id = frappe.db.get_value('Contact', doc.contact_person, 'email_id')
	else:
		email_id = doc.email_id

	reply = get_standard_reply( standard_reply, doc )

	settings = frappe.get_doc('Cluster System Settings', 'Cluster System Settings')

	cal = icalendar.Calendar()
	cal.add('prodid', '-//Aptitudetech ERPNext Automation//aptitudetech.net//')
	cal.add('version', '1.0')

	event = icalendar.Event()
	event.add('summary', reply['subject'])
	event.add('dtstart', get_datetime(doc.appointment_date))
	event.add('dtend', get_datetime(add_to_date(doc.appointment_date, hours=1)))
	event.add('dtstamp', get_datetime(now_datetime()))
	event.add('priority', 5)
	
	if for_update:
		event.add('method', 'REQUEST')
	event['organizer'] = icalendar.vCalAddress('MAILTO:meeting@clusterpos.com')
	event['location']  = icalendar.vText(html2text(doc.appointment_location).replace("=", ""))
	event['uid'] = '{0}/lead@clusterpos.com'.format(doc.get_signature())
	event['sequence'] = get_datetime(now_datetime()).strftime('%Y%m%d%H%M%S')
	event['description'] = html2text(reply['message']).replace("=", "")

	cal.add_component(event)

	email.make(
		doc.doctype,
		doc.name,
		reply['message'],
		reply['subject'],
		sender=settings.email_sender,
		recipients = email_id,
		send_email = True,
		attachments=[{
			'fname': 'meeting.ics',
			'fcontent': cal.to_ical()
		}]
	)


def send_appointment_schedule( doctype, docname ):
	'''Sends a new appointment schedule'''

	doc = frappe.get_doc(doctype, docname)
	settings = frappe.get_doc('Cluster System Settings', 'Cluster System Settings')
	if settings.lead_appointment_enabled and settings.new_appointment_reply:
		if doctype == "Lead" and doc.email_id:
			send_appointment( doc, settings.new_appointment_reply )
		else:
			send_appointment( doc, settings.new_appointment_reply )


def send_invoice_to_customer( invoice_name ):
	'''Send an invoice to the customer'''

	invoice = frappe.get_doc('Sales Invoice', invoice_name)
	settings = frappe.get_doc('Cluster System Settings', 'Cluster System Settings')
	customer_language = frappe.db.get_value('Customer', invoice.customer, 'language')

	if settings.notify_invoice_to_customer and settings.new_invoice_message:
		reply = get_standard_reply( settings.new_invoice_message, invoice, customer_language )
		
		attachments = []
		for attachment in settings.attachments:
			fname, fcontent = get_file( attachment.attachment )
			attachments.append({
				'fname': fname,
				'fcontent': fcontent
			})

		email.make(
			'Sales Invoice',
			invoice_name,
			reply['message'],
			reply['subject'],
			sender=settings.email_sender,
			recipients = invoice.contact_email,
			send_email = True,
			print_html = True,
			print_format = settings.invoice_print_format,
			attachments = attachments
		)


def send_appointment_update( doctype, docname, contact_name ):
	'''Sends an updated appointment schedule'''

	source_doc = frappe.get_doc(doctype, docname)
	settings = frappe.get_doc('Cluster System Settings', 'Cluster System Settings')
	if settings.lead_appointment_enabled and settings.update_appointment_reply:
		if doctype == 'Lead' and source_doc.email_id:
			send_appointment(source_doc, settings.update_appointment_reply, for_update=True )
		else:
			send_appointment(source_doc, settings.update_appointment_reply, for_update=True)


def appointment_reminder():
	'''Sends an appointment reminder'''

	reminders = frappe.get_list('Appointment Reminder', fields=['*'])
	settings = frappe.get_doc('Cluster System Settings', 'Cluster System Settings')
	if not settings.lead_appointment_enabled:
		return

	now_date = now_datetime()
	now_date = now_date - timedelta(minutes=now_date.minute, seconds=now_date.second, microseconds=now_date.microsecond)
	for reminder in reminders:
		_next = add_to_date( now_date, hours=reminder.hours_before )
		# Move the minutes to the last possible moment in the hour
		_next = _next + timedelta(minutes=59 - _next.minute, seconds=59 - _next.second)
		for lead in frappe.get_all("Lead", fields="*", filters={"appointment_date": ["between", now_date, _next]}):
			# Just send the appointment reminder in the first time that the appointment 
			# is fetched in the time window
			if _next.hour == get_datetime( lead.appointment_date ).hour \
				and get_datetime(lead.appointment_date).strftime('%Y-%m-%d') == _next.strftime('%Y-%m-%d'):
				send_appointment( lead, reminder.reminder_message )


def create_appointment_event( doctype, docname, contact_name ):
	'''Create a new appointment event in the calendar'''

	source_doc = frappe.get_doc(doctype, docname)
	doc = frappe.new_doc('Event')
	doc.update({
		'subject': _('Appointment Schedule for {0} : {1} / {2}').format(
			_(doctype), docname, contact_name
		),
		'event_type': 'Public',
		'send_reminder': 1,
		'starts_on': source_doc.appointment_date,
		'color': 'orange',
		'description': "<br>".join([
			_('Appointment Schedule for {0} : {1} / {2}').format(
				_(doctype), docname, contact_name
			),
			_('Scheduled to: {0}').format( source_doc.appointment_date ),
			_('On the Location:'),
			source_doc.appointment_location or "",
		]),
		'ref_type': source_doc.doctype,
		'ref_name': source_doc.name
	})
	doc.insert()

def update_appointment_event( doctype, docname, contact_name ):
	'''Update an apppointment event in the calendar'''

	source_doc = frappe.get_doc(doctype, docname)
	doc = frappe.get_doc('Event', {
		'ref_type': doctype,
		'ref_name': docname,
		'color': 'orange',
		'subject': _('Appointment Schedule for {0} : {1} / {2}').format(
			_(doctype), docname, contact_name
		)
	})
	doc.update({
		'starts_on': source_doc.appointment_date,
		'description': "<br>".join([
			_('Appointment Schedule for {0} : {1} / {2}').format(
				doctype, docname, contact_name
			),
			_('Scheduled to: {0}').format( source_doc.appointment_date ),
			_('On the Location:'),
			source_doc.appointment_location or "",
		])  
	})
	doc.save()


def create_portal_user(doctype, name):
	doc = frappe.get_doc(doctype, name)
	
	email_id = None
	if doctype == "Customer":
		email_id = frappe.db.get_value("Lead", doc.lead_name, "email_id") if doc.lead_name else doc.get("email_id")
	else:
		email_id = doc.get("email_id")

	contact = None
	if contact is None:
		options = [[doctype, name]]
		if doctype == "Customer" and doc.lead_name:
			options.append(["Lead", doc.lead_name])
		
		for dt, dn in options:
			contact = get_default_contact( dt, dn )
			if contact:
				contact = frappe.get_doc("Contact", contact)
				break
	

	if email_id and contact and not frappe.db.exists("User", email_id):
		user = frappe.new_doc("User").update({
			"first_name": contact.first_name,
			"last_name": contact.last_name,
			"email": email_id,
			"user_type": "Website User",
			"send_welcome_email": 0
		})
		user.save(ignore_permissions=True)
		return user.reset_password()
		


def send_wellcome_email( doctype, name, welcome_reply, link ):
	doc = frappe.get_doc(doctype, name)

	email_id = None
	if doctype == "Customer":
		if doc.lead_name:
			email_id = frappe.db.get_value("Lead", doc.lead_name, "email_id")
	else:
		email_id = doc.get('email_id')

	if email_id is None:
		options = [[doctype, name]]
		if doctype == "Customer" and doc.lead_name:
			options.append(["Lead", doc.lead_name])
		
		for dt, dn in options:
			contact = get_default_contact( dt, dn )
			if contact:
				email_id = frappe.db.get_value("Contact", contact, "email_id")
				break

	settings = frappe.get_doc('Cluster System Settings', 'Cluster System Settings')

	attachments = []
	for attachment in settings.wellcome_attachments:
		fname, fcontent = get_file( attachment.attachment )
		attachments.append({
			'fname': fname,
			'fcontent': fcontent
		})

	if email_id:
		reply = get_standard_reply( welcome_reply or settings.wellcome_reply, doc, link=link )
		email.make(
			doctype,
			name,
			reply['message'],
			reply['subject'],
			sender=settings.email_sender,
			recipients = email_id,
			send_email = True,
			attachments = attachments
		)
	else:
		msgs = [
			frappe._(
				"We are unable to find an valid Email for the party {0} - {1}"
			).format(doctype, name)
		]
		if doctype == "Customer":
			msgs.append(frappe._(
				"Please, ensure that the customer has a primary contact, with valid email"
				"<br> or that it relates to a lead"
			))
		frappe.throw("<b>".join(msgs))
		

def notify_task_close_to_customer( doc, project ):
	settings = frappe.get_doc('Cluster System Settings', 'Cluster System Settings')

	if not settings.notify_task_close:
		return

	reply = get_standard_reply( settings.task_close_reply, doc, project=project )

	if not project.customer:
		return

	email_id = None
	customer = frappe.get_doc("Customer", project.customer)
	if frappe.db.exists("Dynamic Link", {"parenttype": "Contact", "link_doctype": "Customer", "link_name": project.customer}):
		contact = get_default_contact( 'Customer', project.customer )
		if contact:
			email_id = frappe.db.get_value("Contact", contact, "email_id")
	if customer.lead_name and email_id is None:
		email_id = frappe.db.get_value("Lead", customer.lead_name, "email_id")	

	if email_id:
		email.make(
			'Project',
			project.name,
			reply['message'],
			reply['subject'],
			sender=settings.email_sender,
			recipients = email_id,
			send_email = True,
		)

def hourly():
	"""Group of Tasks that should run on every hour"""
	
	appointment_reminder()
