#-*- coding: utf-8 -*-

from __future__ import unicode_literals

import frappe
import frappe.defaults

def get_project_autoname( doc, new_name ):
    def autoname():
        doc.name = new_name
    return autoname

@frappe.whitelist()
def process_quote(quote, customer_group=None, territory=None, delivery_date=None):
    from erpnext.crm.doctype.lead.lead import make_customer
    from erpnext.selling.doctype.quotation.quotation import make_sales_order
    from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
    from frappe.desk.form import assign_to

    doc = frappe.get_doc('Quotation', quote)

    if doc.lead and not frappe.db.get_value("Customer", {"lead_name": doc.lead}):
        customer = make_customer( doc.lead )
        customer.customer_group = customer_group
        customer.territory = territory
        customer.flags.ignore_mandatory = True
        customer.flags.ignore_permissions = True
        customer.insert()

    so = make_sales_order( quote )
    so.delivery_date = delivery_date
    so.flags.ignore_mandatory = True
    so.flags.ignore_permissions = True
    so.save()

    if frappe.defaults.get_global_default( 'auto_create_project' ):
        filters = {'project_type': 'Template'}
        if frappe.db.exists( 'Project', {'project_type': 'Template', 'template_type': doc.template_type } ):
            filters['template_type'] = doc.template_type
        base_project = frappe.get_doc('Project', filters)
        project_name = " / ".join([
            doc.customer_name,
            str(frappe.db.count('Project', {'customer': doc.customer}) + 1)
        ])
        new_project = frappe.copy_doc( base_project, True )
        new_project.customer = doc.customer
        new_project.autoname = get_project_autoname( new_project, project_name )
        new_project.flags.ignore_mandatory = True
        new_project.flags.ignore_permissions = True
        new_project.insert()

        for task_name in frappe.get_all("Task", filters={"project": project_name}):
            task = frappe.get_doc("Task", task_name)
            new_task = frappe.copy_doc( task, True )
            new_task.project = new_project.name
            new_task.flags.ignore_mandatory = True
            new_task.flags.ignore_permissions = True
            new_task.insert()

        frappe.msgprint(
            frappe._('New Project {0} created').format(project_name)
        )

        so.project = new_project.name
        

    so.submit()

    frappe.msgprint(
        frappe._('New Sales Order {0} created!').format(so.name)
    )

    dn = make_delivery_note( so.name )
    dn.flags.ignore_mandatory = True
    dn.flags.ignore_permissions = True
    dn.insert()

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
            'date': delivery_date
        })

        frappe.msgprint(
            frappe._('Delivery Note {0} assigned to {1}').format(
                dn.name,
                assign_dn_to
            )
        )

def quotation_onload(doc, handler=None):
    if doc.lead:
        customer = frappe.db.get_value("Customer", {"lead_name": doc.lead})
        doc.get("__onload").has_customer = customer