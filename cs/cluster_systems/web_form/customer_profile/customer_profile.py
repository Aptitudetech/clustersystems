from __future__ import unicode_literals

import frappe

from erpnext.controllers.website_list_for_contact import get_customers_suppliers

def get_context(context):
	# do your magic here

	customers, _ = get_customers_suppliers('Customer', frappe.local.session.user)

	
	if customers:
		context.doc = frappe.get_doc("Customer", customers[0])
		frappe.form_dict.name = customers[0]
		frappe.form_dict.new = 0

	if context.doc:
		context.doc.run_method('onload')

