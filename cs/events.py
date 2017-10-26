#-*- coding: utf-8 -*-

from __future__ import unicode_literals

import frappe
import frappe.defaults
from frappe.utils import now_datetime, flt

from cs import tasks

def quotation_onload(doc, handler=None):
	if doc.lead:
		customer = frappe.db.get_value("Customer", {"lead_name": doc.lead})
		doc.get("__onload").has_customer = customer
		doc.get("__onload").has_sales_order = frappe.db.count("Sales Order Item", {
			"prevdoc_docname": doc.name
		})


def on_lead_onload(doc, handler=None):
	'''Define some variables to decide if the appointment have changed'''

	if not doc.get('__islocal'):
		onload = doc.get('__onload')
		onload.original_appointment_date, onload.original_appointment_location = frappe.db.get_value(
			'Lead', doc.name, ['appointment_date', 'appointment_location']
		)
	else:
		onload = doc.get('__onload')
		onload.original_appointment_date, onload.original_appointment_location = None, None


def on_lead_validate(doc, handler):
	'''Automatically define the appointment location and asign next contact by'''
	from frappe.contacts.doctype.address.address import (get_default_address,
		get_address_display)
	
	if doc.company and doc.appointment_date and not doc.appointment_location:
		address = get_default_address('Company', doc.company)
		address_display = get_address_display(address)
		doc.appointment_location = address_display

def on_lead_oninsert(doc, handler=None):
	'''Creates an appointment event and sends it by email'''

	if doc.appointment_date or doc.appointment_location:
		tasks.send_appointment_schedule( doc.name )
		tasks.create_appointment_event( doc.name )


def on_lead_onupdate(doc, handler=None):
	'''Updates the appointment event and sends the update by email'''
	from frappe.desk.form import assign_to
	
	if not frappe.db.exists("Event", {"ref_type": doc.doctype, "ref_name": doc.name, "color": "orange"}):
		on_lead_oninsert(doc, handler)
	else:
		onload = doc.get('__onload') or frappe._dict()
		if doc.appointment_date and \
			( onload.get("original_appointment_date") != doc.appointment_date or 
			onload.get("original_appointment_location") != doc.appointment_location ):
				tasks.send_appointment_update( doc.name )
				tasks.update_appointment_event( doc.name )
				onload["original_appointment_date"] = doc.appointment_date
				onload["original_appointment_location"] = doc.appointment_location

	if doc.get('contact_by'):
		if not frappe.db.exists("ToDo", {
			"reference_type": "Lead",
			"reference_name": doc.name,
			"owner": doc.contact_by,
			"status": "Open"
		}):
			assign_to.add({
				'assign_to': doc.contact_by,
				'doctype': 'Lead',
				'name': doc.name,
				'description': frappe._('Automatic assignation'),
				'date': doc.contact_date,
				'notify': 1,
				'assigned_by': 'Administrator'
			})


def on_delivery_note_onsubmit(doc, handler):
	'''Makes a new invoice when delivery note submitted'''

	from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice
	template_for_swap = frappe.defaults.get_global_default('template_for_swap')
	if not template_for_swap:
		frappe.throw(frappe._('You must first configure the `Template for Swap` option in `Cluster System Settings` before you can continue'))

	settings = frappe.get_doc('Cluster System Settings', 'Cluster System Settings')
	if not settings.enable_delivery_note_automation \
		or doc.is_return:
		return

	if doc.get('project') \
		and frappe.db.get_value('Project', doc.project, 'template_type') == template_for_swap:
		doc.taxes = []
		return
	
	sales_invoice = make_sales_invoice( doc.name )
	sales_invoice.flags.ignore_permissions = True
	sales_invoice.insert()
	if doc.get('project') and \
		frappe.db.get_value('Project', doc.project, 'template_type') != template_for_swap:
		sales_invoice.submit()

		if settings.notify_invoice_to_customer and sales_invoice.contact_email:
			tasks.send_invoice_to_customer( sales_invoice.name )

def on_project_onload(doc, handler=None):
	from frappe.contacts.doctype.contact.contact import get_default_contact
	from frappe.contacts.doctype.address.address import get_default_address, get_address_display

	template_for_swap = frappe.defaults.get_global_default('template_for_swap')

	if template_for_swap and doc.get('template_type') == template_for_swap:
		if frappe.db.exists('Delivery Note', {'project': doc.name}):
			item_codes = []
			for dn in frappe.get_all('Delivery Note', {'project': doc.name}):
				dn = frappe.get_doc('Delivery Note', dn)
				for item in dn.items:
					if item.item_code not in item_codes:
						item_codes.append(item.item_code)
			doc.get('__onload').dn_item_codes = item_codes
		
		dns_closed = frappe.db.count('Delivery Note', {'project': doc.name, 'is_return': ["=", 0]})
		all_closed = frappe.db.count('Delivery Note', {'project': doc.name, 'is_return': ["=", 0], 'status': 'Closed'})
		doc.get('__onload').all_dn_closed = (all_closed == dns_closed)

	if doc.get('customer'):
		card_data = doc.get('__onload').customer_card = {
			'customer': frappe.get_doc('Customer', doc.customer).as_dict()
		}

		contact = get_default_contact("Customer", doc.customer)
		if contact:
			card_data['contact'] = frappe.get_doc("Contact", contact).as_dict()

		so = frappe.db.exists('Sales Order', {'project': doc.name})
		address = None
		if so:
			address = frappe.db.get_value('Sales Order', so, "customer_address")
		if address:
			address_doc = frappe.get_doc('Address', address)
		else:
			address_name = get_default_address('Customer', doc.customer)
			if address_name:
				address_doc = frappe.get_doc('Address', address_name)
			else:
				address_doc = None
		
		card_data.update({
			'address': address_doc.as_dict() if address_doc else None,
			'address_display': get_address_display(address_doc.as_dict()) if address_doc else None
		})
		card_data['card_template'] = open(frappe.get_app_path('cs', 'public', 'templates', 'customer_card.html'), 'rb').read()


def on_project_validate(doc, handler=None):
	if len(doc.tasks) == len(doc.get('tasks', {'status': 'Closed'})) and doc.status != "Closed":
		doc.status = "Completed"
	for task in doc.tasks:
		if task.status == "Closed" and \
			frappe.db.get_value('Task', task.task_id, 'status') != 'Closed':
			tasks.notify_task_close_to_customer( task, doc )

def on_stock_entry_on_submit(doc, handler=None):
	warehouse_for_loaner = frappe.defaults.get_global_default("warehouse_for_loaner")
	if not warehouse_for_loaner:
		frappe.throw(frappe._("You must first configure the ` Warehouse for Loaner` option in `Cluster System Settings` before you can continue"))

	if doc.purpose == "Material Transfer":
		for row in doc.items:
			if row.t_warehouse == warehouse_for_loaner \
				and row.serial_no \
				and doc.get('__customer_for_loan'):
				customer = doc.get('__customer_for_loan')
				for serial_no in row.serial_no.splitlines():
					if not serial_no:
						continue
					customer_name = frappe.db.get_value('Customer', customer)
					frappe.get_doc('Serial No', serial_no).update({
						'customer': customer,
						'customer_name': customer_name
					})
