#-*- coding: utf-8 -*-

from __future__ import unicode_literals

from datetime import timedelta

import frappe
from frappe import _
from frappe.core.doctype.communication import email
from frappe.utils import now_datetime, add_to_date, get_datetime
from frappe.utils.file_manager import get_file
from frappe.contacts.doctype.contact.contact import get_default_contact


def get_standard_reply( template_name, doc, language=None  ):
    '''Returns the processed HTML of a standard reply with the given doc'''
    
    standard_reply = frappe.get_doc('Standard Reply', template_name)
    return {
        'subject': frappe.render_template( _(standard_reply.subject, language), doc.as_dict() ),
        'message': frappe.render_template( _(standard_reply.response, language), doc.as_dict() )
    }
    

def send_appointment( doc, standard_reply ):
    '''Sends any appointment communication and attach the communication to the Lead'''

    reply = get_standard_reply( standard_reply, doc )
    email.make(
        'Lead',
        doc.name,
        reply['message'],
        reply['subject'],
        sender = doc.modified_by,
        recipients = doc.email_id,
        send_email = True
    )
    frappe.db.commit()


def send_appointment_schedule( lead ):
    '''Sends a new appointment schedule'''

    lead = frappe.get_doc('Lead', lead)
    settings = frappe.get_doc('Cluster System Settings', 'Cluster System Settings')
    if lead.email_id and settings.lead_appointment_enabled and settings.new_appointment_reply:
        send_appointment( lead, settings.new_appointment_reply )


def send_invoice_to_customer( invoice_name ):
    '''Send an invoice to the customer'''

    invoice = frappe.get_doc('Invoice', invoice_name)
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
            sender = invoice.modified_by,
            recipients = invoice.contact_email,
            send_email = True,
            print_html = True,
            print_format = settings.invoice_print_format,
            attachments = attachments
        )
    frappe.db.commit()


def send_appointment_update( lead ):
    '''Sends an updated appointment schedule'''

    lead = frappe.get_doc('Lead', lead)
    settings = frappe.get_doc('Cluster System Settings', 'Cluster System Settings')
    if lead.email_id and settings.lead_appointment_enabled and settings.update_appointment_reply:
        send_appointment( lead, settings.update_appointment_reply )


def appointment_reminder():
    '''Sends an appointment reminder'''

    reminders = frappe.get_list('Appointment Reminder', fields=['*'])
    settings = frappe.get_doc('Cluster System Settings', 'Cluster System Settings')
    if not settings.lead_appointment_enabled:
        return

    now_date = now_datetime()
    for reminder in reminders:
        _next = add_to_date( now_date, hours=reminder.hours_before )
        # Move the minutes to the last possible moment in the hour
        _next = _next + timedelta(minutes=59 - _next.minute, seconds=59 - _next.seconds)
        for lead_name in frappe.get_all( 'Lead', filters={'appointment_date': ['beetween', now_date, _next]} ):
            lead = frappe.get_doc( 'Lead', lead_name )
            # Just send the appointment reminder in the first time that the appointment 
            # is fetched in the time window
            if _next.hour == get_datetime( lead.appointment_date ).hour:
                send_appointment( lead, reminder.reminder_message )
    frappe.db.commit()


def create_appointment_event( lead ):
    '''Create a new appointment event in the calendar'''

    lead = frappe.get_doc('Lead', lead)
    doc = frappe.new_doc('Event')
    doc.update({
        'subject': _('Appointment Schedule for {0} : {1} / {2}').format(
            _('Lead'), lead.name, lead.lead_name
        ),
        'event_type': 'Public',
        'send_reminder': 1,
        'starts_on': lead.appointment_date,
        'color': 'orange',
        'description': "<br>".join([
            _('Appointment Schedule for {0} : {1} / {2}').format(
                _('Lead'), lead.name, lead.lead_name
            ),
            _('Scheduled to: {0}').format( lead.appointment_date ),
            _('On the Location:'),
            lead.appointment_location or "",
        ]),
        'ref_type': 'Lead',
        'ref_name': lead.name
    })
    doc.insert()
    frappe.db.commit()

def update_appointment_event( lead ):
    '''Update an apppointment event in the calendar'''

    lead = frappe.get_doc('Lead', lead)
    doc = frappe.get_doc('Event', {
        'ref_type': 'Lead',
        'ref_name': lead.name,
        'color': 'orange',
        'subject': _('Appointment Schedule for {0} : {1} / {2}').format(
            _('Lead'), lead.name, lead.lead_name
        )
    })
    doc.update({
        'starts_on': lead.appointment_date,
        'description': "<br>".join([
            _('Appointment Schedule for {0} : {1} / {2}').format(
                _('Lead'), lead.name, lead.lead_name
            ),
            _('Scheduled to: {0}').format( lead.appointment_date ),
            _('On the Location:'),
            lead.appointment_location or "",
        ])  
    })
    doc.save()
    frappe.db.commit()


def send_wellcome_email( doctype, name ):
    doc = frappe.get_doc(doctype, name)

    if doctype == "Customer":
        if doc.lead_name:
            email_id = frappe.db.get_value("Lead", doc.lead_name, "email_id")
        else:
            email_id = get_default_contact( doctype, name )
            if email_id:
                email_id = email_id.get("email_id")
    else:
        email_id = doc.get('email_id')

    settings = frappe.get_doc('Cluster System Settings', 'Cluster System Settings')

    attachments = []
    for attachment in settings.wellcome_attachments:
        fname, fcontent = get_file( attachment.attachment )
        attachments.append({
            'fname': fname,
            'fcontent': fcontent
        })

    if email_id:
        reply = get_standard_reply( settings.wellcome_reply, doc )
        email.make(
            doctype,
            name,
            reply['message'],
            reply['subject'],
            sender=doc.modified_by,
            recipients = invoice.contact_email,
            send_email = True,
            attachments = attachments
        )
        


def hourly():
    """Group of Tasks that should run on every hour"""
    
    appointment_reminder()
