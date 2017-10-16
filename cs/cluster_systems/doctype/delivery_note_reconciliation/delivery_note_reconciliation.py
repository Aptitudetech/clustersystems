# -*- coding: utf-8 -*-
# Copyright (c) 2017, aptitudetech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import itertools
from frappe.model.document import Document
from frappe.utils import nowdate

class DeliveryNoteReconciliation(Document):
	def on_load(self):
		if self.details:
			self.items = []

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
			AND `tabDelivery Note`.`is_return` = 0
			AND `tabDelivery Note`.`status` != "Closed"
			AND `tabDelivery Note Item`.`amount` > 0 and round(`tabDeliveryNote`.`billed_amt` *
			    ifnull(`tabDelivery Note Item`.`conversion_rate`, 1), 2) < `tabDelivery Note Item`.`base_amount`
		"""

		for row in frappe.db.sql(sql, as_dict=True):
			if not row['serial_no']:
				row['action'] == 'Bill'
				self.append('details', row)
			else:
				sri = len([s for s row['serial_no'].splitlines() if s])
				for sr in row['serial_no'].splitlines():
					if not sr:
						continue
					srow = row.copy()
					srow['serial_no'] = sr
					srow['qty'] = srow['qty'] / sri
					srow['amount'] = srow['amount'] / sri
					self.append('details', srow)

	def reconcile_or_bill(self):
		for ac, items in groupby(self.items, lambda r: r['action']):
			if not ac:
				continue
			elif ac == "Bill":
				self.bill_items(list(items))
			elif ac == "Reconcile":
				self.reconcile_items(list(items))

	def reconcile_items(self, items):
		from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice
		msgs = []
		for dn, items in groupby(item, lambda r: r['item_code']):
			items = list(items)
			item_codes = set([r['item_code'] for r in items])
			si = make_sales_invoice(dn)

			for i, r in enumerate(si.get('items')):
				if r.get('item_code') not in item_codes:
					del si.items[i]
				r.update({
					'qty': 0.0,
					'rate': 0.0,
					'serial_no': '' 
				})
				for sr in filter(items, lambda _r: _r.get('item_code') == r.get('item_code')):
					r.qty += sr.qty
					r.rate += sr.amount
					r.serial_no += sr.serial_no
			
			if si.get('items'):
				si.run_method('get_missing_values')
				si.run_method('calculate_taxes_and_totals')
				si.run_method('save')
				si.run_method('submit')
				msgs.append(frappe._('The Delivery Note `{0}` was billed into the Sales Invoice `{1}`').format(
					dn, si.name
				))
		if msgs:
			frappe.msgprint('<br>'.join(msgs))

	def bill_items(self, items):
		from erpnext.accounts.party import get_party_account

		items = list(items)
		item_codes = set([r['item_code'] for r in items])
		dns = set([r.delivery_note for r in items])
		all_dns = dns & set([r.reconcile_against for r in items])
		credit_amount = sum([r.amount for r in items])

		party_acc = get_party_account('Customer', items[0].customer, items[0].company)
		stock_devaluation_acc = frappe.db.get_value('Cluster System Settings', 'Cluster System Settings', 'account_for_stock_devaluation')

		accounts = [
			{
				'account': party_acc,
				'party_type': 'Customer',
				'party': customer,
				'reference_type': 'Delivery Note',
				'reference_name': item.reconcile_against,
				'credit_in_account_currency': item.amount,
				'credit': item.amount
			} for item in items
		] + [
			{
				'account': party_acc,
				'party_type': 'Customer',
				'party': items[0].customer,
				'reference_type': 'Delivery Note',
				'reference_name': delivery_note,
				'debit_in_account_currency': abs(frappe.db.get_value('Delivery Note', delivery_note, 'outstanding_amount')),
				'debit': abs(frappe.db.get_value('Delivery Note', delivery_note, 'outstanding_amount'))
			}
			for delivery_note in dns
		]

		je = frappe.new_doc('Journal Entry').update({
			'entry_type': 'Journal Entry',
			'naming_series': 'JV-',
			'posting_date': nowdate(),
			'company': items[0].company,
			'accounts': accounts
		})
		je.run_method('get_balance')
		je.accounts[-1].account = stock_devaluation_acc
		je.run_method('save')
		je.run_method('submit')
		frappe.msgprint(frappe._('The Delivery Notes {0} are reconciled in the Journal Entry `{1}`').format(
			', '.join(map(lambda s: '`{0}`'.format(s)), all_dns),
			je.name
		))


def get_against_reconcilable(customer, item_code):
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
			AND `tabDelivery Note`.`is_return` = 0
			AND `tabDelivery Note`.`status` != "Closed"
			AND `tabDelivery Note Item`.`amount` < 0 and `tabDelivery Note`.`outstanding_amount` < 0
			AND `tabDelivery Note`.`customer` = %s
			AND `tabDelivery Note Item`.`item_code` = %s
		"""

	ret = []
	for row in frappe.db.sql(sql, (customer, item_code), as_dict=False):
		if not row[-1] or not row[-1].splitlines():
			continue
		for sr in row[-1].splitlines():
			if not sr:
				continue
			r = copy(row)
			r[-1] = sr
			ret.append({
				'label': ' | '.join(map(unicode, row)),
				'value': row[0]
			})

	return ret