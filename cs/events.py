#-*- coding: utf-8 -*-

from __future__ import unicode_literals

import frappe
import frappe.defaults
from frappe.utils import now_datetime, flt

from cs import tasks

def get_project_autoname( doc, new_name ):
	def autoname():
		doc.name = new_name
	return autoname


@frappe.whitelist()
def process_quote(quote, customer_group=None, territory=None, language=None, delivery_date=None):
	from erpnext.crm.doctype.lead.lead import make_customer
	from erpnext.selling.doctype.quotation.quotation import make_sales_order
	from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
	from frappe.desk.form import assign_to
	from frappe.utils import today

	doc = frappe.get_doc('Quotation', quote)

	if doc.lead and not frappe.db.get_value("Customer", {"lead_name": doc.lead}):
		customer = make_customer( doc.lead )
		customer.customer_group = customer_group
		customer.territory = territory
		customer.language = language
		customer.flags.ignore_mandatory = True
		customer.flags.ignore_permissions = True
		customer.insert()

	so = make_sales_order( quote )
	so.delivery_date = delivery_date or today()
	so.flags.ignore_mandatory = True
	so.flags.ignore_permissions = True
	so.save()

	if frappe.defaults.get_global_default( 'auto_create_project' ):
		filters = {'project_type': 'Template'}
		if frappe.db.exists( 'Project', {'project_type': 'Template', 
			'template_type': doc.template_type } ):
			filters['template_type'] = doc.template_type
		base_project = frappe.get_doc('Project', filters)
		project_name = " - ".join([
			doc.customer_name,
			"# " + str(frappe.db.count('Project') + 1)
		])
		new_project = frappe.copy_doc( base_project, True )
		if doc.lead:
			new_project.customer = frappe.db.get_value("Customer", {
				"lead_name": doc.lead
			})
		else:
			new_project.customer = doc.customer
		new_project.project_type = "External"
		new_project.autoname = get_project_autoname( new_project, project_name )
		new_project.flags.ignore_mandatory = True
		new_project.flags.ignore_permissions = True
		new_project.insert()

		for task_name in frappe.get_all("Task", filters={"project": base_project.name}, order_by='idx'):
			task = frappe.get_doc("Task", task_name)
			new_task = frappe.copy_doc( task, True )
			new_task.project = new_project.name
			new_task.flags.ignore_mandatory = True
			new_task.flags.ignore_permissions = True
			new_task.insert()

			if new_task.get('assigned_to'):
				assign_to.add({
					'assign_to': new_task.assigned_to,
					'doctype': 'Task',
					'name': new_task.name,
					'description': frappe._('Automatic assignation'),
					'date': today(),
					'notify': 1,
					'assigned_by': 'Administrator'
				})

		frappe.msgprint(
			frappe._('New Project {0} created').format(project_name)
		)

		so.project = new_project.name
		

	if doc.get('template_type') == 'Swap and Warranty':
		so.taxes = []

	so.submit()

	frappe.msgprint(
		frappe._('New Sales Order {0} created!').format(so.name)
	)

	dn = make_delivery_note( so.name )
	dn.flags.ignore_mandatory = True
	dn.flags.ignore_permissions = True
	dn.insert()
	for row in doc.items:
		if row.get("serial_no"):
			frappe.db.set_value(row.doctype, row.name, 'serial_no', None, update_modified=False)

	frappe.msgprint(
		frappe._('New Delivery Note {0} create!').format(so.name)
	)

	assign_dn_to = frappe.defaults.get_global_default( 'auto_assign_dn_to' )
	if assign_dn_to:
		assign_to.add({
			'assign_to': assign_dn_to,
			'doctype': 'Delivery Note',
			'name': dn.name,
			'description': frappe._('Automatic assignation'),
			'date': delivery_date,
			'notify': 1,
			'assigned_by': 'Administrator'
		})

		frappe.msgprint(
			frappe._('Delivery Note {0} assigned to {1}').format(
				dn.name,
				assign_dn_to
			)
		)

	settings = frappe.get_doc("Cluster System Settings", "Cluster System Settings")
	if settings.send_wellcome_email and settings.wellcome_reply:
		tasks.send_wellcome_email( doc.quotation_to, doc.lead or doc.customer )
		#enqueue( 'cs.tasks.send_wellcome_email', doc.quotation_to, doc.lead or doc.customer )


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
		#enqueue( 'cs.tasks.send_appointment_schedule', doc.name )
		#enqueue( 'cs.tasks.create_appointment_event', doc.name )


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
				#enqueue( 'cs.tasks.send_appointment_update', doc.name )
				#enqueue( 'cs.tasks.update_appointment_event', doc.name )
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
	
	settings = frappe.get_doc('Cluster System Settings', 'Cluster System Settings')
	if not settings.enable_delivery_note_automation \
		or doc.is_return:
		return

	if doc.get('project') \
		and frappe.db.get_value('Project', doc.project, 'template_type') == 'Swap and Warranty':
		doc.taxes = []
		return
	
	sales_invoice = make_sales_invoice( doc.name )
	sales_invoice.flags.ignore_permissions = True
	sales_invoice.insert()
	sales_invoice.submit()

	if settings.notify_invoice_to_customer and sales_invoice.contact_email:
		tasks.send_invoice_to_customer( sales_invoice.name )
		#enqueue( 'cs.tasks.send_invoice_to_customer', sales_invoice.name )


