# -*- coding: utf-8 -*-
# Copyright (c) 2017, Dirk Chang and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
import redis
import requests
import datetime
import uuid
from frappe.utils import now, get_datetime, convert_utc_to_user_timezone
from frappe import throw, msgprint, _, _dict
from iot.doctype.iot_hdb_settings.iot_hdb_settings import IOTHDBSettings
from hdb_api import valid_auth_code


UTC_FORMAT1 = "%Y-%m-%dT%H:%M:%S.%fZ"
UTC_FORMAT2 = "%Y-%m-%dT%H:%M:%SZ"
def utc2local(utc_st):
    now_stamp = time.time()
    local_time = datetime.datetime.fromtimestamp(now_stamp)
    utc_time = datetime.datetime.utcfromtimestamp(now_stamp)
    offset = local_time - utc_time
    local_st = utc_st + offset
    return local_st

@frappe.whitelist()
def redis_status():
	from iot.doctype.iot_hdb_settings.iot_hdb_settings import get_redis_status
	return get_redis_status()


@frappe.whitelist()
def influxdb_status():
	from iot.doctype.iot_hdb_settings.iot_hdb_settings import get_influxdb_status
	return get_influxdb_status()


@frappe.whitelist()
def iot_device_data_f(sn=None, vsn=None):
	return json.load(open('/home/frappe/frappe-bench/sites/test/public/files/data.json'))


@frappe.whitelist()
def iot_device_data(sn=None, vsn=None):
	sn = sn or frappe.form_dict.get('sn')
	vsn = vsn or sn
	doc = frappe.get_doc('IOT Device', sn)
	doc.has_permission("read")

	if vsn != sn:
		if vsn not in iot_device_tree(sn):
			return ""

	cfg = iot_device_cfg(sn, vsn)
	if not cfg:
		return ""
	client = redis.Redis.from_url(IOTHDBSettings.get_redis_server() + "/2")
	hs = client.hgetall(vsn)
	data = {}
	if cfg.has_key("nodes"):
		nodes = cfg.get("nodes")
		for node in nodes:
			tags = node.get("tags")
			for tag in tags:
				name = node.get("name")+"."+tag.get('name')
				data[name] = {"PV": hs.get(name + ".PV"), "TM": hs.get(name + ".TM"), "Q": hs.get(name + ".Q"),
				              "DESC": tag.get("desc"), }

	if cfg.has_key("tags"):
		tags = cfg.get("tags")
		for tag in tags:
			name = tag.get('name')
			data[name] = {"PV": hs.get(name + ".PV"), "TM": hs.get(name + ".TM"), "Q": hs.get(name + ".Q"),
			              "DESC": tag.get("desc"), }

	return data


@frappe.whitelist()
def iot_device_data_array(sn=None, vsn=None):
	sn = sn or frappe.form_dict.get('sn')
	vsn = vsn or sn
	doc = frappe.get_doc('IOT Device', sn)
	doc.has_permission("read")

	if vsn != sn:
		if vsn not in iot_device_tree(sn):
			return ""

	cfg = iot_device_cfg(sn, vsn)
	if not cfg:
		return ""

	client = redis.Redis.from_url(IOTHDBSettings.get_redis_server() + "/2")
	hs = client.hgetall(vsn)
	data = []

	if cfg.has_key("nodes"):
		nodes = cfg.get("nodes")
		for node in nodes:
			tags = node.get("tags")
			for tag in tags:
				name = tag.get('name')
				tt = hs.get(name + ".TM")
				timestr = ''
				if tt:
					timestr = str(
						convert_utc_to_user_timezone(datetime.datetime.utcfromtimestamp(int(int(tt) / 1000))).replace(
							tzinfo=None))
				data.append({"NAME": name, "PV": hs.get(name + ".PV"),  # "TM": hs.get(name + ".TM"),
				             "TM": timestr, "Q": hs.get(name + ".Q"), "DESC": tag.get("desc"), })

	if cfg.has_key("tags"):
		tags = cfg.get("tags")
		for tag in tags:
			name = tag.get('name')
			tt = hs.get(name + ".TM")
			timestr = ''
			if tt:
				timestr = str(
					convert_utc_to_user_timezone(datetime.datetime.utcfromtimestamp(int(int(tt) / 1000))).replace(
						tzinfo=None))
			data.append({"NAME": name, "PV": hs.get(name + ".PV"),  # "TM": hs.get(name + ".TM"),
			             "TM": timestr, "Q": hs.get(name + ".Q"), "DESC": tag.get("desc"), })

	return data


