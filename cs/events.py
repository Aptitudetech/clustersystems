#-*- coding: utf-8 -*-

from __future__ import unicode_literals

import frappe
import frappe.defaults

def get_project_autoname( new_name ):
    def autoname(self):
        self.name = new_name
    return autoname

def process_quote(doc, method=None):
    from erpnext.selling.doctype.quotation.quotation import make_sales_order
    from erpnext.stock.doctype.sales_order.sales_order import make_delivery_note
    from frappe.desk.form import assign_to

    so = make_sales_order( doc.name )
    so.flags.ignore_mandatory = True
    so.flags.ignore_permissions = True
    so.save()

    if frappe.defaults.get_global_default( 'auto_create_project' ):
        base_project = frappe.get_doc('Project', {'project_type': 'template'})
        project_name = " / ".join(
            doc.customer_name,
            str(frappe.db.count('Project', {'customer': self.customer}) + 1)
        )
        new_project.autoname = get_project_autoname( project_name )
        new_project.flags.ignore_mandatory = True
        new_project.flags.ignore_permissions = True
        new_project.insert()
        so.project = new_project.name

    so.submit()
    dn = make_delivery_note( so.name )
    dn.flags.ignore_mandatory = True
    dn.flags.ignore_permissions = True
    dn.insert()

    assign_dn_to = frappe.defaults.get_global_default( 'auto_assign_dn_to' )
    if assign_dn_to:
        assign_to({
            'assign_to': assign_dn_to,
            'doctype': 'Delivery Note',
            'name': dn.name,
            'description': frappe._('Automatic assignation')
        })