def on_task_validate( doc, handler ):
	if doc.status == "Closed" and frappe.db.get_value("Task", doc.name, "status") != "Closed":
		tasks.notify_task_close_to_customer( doc.name )


@frappe.whitelist()
def get_company_address(company):
	from frappe.contacts.doctype.address.address import get_company_address

	return (get_company_address(company) or {}).get("company_address_display")


@frappe.whitelist()
def make_return(customer, item_code, serial_no, warehouse, credit_amount, 
	company, project, reconcile_against=None):
	'''Automates the return generation against a project'''

	from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_return

	msgs = []
	if not frappe.db.exists('Serial No', serial_no) or not frappe.db.get_value('Serial No', serial_no, 'creation_document_type'):
		now = now_datetime().strftime('%Y-%m-%d %H:%M:%S').split(' ')
		uom = frappe.db.get_value('Item', item_code, 'stock_uom')
		ste = frappe.new_doc('Stock Entry').update({
			'purpose': 'Material Receipt',
			'naming_series': 'STE-',
			'company': company,
			'posting_date': now[0],
			'posting_time': now[1],
			't_warehouse': warehouse,
			'project': project,
			'items': [
				{
					'item_code': item_code,
					'qty': 1,
					'basic_rate': 0.0,
					'basic_amount': 0.0,
					'uom': uom,
					'stock_uom': uom,
					'conversion_factor': 1.0,
					'serial_no': serial_no,
					'allow_zero_valuation_rate': 1,
					't_warehouse': warehouse
				}
			]
		})
		ste.run_method('get_missing_values')
		ste.run_method('save')
		ste.run_method('submit')

		msgs.append(frappe._('New Stock Entry `{0}` created!').format(ste.name))

		dn = frappe.new_doc('Delivery Note').update({
			'series': 'DN-',
			'customer': customer,
			'company': company,
			'posting_date': now[0],
			'posting_time': now[1],
			'project': project,
			'items': [{
				'item_code': item_code,
				'warehouse': warehouse,
				'quantity': 1.0,
				'stock_uom': uom,
				'uom': uom,
				'conversion_factor': 1.0,
				'stock_qty': 1.0,
				'price_list_rate': 0.0,
				'rate': 0.0,
				'amount': 0.0,
				'allow_zero_valuation_rate': 1,
				'serial_no': serial_no
			}]
		})
		dn.run_method('get_missing_values')
		dn.run_method('save')
		dn.run_method('submit')

		msgs.append(frappe._('New Delivery Note `{0}` created!').format(dn.name))
	else:
		returned = frappe.db.exists('Delivery Note Item', {
			'docstatus': 1,
			'qty': ['<', 0],
			'serial_no': ['like', "%" + serial_no + "%"]
		})

		if returned:
			frappe.throw(_('The serial no `{0}` was already swapped!').format(serial_no))
		else:
			delivered = frappe.db.exists('Delivery Note Item', {
				'docstatus': 1,
				'qty': ['>', 0],
				'serial_no': ['like', "%" + serial_no + "%"]
			})
			dn = frappe.get_doc('Delivery Note', delivered)	
	
	rt = make_sales_return(dn.name)
	for i, item in enumerate(rt.items):
		if item.item_code != item_code:
			del rt.items[i]
		item.update({
			'item_code': item_code,
			'qty': -1,
			'rate': flt(credit_amount),
			'amount': -flt(credit_amount),
			'uom': uom,
			'stock_uom': uom,
			'conversion_factor': 1.0,
			'serial_no': serial_no
		})

	rt.run_method('get_missing_values')
	rt.run_method('save')
	rt.run_method('submit')

	if reconcile_against is not None:
		frappe.get_doc('Delivery Note', reconcile_against).update_status('Closed')
		rt.update_status('Closed')

	msgs.append(frappe._('New Return `{0}` created!').format(rt.name))

	if dn.grand_total == 0:
		dn.update_status('Closed')

	if msgs:
		frappe.msgprint('<br>'.join(msgs))


def on_project_onload(doc, handler=None):
	if doc.get('template_type') == 'Swap and Warranty' \
		and frappe.db.exists('Delivery Note', {'project': doc.name}):
		item_codes = []
		for dn in frappe.get_all('Delivery Note', {'project': doc.name}):
			dn = frappe.get_doc('Delivery Note', dn)
			for item in dn.items:
				if item.item_code not in item_codes:
					item_codes.append(item.item_code)
		doc.get('__onload').dn_item_codes = item_codes