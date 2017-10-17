#-*- coding: utf-8 -*-

from __future__ import unicode_literals

import frappe

@frappe.whitelist()
def get_company_address(company):
    from frappe.contacts.doctype.address.address import get_company_address
    return get_company_address( company )


@frappe.whitelist()
def get_against_reconcilable(project):
	from copy import copy
	sql = """
		select 
			`tabDelivery Note`.`name` as `delivery_note`,
			`tabDelivery Note`.`posting_date` as `date`,
			`tabDelivery Note`.`customer` as `customer`,
			`tabDelivery Note`.`project` as `project`,
			`tabDelivery Note`.`company` as `company`,
			`tabDelivery Note Item`.`item_code` as `item_code`,
			`tabDelivery Note Item`.`item_name` as `item_name`,
			`tabDelivery Note Item`.`description` as `description`,
			`tabDelivery Note Item`.`qty` as `qty`,
			`tabDelivery Note Item`.`amount` as `amount`,
			`tabDelivery Note Item`.`serial_no` as `serial_no`
		FROM `tabDelivery Note`
		INNER JOIN `tabDelivery Note Item` ON `tabDelivery Note Item`.`parent` = `tabDelivery Note`.`name`
		WHERE
			`tabDelivery Note`.`docstatus` = 1
			AND `tabDelivery Note`.`is_return` = 1
			AND `tabDelivery Note`.`status` != "Closed"
			AND `tabDelivery Note Item`.`amount` < 0
            AND `tabDelivery Note`.`project` = %s
		"""

	ret = []
	for row in frappe.db.sql(sql, (project,), as_dict=False):
		if not row[-1] or not row[-1].splitlines():
			continue
		for sr in row[-1].splitlines():
			if not sr:
				continue
			r = list(copy(row))
			r[-1] = sr
			ret.append({
				'label': ' | '.join(map(unicode, row)),
				'value': row[0]
			})

	return ret
