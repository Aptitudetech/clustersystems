// Copyright (c) 2017, aptitudetech and contributors
// For license information, please see license.txt

frappe.ui.form.on('Delivery Note Reconciliation', {
	refresh: function(frm) {

	}
});

frappe.ui.form.on('Delivery Note Reconciliation Detail', {
	'get_against_reconcilable': function(frm, cdt, cdn){
		var grid_row = frm.fields_dict.details.grid.grid_rows_by_docname[d.name].grid,
			df = frappe.utils.filter_dict(grid_row.docfields, {'fieldname': 'reconcile_against'})[0];
		frappe.call({
			'method': 'cs.cs.doctype.delivery_note_reconciliation.delivery_note_reconciliation.get_against_reconcilable',
			'args': {
				'customer': d.customer,
				'item_code': d.item_code
			},
			callback: function(res){
				if (res && res.message){
					df.options = res.message
				} else {
					df.options = [];
				}
			}
		});
	},
	'action': function(frm, cdt, cdn){
		var d = locals[cdt][cdn];
		if (d.action === 'Reconcile' && !d.serial_no){
			frappe.msgprint(__('Only serializable items can be reconciled trought this tool!'));
			frappe.model.set_value(cdt, cdn, 'action', 'Bill');
		} else if (d.action === 'Reconcile'){
			frappe.ui.form.get_event_handler_list('Delivery Note Reconciliation Detail', 'get_against_reconcilable').forEach(function(fn){
				fn(frm, cdt, cdn);
			});
		}
	}
})