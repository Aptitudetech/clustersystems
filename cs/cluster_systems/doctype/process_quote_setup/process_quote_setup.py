# -*- coding: utf-8 -*-
# Copyright (c) 2017, aptitudetech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import frappe.defaults
from frappe.model.document import Document

class ProcessQuoteSetup(Document):
	def validate( self ):
    	for field in ['auto_create_project', 'auto_assign_dn_to']:
    		frappe.defaults.add_global_default(field, self.get(field))
