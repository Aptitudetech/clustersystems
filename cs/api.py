#-*- coding: utf-8 -*-

from __future__ import unicode_literals

import frappe

@frappe.whitelist()
def get_company_address(company):
    from frappe.contacts.doctype.address.address import get_company_address
    return get_company_address( company )