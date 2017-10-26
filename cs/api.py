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

	msgs = []

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
		if not frappe.db.exists( 'Project', 
			{'project_type': 'Template',  'template_type': doc.template_type } ):
			frappe.throw(frappe._('A Project Template of type "{0}" does not exist, please create one').format(
				doc.template_type
			))
		
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

		msgs.append(
			frappe._('New Project {0} created').format(project_name)
		)

		so.project = new_project.name
		
	template_for_swap = frappe.defaults.get_global_default('template_for_swap')
	if not template_for_swap:
		frappe.throw(frappe._('You must first configure the `Template for Swap` option in `Cluster System Settings` before you can continue'))

	if doc.get('template_type') == template_for_swap:
		so.taxes = []

	so.submit()

	msgs.append(
		frappe._('New Sales Order {0} created!').format(so.name)
	)

	dn = make_delivery_note( so.name )
	dn.flags.ignore_mandatory = True
	dn.flags.ignore_permissions = True
	dn.insert()
	for row in dn.items:
		item = doc.get('items', {'item_code': row.item_code})
		if item and item[0].notes:
			frappe.db.set_value(row.doctype, row.name, 'notes', item[0].notes, update_modified=False)
		if row.get("serial_no"):
			frappe.db.set_value(row.doctype, row.name, 'serial_no', None, update_modified=False)

	msgs.append(
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

		msgs.append(
			frappe._('Delivery Note {0} assigned to {1}').format(
				dn.name,
				assign_dn_to
			)
		)

	return {
		'msgs': msgs,
		'project_name': new_project.name if frappe.defaults.get_global_default( 'auto_create_project' ) else None
	}

	settings = frappe.get_doc("Cluster System Settings", "Cluster System Settings")
	if settings.send_wellcome_email and settings.wellcome_reply:
		tasks.send_wellcome_email( doc.quotation_to, doc.lead or doc.customer )



@frappe.whitelist()
def get_company_address(company):
	from frappe.contacts.doctype.address.address import get_company_address

	return (get_company_address(company) or {}).get("company_address_display")


@frappe.whitelist()
def get_against_reconcilable(project):
	from copy import copy
	sql = """
		select 
			`tabDelivery Note`.`name` as `name`,
			`tabDelivery Note Item`.`item_code` as `item_code`,
			`tabDelivery Note Item`.`serial_no` as `serial_no`
		FROM `tabDelivery Note`
		INNER JOIN `tabDelivery Note Item` ON `tabDelivery Note Item`.`parent` = `tabDelivery Note`.`name`
		WHERE
			`tabDelivery Note`.`docstatus` = 1
			AND `tabDelivery Note`.`is_return` = 0
			AND `tabDelivery Note`.`status` != "Closed"
			AND `tabDelivery Note Item`.`amount` > 0
            AND `tabDelivery Note`.`project` = %s
		"""

	ret = []
	for row in frappe.db.sql(sql, (project,), as_dict=False):
		if not row[-1] or not row[-1].splitlines():
			continue
		for sr in row[-1].splitlines():
			if not sr:
				continue
			r = list(copy(row))
			r[-1] = sr
			ret.append({
				'label': ' | '.join(map(unicode, row[1:])),
				'value': row[0]
			})

	return ret


@frappe.whitelist()
def make_return(customer, item_code, serial_no, warehouse, 
	company, project, reconcile_against=None):
	'''Automates the return generation against a project'''

	from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_return
	from erpnext.stock.utils import get_stock_balance

	msgs = []
	now = now_datetime().strftime('%Y-%m-%d %H:%M:%S').split(' ')
	uom = frappe.db.get_value('Item', item_code, 'stock_uom')

	item_valuation_rate = get_stock_balance(item_code=item_code, warehouse=warehouse, with_valuation_rate=1)[1]
	credit_amount = item_valuation_rate * flt(frappe.defaults.get_global_default('percent_for_return')) / 100.0

	if not frappe.db.exists('Serial No', serial_no) or not frappe.db.get_value('Serial No', serial_no, 'purchase_document_type'):
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

	delivered = frappe.db.get_value('Delivery Note Item', filters={
		'docstatus': 1,
		'qty': ['>', 0],
		'serial_no': ['like', "%" + serial_no + "%"]
	}, fieldname="parent")
	
	if delivered:
		dn = frappe.get_doc('Delivery Note', delivered)	
	else:

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
	
	returned = frappe.db.exists('Delivery Note Item', {
		'docstatus': 1,
		'qty': ['<', 0],
		'serial_no': ['like', "%" + serial_no + "%"]
	})
	if returned:
		frappe.throw(_('The serial no `{0}` was already swapped!').format(serial_no))
	
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

@frappe.whitelist()
def cancel_process_quote_return(project):
	
	for si in frappe.get_all('Sales Invoice', filters={'project': project}, fields=['name']):
		si = frappe.get_doc('Sales Invoice', si)
		if si.docstatus == 0:
			frappe.delete_doc('Sales Invoice', si.name)

	for dn in frappe.get_all('Delivery Note', filters={'project': project}, fields=['name']):
		dn = frappe.get_doc('Delivery Note', dn)
		if dn.docstatus == 1:
			dn.cancel()
		elif dn.docstatus == 0:
			frappe.delete_doc('Delivery Note', dn.name)

	for so in frappe.get_all('Sales Order', filters={'project': project}, fields=['name']):
		so = frappe.get_doc('Sales Order', so.name)
		if so.docstatus == 1:
			so.cancel()
		elif so.docstatus == 0:
			frappe.delete_doc('Sales Order', so.name)

	template_type, customer = frappe.db.get_value('Project', fieldname=['template_type', 'customer'],
		filters={'name': project})
	for qt in frappe.get_all('Quotation', filters={'template_type': template_type, 'customer': customer}, fields=['name']):
		qt = frappe.get_doc('Quotation', qt.name)
		if qt.docstatus == 1:
			qt.cancel()
		elif qt.docstatus == 0:
			frappe.delete_doc('Quotation', qt.name)

	for ts in frappe.get_all('Task', filters={'project': project}, fields=['name']):
		ts = frappe.get_doc('Task', ts.name)
		if ts.status not in ('Closed', 'Cancelled'):
			frappe.db.set_value('Task', ts.name, 'status', 'Cancelled')
		
	frappe.db.set_value('Project', project, 'status', 'Cancelled')
