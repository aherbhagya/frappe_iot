# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe import _


def is_enterprise_admin(user, enterprise):
	return frappe.db.get_value("IOT Enterprise", {"name": enterprise, "admin": user}, "admin")


def list_possible_users(enterprise):
	domain = frappe.db.get_value("IOT Enterprise", enterprise, "domain")
	return frappe.get_all("User",
		filters={"email": ("like", "%@{0}".format(domain))},
		fields=["name", "full_name", "enabled", "email", "creation"])


def get_context(context):
	enterprise = frappe.form_dict.enterprise
	user = frappe.session.user

	if not enterprise:
		raise frappe.ValidationError(_("You need specified IOT Enterprise"))

	user_roles = frappe.get_roles(frappe.session.user)
	if 'IOT User' not in user_roles or frappe.session.user == 'Guest':
		raise frappe.PermissionError("Your account is not an IOT User!")

	if not (is_enterprise_admin(user, enterprise) or 'IOT Manager' in user_roles):
		raise frappe.PermissionError

	context.no_cache = 1
	context.show_sidebar = True

	possible_users = list_possible_users(enterprise)

	context.parents = [{"label": enterprise, "route": "/iot_enterprise/" + enterprise}]
	context.doc = {
		"enterprise": enterprise,
		"possible_users": possible_users
	}