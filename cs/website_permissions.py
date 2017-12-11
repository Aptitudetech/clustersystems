#-*- coding: utf-8 -*-

import frappe
from erpnext.controllers.website_list_for_contact import get_customers_suppliers

def has_website_permission(doc, ptype,  user, verbose=False):
	if doc:
		customer, suppliers = get_customers_suppliers(doc.doctype, frappe.local.session.user)
		if doc.doctype == "Customer":
			return doc.name in customer
		return doc.name in suppliers
	return False
