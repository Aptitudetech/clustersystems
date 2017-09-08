#-*- coding: utf-8 -*-

from __future__ import unicode_literals

import frappe

def execute():
    if frappe.db.exists("DocType", "Process Quote Setup"):
        frappe.delete_doc("DocType", "Process Quote Setup")