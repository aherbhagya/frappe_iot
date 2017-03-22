# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe import _
from iot.iot.doctype.iot_user.iot_user import add_user


def is_company_admin(user, company):
	return frappe.db.get_value("IOT Enterprise", {"name": company, "admin": user}, "admin")


def list_users_by_domain(domain):
	return frappe.get_all("User",
		filters={"email": ("like", "%@{0}".format(domain))},
		fields=["name", "full_name", "enabled", "email", "creation"])


def list_possible_users(company):
	domain = frappe.db.get_value("IOT Enterprise", company, "domain")
	users = list_users_by_domain(domain)
	return [user for user in users if not frappe.get_value('IOT User', {"user": user.name, "company": company})]


def get_context(context):
	company = frappe.form_dict.company
	if frappe.form_dict.user:
		add_user(frappe.form_dict.user, company)

	user = frappe.session.user

	if not company:
		raise frappe.ValidationError(_("You need specified IOT Enterprise"))

	user_roles = frappe.get_roles(frappe.session.user)
	if 'IOT User' not in user_roles or frappe.session.user == 'Guest':
		raise frappe.PermissionError("Your account is not an IOT User!")

	if not (is_company_admin(user, company) or 'IOT Manager' in user_roles):
		raise frappe.PermissionError

	context.no_cache = 1
	context.show_sidebar = True

	possible_users = list_possible_users(company)

	context.parents = [{"label": company, "route": "/iot_companys/" + company}]
	context.doc = {
		"company": company,
		"possible_users": possible_users
	}
