# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "cs"
app_title = "Cluster Systems"
app_publisher = "aptitudetech"
app_description = "Cluster Systems"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "info@aptitudetech.net"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/cs/css/cs.css"
app_include_js = "/assets/cs/js/cs.js"

# include js, css files in header of web template
# web_include_css = "/assets/cs/css/cs.css"
# web_include_js = "/assets/cs/js/cs.js"

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

doctype_calendar_js = {
	"Task": "public/js/task_calendar.js"
}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Website user home page (by function)
# get_website_user_home_page = "cs.utils.get_home_page"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "cs.install.before_install"
# after_install = "cs.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "cs.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

doc_events = {
	"Lead": {
		"onload": [
			"cs.events.on_lead_onload"
		],
		"validate": [
			"cs.events.on_lead_validate"
		],
		"oninsert": [
			"cs.events.on_lead_oninsert",
		],
		"on_update": [
			"cs.events.on_lead_onupdate"
		]
	},
	"Customer": {
		'onload': [
			"cs.events.on_customer_onload"
		],
		'validate': [
			"cs.events.on_customer_validate"
		]
	},
	"Opportunity": {
		'onload': [
			"cs.events.on_lead_onload"
		],
		'validate': [
			"cs.events.on_lead_validate"
		],
		'oninsert': [
			"cs.events.on_lead_oninsert"
		],
		'on_update': [
			"cs.events.on_lead_onupdate"
		]
	},
	"Quotation": {
		"onload": [
			"cs.events.quotation_onload"
		]
	},
	"Delivery Note": {
		"on_submit": [
			"cs.events.on_delivery_note_onsubmit"
		]
	},
	"Sales Invoice": {
		"on_submit": [
			"cs.events.on_sales_invoice_onsubmit"
		]
	},
	"Project": {
		"onload": [
			"cs.events.on_project_onload"
		],
		"validate": [
			"cs.events.on_project_validate"
		],
	},
	"Stock Entry": {
		"on_submit": [
			"cs.events.on_stock_entry_on_submit"
		]
	}
}

has_website_permission = {
	"Customer": "cs.website_permissions.has_website_permission"
}

# Scheduled Tasks
# ---------------

scheduler_events = {
# 	"all": [
# 		"cs.tasks.all"
# 	],
# 	"daily": [
# 		"cs.tasks.daily"
# 	],
	"hourly": [
		"cs.tasks.hourly"
],
# 	"weekly": [
# 		"cs.tasks.weekly"
# 	]
# 	"monthly": [
# 		"cs.tasks.monthly"
# 	]
}

# Testing
# -------

# before_tests = "cs.install.before_tests"

# Overriding Whitelisted Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "cs.event.get_events"
# }

fixtures = [
	{"dt": "Print Format", "filters": {"standard": "No"}},
	{"dt": "Standard Reply"},
	{"dt": "Website Theme", "filters": {"name": "Cluster"}},
	{"dt": "Portal Settings"},
	{"dt": "Custom Field", "filters": {"dt": "Customer"}},
	{"dt": "Website Script"}
]

get_website_user_home_page = "cs.routes.get_website_user_home_page"
