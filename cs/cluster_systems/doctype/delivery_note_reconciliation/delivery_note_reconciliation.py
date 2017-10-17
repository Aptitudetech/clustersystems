# -*- coding: utf-8 -*-
# Copyright (c) 2017, aptitudetech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from itertools import groupby
from frappe.model.document import Document
from frappe.utils import nowdate

class DeliveryNoteReconciliation(Document):
	def onload(self):
		if self.details:
			self.details = []

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
			AND `tabDelivery Note Item`.`amount` > 0 and round(`tabDelivery Note Item`.`billed_amt` *
			    ifnull(`tabDelivery Note`.`conversion_rate`, 1), 2) < `tabDelivery Note Item`.`base_amount`
		ORDER BY `tabDelivery Note`.`name`
		"""

		for row in frappe.db.sql(sql, as_dict=True):
			if not row['serial_no']:
				row['action'] == 'Bill'
				self.append('details', row)
			else:
				sri = len([s for s in row['serial_no'].splitlines() if s])
				for sr in row['serial_no'].splitlines():
					if not sr:
						continue
					srow = row.copy()
					srow['serial_no'] = sr
					srow['qty'] = srow['qty'] / sri
					srow['amount'] = srow['amount'] / sri
					self.append('details', srow)

	def validate(self):
		msgs = []
		for row in self.get('details', {'action': 'reconcile'}):
			if not row.reconcile_against:
				msgs.append(frappe._('One refrence document is required to reconcile `{0}` at row # `{1}`').format(
					row.delivery_note,
					row.idx
				))
		if msgs:
			frappe.throw('<br>'.join(msgs))

	def run(self):
		self.run_method('validate')
		for ac, items in groupby(self.details, lambda r: r.get('action')):
			if not ac:
				continue
			elif ac == "Bill":
				self.bill_items(list(items))
			elif ac == "Reconcile":
				self.reconcile_items(list(items))
		self.run_method('onload')

	def bill_items(self, items):
		from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice
		msgs = []
		for dn, items in groupby(items, lambda r: r.get('delivery_note')):
			items = list(items)
			item_codes = set([r.get('item_code') for r in items])
			si = make_sales_invoice(dn)

			for i, r in enumerate(si.get('items')):
				if r.get('item_code') not in item_codes:
					del si.items[i]
				r.update({
					'qty': 0.0,
					'rate': 0.0,
					'serial_no': '' 
				})
				for sr in filter(lambda _r: _r.get('item_code') == r.get('item_code'), items):
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

	def reconcile_items(self, items):
		from erpnext.accounts.party import get_party_account

		items = list(items)
		item_codes = list(set([r.get('item_code') for r in items]))
		dns = [r.delivery_note for r in items]
		all_dns = [r.reconcile_against for r in items if r.reconcile_against] + dns
		settings = frappe.get_doc('Cluster System Settings', 'Cluster System Settings')
		stock_devaluation_acc = settings.get('account_for_stock_devaluation')

		if not stock_devaluation_acc:
			frappe.throw(frappe._('You need to setup an Stock Devaluation account, under Cluster System Settings'))

		accounts = []
		for delivery_note in set(all_dns):
			d_or_c = frappe.db.get_value('Delivery Note', delivery_note, 'grand_total')
			accounts.append({
				'account': frappe.db.get_value('Item', item_codes[0], 'expense_account'),
				'reference_type': 'Delivery Note',
				'reference_name': delivery_note,
				'debit_in_account_currency': abs(d_or_c) if d_or_c <= 0 else 0.0,
				'debit': abs(d_or_c) if d_or_c <= 0 else 0.0,
				'credit_in_account_currency': abs(d_or_c) if d_or_c > 0 else 0.0,
				'credit': abs(d_or_c) if d_or_c > 0 else 0.0,
			})
			frappe.get_doc('Delivery Note', delivery_note).update_status('Closed')

		je = frappe.new_doc('Journal Entry').update({
			'entry_type': 'Journal Entry',
			'naming_series': 'JV-',
			'posting_date': nowdate(),
			'company': items[0].company,
			'accounts': accounts
		})
		je.run_method('set_total_debit_credit')
		if abs(je.difference):
			je.append('accounts', {
				"account": stock_devaluation_acc,
				"debit": abs(min([je.difference, 0.0])),
				"debit_in_account_currency": abs(min([je.difference, 0.0])),
				"credit": abs(max([je.difference, 0.0])),
				"credit_in_account_currency": abs(max([je.difference, 0.0]))
			})
		for row in je.accounts:
			setattr(row, '_validate_selects', lambda *args: None)	
		je.run_method('save')
		je.run_method('submit')
		frappe.msgprint(frappe._('The Delivery Notes {0} are reconciled in the Journal Entry `{1}`').format(
			', '.join(map(lambda s: '`{0}`'.format(s), all_dns)),
			je.name
		))


@frappe.whitelist()
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
			AND `tabDelivery Note`.`is_return` = 1
			AND `tabDelivery Note`.`status` != "Closed"
			AND `tabDelivery Note Item`.`amount` < 0
			AND `tabDelivery Note`.`customer` = %s
		"""

	ret = []
	for row in frappe.db.sql(sql, (customer), as_dict=False):
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