@frappe.whitelist()
def iot_device_his_data(sn=None, vsn=None, fields=None, condition=None):
	vsn = vsn or sn
	fields = fields or "*"
	doc = frappe.get_doc('IOT Device', sn)
	doc.has_permission("read")

	if vsn != sn:
		if vsn not in iot_device_tree(sn):
			return 401

	inf_server = IOTHDBSettings.get_influxdb_server()
	if not inf_server:
		frappe.logger(__name__).error("InfluxDB Configuration missing in IOTHDBSettings")
		return 500
	query = 'SELECT ' + fields + ' FROM "' + vsn + '"'
	if condition:
		query = query + " WHERE " + condition
	else:
		query = query + " LIMIT 1000"

	domain = frappe.get_value("Cloud Company", doc.company, "domain")
	r = requests.session().get(inf_server + "/query", params={"q": query, "db": domain}, timeout=10)
	if r.status_code == 200:
		return r.json()["results"] or r.json()

	return r.text



@frappe.whitelist()
def taghisdata(sn=None, vsn=None, fields=None, condition=None):
	vsn = vsn or sn
	fields = fields or "*"
	doc = frappe.get_doc('IOT Device', sn)
	doc.has_permission("read")

	inf_server = IOTHDBSettings.get_influxdb_server()
	if not inf_server:
		frappe.logger(__name__).error("InfluxDB Configuration missing in IOTHDBSettings")
		return 500
	query = 'SELECT ' + fields + ' FROM "' + vsn + '"'
	if condition:
		query = query + " WHERE " + condition
	else:
		query = query + " LIMIT 1000"

	domain = frappe.get_value("Cloud Company", doc.company, "domain")
	r = requests.session().get(inf_server + "/query", params={"q": query, "db": domain}, timeout=10)
	if r.status_code == 200:
		try:
			res = r.json()["results"][0]['series'][0]['values']
			taghis = []
			for i in range(0, len(res)):
				hisvalue = {}
				#print('*********', res[i][0])
				try:
					utc_time = datetime.datetime.strptime(res[i][0], UTC_FORMAT1)
				except Exception as err:
					pass
				try:
					utc_time = datetime.datetime.strptime(res[i][0], UTC_FORMAT2)
				except Exception as err:
					pass
					local_time = str(convert_utc_to_user_timezone(utc_time).replace(tzinfo=None))
				#print('#######', local_time)
				if res[i][2] == '1':
					hisvalue = {'name': res[i][1], 'value': res[i][4], 'time': local_time, 'quality': 0}
				elif res[i][2] == '2':
					hisvalue = {'name': res[i][1], 'value': res[i][3], 'time': local_time, 'quality': 0}
				taghis.append(hisvalue)
			#print(taghis)
			return taghis
		except Exception as err:
			return r.json()

@frappe.whitelist()
def iot_device_tree(sn=None):
	sn = sn or frappe.form_dict.get('sn')
	doc = frappe.get_doc('IOT Device', sn)
	doc.has_permission("read")
	client = redis.Redis.from_url(IOTHDBSettings.get_redis_server() + "/1")
	return client.lrange(sn, 0, -1)


@frappe.whitelist()
def iot_device_cfg(sn=None, vsn=None):
	sn = sn or frappe.form_dict.get('sn')
	doc = frappe.get_doc('IOT Device', sn)
	doc.has_permission("read")
	client = redis.Redis.from_url(IOTHDBSettings.get_redis_server() + "/0")
	return json.loads(client.get(vsn or sn) or "")


def get_post_json_data():
	if frappe.request.method != "POST":
		throw(_("Request Method Must be POST!"))
	ctype = frappe.get_request_header("Content-Type")
	if "json" not in ctype.lower():
		throw(_("Incorrect HTTP Content-Type found {0}").format(ctype))
	data = frappe.request.get_data()
	if not data:
		throw(_("JSON Data not found!"))
	return json.loads(data)


@frappe.whitelist()
def iot_device_write():
	ctrl = _dict(get_post_json_data())
	doc = frappe.get_doc('IOT Device', ctrl.sn)
	doc.has_permission("read")
	cmd = {
		"sn": ctrl.vsn,
		"tag": ctrl.tag,
		"nrsp": ctrl.nrsp,
		"vt": ctrl.vt,
		"val": ctrl.val,
		"pris": ctrl.pris or uuid.uuid1()
	}

	client = redis.Redis.from_url(IOTHDBSettings.get_redis_server())
	r = client.publish("ziotagwrites", json.dumps({
		"cmds": [cmd],
		"ver": 0
	}))
	return {
		"result": r,
		"uuid": cmd["pris"]
	}


@frappe.whitelist(allow_guest=True)
def iot_device_api_write():
	valid_auth_code()
	return iot_device_write()


@frappe.whitelist(allow_guest=True)
def ping():
	form_data = frappe.form_dict
	if frappe.request and frappe.request.method == "POST":
		if form_data.data:
			form_data = json.loads(form_data.data)
		return form_data.get("text") or "No Text"
	return 'pong'
