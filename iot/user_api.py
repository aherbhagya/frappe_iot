# -*- coding: utf-8 -*-
# Copyright (c) 2017, Dirk Chang and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
import redis
import datetime
import uuid
import hdb_api
import hdb
from frappe.utils import now, get_datetime, convert_utc_to_user_timezone
from frappe import throw, msgprint, _, _dict


def valid_auth_code(auth_code=None):
	if 'Guest' != frappe.session.user:
		return
	auth_code = auth_code or frappe.get_request_header("AuthorizationCode")
	if not auth_code:
		throw(_("AuthorizationCode is required in HTTP Header!"))
	frappe.logger(__name__).debug(_("API AuthorizationCode as {0}").format(auth_code))

	user = frappe.get_value("IOT User Api", {"authorization_code": auth_code}, "user")
	if not user:
		throw(_("Authorization Code is incorrect!"))
	# form dict keeping
	form_dict = frappe.local.form_dict
	frappe.set_user(user)
	frappe.local.form_dict = form_dict


@frappe.whitelist(allow_guest=True)
def get_user():
	valid_auth_code()
	return frappe.session.user


@frappe.whitelist(allow_guest=True)
def gen_uuid():
	return str(uuid.uuid1()).upper()


@frappe.whitelist(allow_guest=True)
def list_devices():
	valid_auth_code()
	return hdb_api.list_iot_devices(frappe.session.user)


@frappe.whitelist(allow_guest=True)
def get_device(sn=None):
	valid_auth_code()
	return hdb_api.get_device(sn)


@frappe.whitelist(allow_guest=True)
def iot_device_tree(sn=None):
	valid_auth_code()
	return hdb.iot_device_tree(sn)


@frappe.whitelist(allow_guest=True)
def iot_device_cfg(sn=None, vsn=None):
	valid_auth_code()
	return hdb.iot_device_cfg(sn, vsn)


@frappe.whitelist(allow_guest=True)
def iot_device_data(sn=None, vsn=None):
	valid_auth_code()
	return hdb.iot_device_data(sn, vsn)


@frappe.whitelist(allow_guest=True)
def iot_device_data_array(sn=None, vsn=None):
	valid_auth_code()
	return hdb.iot_device_data_array(sn, vsn)


@frappe.whitelist(allow_guest=True)
def iot_device_his_data(sn=None, vsn=None, fields=None, condition=None):
	valid_auth_code()
	return hdb.iot_device_his_data(sn, vsn)


@frappe.whitelist(allow_guest=True)
def iot_device_write():
	valid_auth_code()
	return hdb.iot_device_write()