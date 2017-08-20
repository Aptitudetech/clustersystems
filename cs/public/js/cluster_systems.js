frappe.ui.form.on('Project', {
    project_type: function(frm, cdt, cdn){
        frm.toggle_reqd( 'template_type', frm.doc.project_type === 'Template' );
    }
});

frappe.ui.form.on('Quotation', {
    refresh: function(frm, cdt, cdn){
        if (frm.doc.docstatus === 1 && !frm.doc.project){
            frm.add_custom_button(
                __('Process Quote'),
                function(){
                    frm.call({
                        'method': 'process_quote'
                    });
                }
            )
        }
    }
});