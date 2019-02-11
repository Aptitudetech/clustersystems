#-*- coding: utf-8 -*-

import frappe
from frappe import _



def execute():
    pe_list = frappe.get_all('Payment Entry', filters={
        'docstatus': 1,
        'posting_date': ['<=', '2018-11-30']
    }, fields=['name', 'posting_date'])

    for pe in pe_list:
        frappe.db.set_value('Payment Entry', pe.name, 'clearance_date', pe.posting_date)

    po_list = frappe.get_all("Purchase Order", filters={
	'docstatus': 1,
	'transaction_date': ['<=', '2018-11-30']
    }, fields=['name'])

    for po in po_list:
        frappe.db.set_value('Purchase Order', po.name, 'status', 'Closed')
