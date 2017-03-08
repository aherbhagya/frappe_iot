# -*- coding: utf-8 -*-
# Copyright (c) 2015, Dirk Chang and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
import requests
from frappe import throw, msgprint, _
from frappe.model.document import Document
from iot.doctype.iot_device.iot_device import IOTDevice
from iot.doctype.iot_hdb_settings.iot_hdb_settings import IOTHDBSettings
from iot.doctype.iot_settings.iot_settings import IOTSettings


def valid_auth_code(auth_code=None):
	auth_code = auth_code or frappe.get_request_header("HDB_AuthorizationCode")
	if not auth_code:
		throw(_("HDB_AuthorizationCode is required in HTTP Header!"))
	frappe.logger(__name__).debug(_("HDB_AuthorizationCode as {0}").format(auth_code))

	code = IOTHDBSettings.get_authorization_code()
	if auth_code != code:
		throw(_("Authorization Code is incorrect!"))

	frappe.session.user = IOTHDBSettings.get_on_behalf()


@frappe.whitelist(allow_guest=True)
def list_enterprises(usr=None, pwd=None):
	valid_auth_code()
	# 	return frappe.get_all("IOT Enterprise", fields=["*"], filters = {"name": ("like", "*")})
	return frappe.get_all("IOT Enterprise", fields=["name", "ent_name", "enabled", "admin", "domain"])


@frappe.whitelist(allow_guest=True)
def login(user=None, passwd=None):
	"""
	HDB Application checking for user login
	:param user: Username (Frappe Username)
	:param pwd: Password (Frappe User Password)
	:return: {"user": <Frappe Username>, "ent": <IOT Enterprise>}
	"""
	valid_auth_code()
	if not (user and passwd):
		usr, passwd = frappe.form_dict.get('user'), frappe.form_dict.get('passwd')
	frappe.logger(__name__).debug(_("HDB Checking login {0} password {1}").format(user, passwd))

	"""
	if '@' not in usr:
		throw(_("Username must be <login_name>@<enterprise domain>"))

	login_name, domain = usr.split('@')
	enterprise = frappe.db.get_value("IOT Enterprise", {"domain": domain}, "name")
	if not enterprise:
		throw(_("Enterprise Domain {0} does not exists").format(domain))

	user = frappe.db.get_value("IOT User", {"enterprise": enterprise, "login_name": login_name}, "user")
	if not user:
		throw(_("User login_name {0} not found in Enterprise {1}").format(login_name, enterprise))
	"""

	frappe.local.login_manager.authenticate(user, passwd)
	if frappe.local.login_manager.user != user:
		throw(_("Username password is not matched!"))

	enterprise = frappe.get_value("IOT User", user, "enterprise") or IOTSettings.get_default_enterprise()
	
	return {"usr": user, "ent": enterprise}


@frappe.whitelist(allow_guest=True)
def list_devices(user=None):
	"""
	List devices according to user specified in query params by naming as 'usr'
		this user is ERPNext user which you got from @iot.auth.login
	:param user: ERPNext username
	:return: device list
	"""
	valid_auth_code()
	user = user or frappe.form_dict.get('user')
	if not user:
		throw(_("Query string user does not specified"))
	frappe.logger(__name__).debug(_("List Devices for user {0}").format(user))

	devices = []

	if frappe.get_value("IOT User", user):
		user_doc = frappe.get_doc("IOT User", user)
		groups = user_doc.get("group_assigned")
		for g in groups:
			bunch_codes = [d[0] for d in frappe.db.get_values("IOT Device Bunch", {"owner_id": g.group, "owner_type": "IOT Employee Group"}, "code")]
			sn_list = []
			for c in bunch_codes:
				sn_list.append({"bunch": c, "sn": IOTDevice.list_device_sn_by_bunch(c)})
			devices.append({"group": g.group, "devices": sn_list})

	bunch_codes = [d[0] for d in frappe.db.get_values("IOT Device Bunch", {"owner_id": user, "owner_type": "User"}, "code")]
	sn_list = []
	for c in bunch_codes:
		sn_list.append({"bunch": c, "sn": IOTDevice.list_device_sn_by_bunch(c)})
	devices.append({"private_devices": sn_list})

	return devices


