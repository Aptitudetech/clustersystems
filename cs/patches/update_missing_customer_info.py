#-*- coding: utf-8 -*-

from __future__ import unicode_literals

import frappe

def execute():
	frappe.db.sql('UPDATE `tabCustomer` SET `customer_group` = "Commercial" where ifnull(`customer_group`, "")="";')
	frappe.db.sql('UPDATE `tabCustomer` SET `territory` = "Canada" where ifnull(`territory`, "")="";')