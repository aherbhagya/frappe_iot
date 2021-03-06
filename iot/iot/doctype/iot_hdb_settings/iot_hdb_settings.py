# -*- coding: utf-8 -*-
# Copyright (c) 2017, Dirk Chang and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import re
import redis
import requests
from frappe import throw, _
from frappe.model.document import Document


class IOTHDBSettings(Document):
	def validate(self):
		if self.enable_default_bunch_code and not self.default_bunch_code:
			throw(_("Default Bunch Code Missing"))

	def update_redis_status(self, status):
		self.redis_status = status
		self.redis_updated = frappe.utils.now()
		self.save()

	def update_influxdb_status(self, status):
		self.influxdb_status = status
		self.influxdb_updated = frappe.utils.now()
		self.save()

	def update_hdb_status(self, status):
		self.hdb_status = status
		self.hdb_updated = frappe.utils.now()
		self.save()

	def refresh_status(self):
		#frappe.enqueue('iot.iot.doctype.iot_hdb_settings.iot_hdb_settings.get_hdb_status')
		get_hdb_status(self)

	@staticmethod
	def get_on_behalf(auth_code):
		if frappe.db.get_single_value("IOT HDB Settings", "authorization_code") == auth_code:
			return frappe.db.get_single_value("IOT HDB Settings", "on_behalf")
		return None

	@staticmethod
	def get_redis_server():
		url = frappe.db.get_single_value("IOT HDB Settings", "redis_server")
		if not url:
			return None
		return gen_server_url(url, "redis", 6379)

	@staticmethod
	def get_influxdb_server():
		url = frappe.db.get_single_value("IOT HDB Settings", "influxdb_server")
		if not url:
			return None
		return gen_server_url(url, "http", 8086)

	@staticmethod
	def get_default_bunch():
		return frappe.db.get_single_value("IOT HDB Settings", "default_bunch_code")

	@staticmethod
	def is_default_bunch_enabled():
		return frappe.db.get_single_value("IOT HDB Settings", "enable_default_bunch_code")


def gen_server_url(server, protocol, port):
	m = re.search("^(.+)://(.+)$", server)
	if m:
		protocol = m.group(1)
		server = m.group(2)

	m = re.search("^(.+):(\d+)$", server)

	if m:
		server = m.group(1)
		port = m.group(2)
	return ("{0}://{1}:{2}").format(protocol, server, port)


def get_redis_status():
	try:
		client = redis.Redis.from_url(IOTHDBSettings.get_redis_server(), socket_timeout=0.1,
										socket_connect_timeout=0.1)
		return client.ping()
	except Exception:
		return False


def get_influxdb_status():
	try:
		inf_server = IOTHDBSettings.get_influxdb_server()
		if not inf_server:
			frappe.logger(__name__).error("InfluxDB Configuration missing in IOTHDBSettings")
			return

		r = requests.session().get(inf_server + "/query", params={"q": '''SHOW USERS'''}, timeout=1)
		return r.status_code == 200
	except Exception:
		return False


def get_hdb_status(doc):
	doc = doc or frappe.get_single("IOT HDB Settings")

	status = get_redis_status()
	if status:
		doc.update_redis_status("ON")
	else:
		doc.update_redis_status("OFF")

	status = get_influxdb_status()
	if status:
		doc.update_influxdb_status("ON")
	else:
		doc.update_influxdb_status("OFF")
