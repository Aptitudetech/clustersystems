#-*- coding: utf-8 -*-

import frappe
from frappe import _



def execute():
    for dt, fd in (
        ('Journal Entry', 'cheque_no'), 
        ('Payment Entry', 'reference_no')):
        tr_list = frappe.get_all(dt, filters={
            'docstatus': 1,
            'posting_date': ['<=', '2018-11-30'],
            fd: ['!=', None]
        }, or_filters={'clearance_date': ['in', ['', None]]}, fields=['name', 'posting_date'])

        for row in tr_list:
            frappe.db.set_value(dt, row.name, 'clearance_date', row.posting_date)

    po_list = frappe.get_all("Purchase Order", filters={
	'docstatus': 1,
	'transaction_date': ['<=', '2018-11-30']
    }, fields=['name'])

    for po in po_list:
        frappe.db.set_value('Purchase Order', po.name, 'status', 'Closed')
