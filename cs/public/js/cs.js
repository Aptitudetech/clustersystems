frappe.ui.form.on('Project', {
    project_type: function(frm, cdt, cdn){
        frm.toggle_reqd( 'template_type', frm.doc.project_type === 'Template' );
    }
});

frappe.ui.form.on('Quotation', {
    refresh: function(frm, cdt, cdn){
        if (frm.doc.docstatus === 1 && !frm.doc.__onload.has_sales_order){
            frm.add_custom_button(
                __('Process Quote'),
                (
                    frm.doc.customer || (
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
                                'fieldtype': 'Select',
                                'label': __('Customer Language'),
                                'fieldname': 'language',
                                'options': frappe.get_languages(),
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

frappe.ui.form.on('Sales Invoice', {
    'refresh': function(frm){
        if (frm.doc.__islocal && frm.doc.is_return){
            frm.set_value('naming_series', 'SINV-RET');
        }
    }
});

frappe.ui.form.on('Lead', {
    'appointment_date': function(frm, cdt, cdn){
        if (!frm.doc.appointment_location){
            frappe.call({
                'method': 'cs.events.get_company_address',
                'args': {
                    'company': frm.doc.company
                },
                'callback': function(res){
                    if (res && res.message){
                        frm.set_value('appointment_location', res.message)
                    }
                }
            });
        }
    }
});

frappe.ui.form.on('Project', 'refresh', function(frm, cdt, cdn){
    if (!frm.doc.__islocal && frm.doc.template_type === "Swap and Warranty"){
        if (frm.doc.template_type === "Swap and Warranty"){
            var fields = [
                {
                    'fieldname': 'warehouse',
                    'label': __('Warehouse for Replacement'),
                    'fieldtype': 'Link',
                    'options': 'Warehouse',
                    'reqd': 1,
                    'default': frappe.defaults.get_global_default("warehouse_for_return"),
                    'get_query': function(){
                        return {
                            filters: {
                                'is_group': ["=", 0],
                                'company': frm.doc.company
                            }
                        }
                    },
                    'on_make': function(field){
                        debugger;
                        field.refresh();
                        field.$input.on('change', function(ev){
                            if (d.get_value('warehouse') && d.get_value('item_code')){
                                frappe.call({
                                    'method': 'erpnext.stock.utils.get_stock_balance',
                                    'args': {
                                        'item_code': d.get_value('item_code'),
                                        'warehouse': d.get_value('warehouse'),
                                        'with_valuation_rate': 1
                                    },
                                    'callback': function(res){
                                        if (res && res.message && res.message.length == 2 && res.message[1] > 0){
                                            d.set_value('valuation_rate', res.message[1]);
                                        }
                                    }
                                });
                            }
                        });
                    }
                },
                {
                    'fieldname': 'item_code',
                    'label': __('Item Code'),
                    'fieldtype': 'Link',
                    'options': 'Item',
                    'get_query': function(doc){
                        var filters = {
                            "is_stock_item": 1,
                            "has_serial_no": 1
                        };
                        if (doc.__onload && doc.__onload.dn_item_codes){
                            filters['name'] = ['in', doc.__onload.dn_item_codes];
                        }
                        return {
                            'query': "erpnext.controllers.queries.item_query",
                            'filters': filters
                        }
                    },
                    'default': frm.doc.__onload && frm.doc.__onload.dn_item_codes && frm.doc.__onload.dn_item_codes.length ? frm.doc.__onload.dn_item_codes[0] : null,
                    'on_make': function(field){
                        debugger;
                        field.refresh();
                        field.$input.on('change', function(ev){
                            if (d.get_value('warehouse') && d.get_value('item_code')){
                                frappe.call({
                                    'method': 'erpnext.stock.utils.get_stock_balance',
                                    'args': {
                                        'item_code': d.get_value('item_code'),
                                        'warehouse': d.get_value('warehouse'),
                                        'with_valuation_rate': 1
                                    },
                                    'callback': function(res){
                                        if (res && res.message && res.message.length == 2 && res.message[1] > 0){
                                            d.set_value('valuation_rate', res.message[1]);
                                        }
                                    }
                                });
                            }
                        });
                    }
                },
                {
                    'fieldname': 'serial_no',
                    'label': __('Serial No Received'),
                    'fieldtype': 'Data',
                    'reqd': 1
                },
                {
                    "fieldtype": "Column Break"
                },
                {
                    'fieldtype': 'Currency',
                    'fieldname': 'valuation_rate',
                    'label': __('Valuation Rate'),
                    'on_make': function(field){
                        debugger;
                        field.refresh();
                        field.$input.on('change', function(ev){
                            if (d.get_value('valuation_rate') && d.get_value('percent_for_return')){
                                d.set_value('credit_amount', (
                                    d.get_value('valuation_rate') * get.value('percent_for_return') / 100.0)
                                );
                            }
                            return true;
                        });
                    }
                },
                {
                    'fieldtype': 'Percent',
                    'fieldname': 'percent_for_return',
                    'label': __('Percent Amount'),
                    'default': frappe.defaults.get_global_default('percent_for_return'),
                    'on_make': function(field){
                        debugger;
                        field.refresh();
                        field.$input.on('change', function(ev){
                            if (d.get_value('valuation_rate') && d.get_value('percent_for_return')){
                                d.set_value('credit_amount', (
                                    d.get_value('valuation_rate') * get.value('percent_for_return') / 100.0)
                                );
                            }
                            return true;
                        });
                    }
                },
                {
                    'fieldtype': 'Currency',
                    'fieldname': 'credit_amount',
                    'label': __('Credit Amount'),
                    'reqd': 1
                }
            ]
        }
        frm.add_custom_button(__("Create Return"), function(){
            frappe.prompt(
                fields,
                function(args){
                    delete args['valuation_rate'];
                    delete args['percent_for_return'];
                    args['company'] = frm.doc.company;
                    args['customer'] = frm.doc.customer;
                    args['project'] = frm.doc.name;
                    frappe.call({
                        'method': 'cs.events.make_return',
                        'args': args,
                        'freeze_message': __('Please wait a few moments while we process your return'),
                        'freeze': true
                    });
                },
                __('Serial Number for Return')
            );
        });
    }
});