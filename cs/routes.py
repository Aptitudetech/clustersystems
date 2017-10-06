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

	data = frappe.db.sql("""select name, exp_start_date, exp_end_date,
		subject, status, project, color from `tabTask`
		where ((ifnull(exp_start_date, '0000-00-00')!= '0000-00-00') \
				and (exp_start_date <= %(end)s) \
			or ((ifnull(exp_end_date, '0000-00-00')!= '0000-00-00') \
				and exp_end_date >= %(start)s))
		{conditions}""".format(conditions=conditions), {
			"start": start,
			"end": end
		}, as_dict=True, update={"allDay": 0})

	return data