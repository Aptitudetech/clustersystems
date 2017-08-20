frappe.ui.form.on('Project', {
    project_type: function(frm, cdt, cdn){
        frm.toggle_reqd( 'template_type', frm.doc.project_type === 'Template' );
    }
});

frappe.ui.form.on('Quotation', {
    refresh: function(frm, cdt, cdn){
        if (frm.doc.docstatus === 1){
            frm.add_custom_button(
                __('Process Quote'),
                (frm.doc.order_type !== 'Sales') ?
                function(){
                    frm.call({
                        'method': 'cs.events.process_quote',
                        'args': {
                            'quote': frm.doc.name
                        },
                        'freeze_message': __('Please wait a few moments while we process your quote'),
                        'freeze': true
                    });
                } :
                function() {
                    frappe.prompt([
                        {
                            'fieldname': 'delivery_date',
                            'label': __('Sales Order Delivery Date'),
                            'fieldtype': 'Date',
                            'reqd': 1
                        }],
                        function(args){
                            frm.call({
                                'method': 'cs.events.process_quote',
                                'args': {
                                    'quote': frm.doc.name,
                                    'delivery_date': args.delivery_date
                                },
                                'freeze_message': __('Please wait a few moments while we process your quote'),
                                'freeze': true
                            });
                        },
                        __('Delivery Date for Sales Order'),
                        __('Process')
                    );
                }
            )
        }
    }
});