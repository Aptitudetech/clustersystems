#-*- coding: utf-8 -*-

from __future__ import unicode_literals

import frappe

@frappe.whitelist()
def get_task_events(start, end, filters=None):
	"""Returns events for Gantt / Calendar view rendering.
	:param start: Start date-time.
	:param end: End date-time.
	:param filters: Filters (JSON).
	"""
	from frappe.desk.calendar import get_event_conditions
	conditions = get_event_conditions("Task", filters)

	data = frappe.db.sql("""select name, case when exp_start_time is not null then concat(exp_start_date, " ", exp_start_time) else exp_start_date end as exp_start_date, exp_end_date,
		subject, status, project, color from `tabTask`
		where  exp_start_date is not null and ((ifnull(exp_start_date, '0000-00-00')!= '0000-00-00') \
				and (exp_start_date <= %(end)s) \
			or ((ifnull(exp_end_date, '0000-00-00')!= '0000-00-00') \
				and exp_end_date >= %(start)s))
		{conditions}""".format(conditions=conditions), {
			"start": start,
			"end": end
		}, as_dict=True, update={"allDay": 0})

	return data


@frappe.whitelist()
def get_serial_no_details(serial_no, warehouse):
	from erpnext.stock.utils import get_stock_balance
	if not frappe.db.exists('Serial No', serial_no):
		frappe.throw(__("The given serial no `{0}` was not found!").format(serial_no))
	
	doc = frappe.get_doc("Serial No", serial_no)
	if doc.delivery_document_type and doc.delivery_document_no:
		frappe.throw(__("The given serial no `{0}` is already delivered").format(serial_no))
	elif doc.warehouse != warehouse:
		frappe.throw(__("The given serial no `{0}` aren't in the warehouse `{1}`, it are in `{2}").format(
			serial_no, warehouse, doc.warehouse
		))
	
	qty, val_rate = stock_balance(doc.item_code, warehouse, with_valuation_rate=True)

	ret = {
		'serial_no': serial_no,
		'warehouse': warehouse,
		'item_code': doc.item_code,
		'in_stock': qty > 0,
		'valuation_rate': val_rate,
		'maintenance_status': doc.maintenance_status,
		'warranty_expiry_date': doc.warranty_expiry_date,
		'amc_expiry_date': doc.amc_expiry_date
	}
