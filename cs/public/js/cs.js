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
                (frm.doc.order_type !== 'Sales' || (
                    frm.doc.lead 
                    && frm.doc.__onload.has_customer)) ?
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
                    var fields = [], title = [];
                    if (frm.doc.lead && !frm.doc.__onload.has_customer){
                        title.push(__('Customer Details'));
                        fields = fields.concat([
                            {
                                'fieldtype': 'Section Break',
                                'label': __('Customer Details'), 
                            },
                            {
                                'fieldtype': 'Link',
                                'label': __('Customer Group'),
                                'options': 'Customer Group',
                                'reqd': 1
                            },
                            {
                                'fieldtype': 'Column Break'
                            },
                            {
                                'fieldtype': 'Link',
                                'label': __('Territory'),
                                'options': 'Territory',
                                'reqd': 1,
                                "default": frappe.defaults.get_global_default("territory")
                            }
                        ])
                    }
                    if ( frm.doc.order_type === 'Sales' ){
                        title.push(__('Delivery Date'));
                        fields = fields.concat([
                            {
                                'fieldtype': 'Section Break',
                                'label': __('Sales Order Details')
                            },
                            {
                                'fieldname': 'delivery_date',
                                'label': __('Delivery Date'),
                                'fieldtype': 'Date',
                                'reqd': 1
                            }
                        ])
                    }

                    if (title.length == 2){
                        title[0] = title[0] + ' ';
                        title[1] = ' ' + title[1]; 
                    }

                    frappe.prompt(
                        fields,
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
                        title.join(__('and')),
                        __('Process')
                    );
                }
            )
        }
    }
});