def get_post_json_data():
	if frappe.request.method != "POST":
		throw(_("Request Method Must be POST!"))
	ctype = frappe.get_request_header("Content-Type")
	if "json" not in ctype.lower():
		throw(_("Incorrect HTTP Content-Type found {0}").format(ctype))
	if not frappe.form_dict.data:
		throw(_("JSON Data not found!"))
	return json.loads(frappe.form_dict.data)


@frappe.whitelist(allow_guest=True)
def get_device(sn=None):
	valid_auth_code()
	sn = sn or frappe.form_dict.get('sn')
	if not sn:
		throw(_("Request fields not found. fields: sn"))

	dev = IOTDevice.get_device_doc(sn)
	return dev


@frappe.whitelist(allow_guest=True)
def add_device(device_data=None):
	valid_auth_code()
	device = device_data or get_post_json_data()
	sn = device.get("sn")
	if not sn:
		throw(_("Request fields not found. fields: sn"))

	if IOTDevice.check_sn_exists(sn):
		# TODO: Check for bunch code when device is existing.
		return IOTDevice.get_device_doc(sn)

	device.update({
		"doctype": "IOT Device"
	})
	doc = frappe.get_doc(device).insert().as_dict()

	url = IOTHDBSettings.get_callback_url()
	if url:
		""" Fire callback data """
		session = requests.session()
		user_list = IOTDevice.find_owners_by_bunch(device.get("bunch"))
		r = session.post(url, json={
			'cmd': 'add_device',
			'sn': sn,
			'users': user_list
		})

		if r.status_code != 200:
			frappe.logger(__name__).error("Callback Failed! \r\n", r.content)

	return doc


@frappe.whitelist(allow_guest=True)
def update_device():
	valid_auth_code()
	data = get_post_json_data()
	if data.get("bunch") is not None:
		add_device(device_data=data)
	update_device_bunch(device_data=data)
	return update_device_status(device_data=data)


@frappe.whitelist(allow_guest=True)
def update_device_bunch(device_data=None):
	valid_auth_code()
	data = device_data or get_post_json_data()
	bunch = data.get("bunch")
	sn = data.get("sn")
	if sn is None:
		throw(_("Request fields not found. fields: sn"))

	dev = IOTDevice.get_device_doc(sn)
	if not dev:
		throw(_("Device is not found. SN:{0}").format(sn))

	if bunch == "":
		bunch = None
	if dev.bunch == bunch:
		return dev

	org_bunch = dev.bunch
	dev.update_bunch(bunch)

	url = IOTHDBSettings.get_callback_url()
	if url:
		""" Fire callback data """
		session = requests.session()
		org_user_list = IOTDevice.find_owners_by_bunch(org_bunch)
		user_list = IOTDevice.find_owners_by_bunch(bunch)
		r = session.post(url, json={
			'cmd': 'update_device',
			'sn': sn,
			'add_users': user_list,
			'del_users': org_user_list
		})

		if r.status_code != 200:
			frappe.logger(__name__).error("Callback Failed! \r\n", r.content)

	return dev


@frappe.whitelist(allow_guest=True)
def update_device_status(device_data=None):
	valid_auth_code()
	data = device_data or get_post_json_data()
	status = data.get("status")
	sn = data.get("sn")
	if not (sn and status):
		throw(_("Request fields not found. fields: sn\tstatus"))

	dev = IOTDevice.get_device_doc(sn)
	if not dev:
		throw(_("Device is not found. SN:{0}").format(sn))

	dev.update_status(status)
	return dev


@frappe.whitelist(allow_guest=True)
def update_device_name():
	valid_auth_code()
	data = get_post_json_data()
	name = data.get("name")
	sn = data.get("sn")
	if not (sn and name):
		throw(_("Request fields not found. fields: sn\tname"))

	dev = IOTDevice.get_device_doc(sn)
	if not dev:
		throw(_("Device is not found. SN:{0}").format(sn))

	dev.update_name(name)
	return dev


@frappe.whitelist(allow_guest=True)
def get_time():
	valid_auth_code()
	return frappe.utils.now()


@frappe.whitelist(allow_guest=True)
def ping():
	form_data = frappe.form_dict
	if frappe.request and frappe.request.method == "POST":
		if form_data.data:
			form_data = json.loads(form_data.data)
		return form_data.get("text") or "No Text"
	return 'pong'


