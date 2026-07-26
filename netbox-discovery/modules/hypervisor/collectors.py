#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import atexit
import datetime
import hashlib
import ipaddress
import json
import re
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
import os
import sys

BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")
VENDOR = os.path.join(BASE, "vendor")
if os.path.isdir(VENDOR) and VENDOR not in sys.path:
    sys.path.insert(0, VENDOR)

from modules.hypervisor.config import clean

COLLECTOR_VERSION = "1.0-product"


def utc_now():
    return datetime.datetime.utcnow().isoformat() + "Z"


def safe_int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return default


def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def norm_mac(value):
    raw = re.sub(r"[^0-9A-Fa-f]", "", clean(value))
    if len(raw) != 12:
        return ""
    raw = raw.upper()
    return ":".join(raw[i:i + 2] for i in range(0, 12, 2))


def valid_ip(value):
    value = clean(value)
    if not value:
        return ""
    try:
        obj = ipaddress.ip_address(value.split("%")[0].split("/")[0])
        if obj.is_loopback or obj.is_link_local or obj.is_multicast or obj.is_unspecified:
            return ""
        return str(obj)
    except Exception:
        return ""


def endpoint_host(endpoint):
    value = clean(endpoint)
    if "://" not in value:
        return value.split("/")[0].split(":")[0] if value.count(":") == 1 else value
    parsed = urllib.parse.urlparse(value)
    return parsed.hostname or value


def mask_to_prefix(mask):
    mask = clean(mask)
    if not mask:
        return None
    try:
        return ipaddress.ip_network("0.0.0.0/{0}".format(mask), strict=False).prefixlen
    except Exception:
        return None


def normalize_ip_record(address, prefix_length=None, primary=False):
    ip = valid_ip(address)
    if not ip:
        return None
    prefix = None
    try:
        if prefix_length is not None and clean(prefix_length) != "":
            prefix = int(prefix_length)
            max_prefix = 32 if ipaddress.ip_address(ip).version == 4 else 128
            if prefix < 0 or prefix > max_prefix:
                prefix = None
    except Exception:
        prefix = None
    return {"address": ip, "prefix_length": prefix, "primary": bool(primary)}


def _vmware_context(source):
    if bool(source.get("verify_ssl", False)):
        return ssl.create_default_context()
    return ssl._create_unverified_context()


def _vmware_connect(source):
    try:
        from pyVim.connect import SmartConnect, Disconnect
    except Exception as exc:
        raise RuntimeError(
            "pyVmomi indisponível ({0}). Reinstale/atualize o produto.".format(exc)
        )
    host = endpoint_host(source.get("endpoint"))
    previous_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(safe_int(source.get("timeout"), 60) or 60)
    try:
        service_instance = SmartConnect(
            host=host,
            user=source.get("username"),
            pwd=source.get("secret"),
            port=safe_int(source.get("port"), 443) or 443,
            sslContext=_vmware_context(source),
        )
    finally:
        socket.setdefaulttimeout(previous_timeout)
    atexit.register(Disconnect, service_instance)
    return service_instance, Disconnect


def _vmware_list(content, vim_type):
    view = content.viewManager.CreateContainerView(content.rootFolder, [vim_type], True)
    try:
        return list(view.view)
    finally:
        view.Destroy()


def _vmware_datacenter(obj, vim):
    cur = obj
    while cur:
        if isinstance(cur, vim.Datacenter):
            return clean(cur.name)
        cur = getattr(cur, "parent", None)
    return ""


def _vmware_cluster(host, vim):
    parent = getattr(host, "parent", None)
    if isinstance(parent, vim.ClusterComputeResource):
        return clean(parent.name)
    return ""


def _vmware_host_serial(host):
    hardware = getattr(host, "hardware", None)
    system_info = getattr(hardware, "systemInfo", None)
    serial = clean(getattr(system_info, "serialNumber", ""))
    if serial:
        return serial
    preferred = []
    fallback = []
    for item in getattr(system_info, "otherIdentifyingInfo", []) or []:
        value = clean(getattr(item, "identifierValue", ""))
        itype = getattr(item, "identifierType", None)
        key = clean(getattr(itype, "key", "")).lower()
        label = clean(getattr(itype, "label", "")).lower()
        if not value:
            continue
        if "service" in key or "serial" in key or "service" in label or "serial" in label:
            preferred.append(value)
        else:
            fallback.append(value)
    return (preferred or fallback or [""])[0]


def _vmware_management_devices(host):
    selected = set()
    try:
        manager = getattr(getattr(host, "configManager", None), "virtualNicManager", None)
        if manager:
            cfg = manager.QueryNetConfig("management")
            for device in getattr(cfg, "selectedVnic", []) or []:
                selected.add(clean(device))
    except Exception:
        pass
    return selected


def _vmware_host_interfaces(host):
    selected = _vmware_management_devices(host)
    rows = []
    try:
        network = getattr(getattr(host, "config", None), "network", None)
        for vnic in getattr(network, "vnic", []) or []:
            device = clean(getattr(vnic, "device", "")) or "vmk"
            spec = getattr(vnic, "spec", None)
            ip_spec = getattr(spec, "ip", None)
            ip = valid_ip(getattr(ip_spec, "ipAddress", ""))
            prefix = mask_to_prefix(getattr(ip_spec, "subnetMask", ""))
            mac = norm_mac(getattr(spec, "mac", ""))
            primary = device in selected or (not selected and device == "vmk0")
            ips = []
            if ip:
                rec = normalize_ip_record(ip, prefix, primary)
                if rec:
                    ips.append(rec)
            rows.append({
                "name": device,
                "mac": mac,
                "network": "",
                "ips": ips,
                "management": bool(primary),
            })
    except Exception:
        pass
    return rows


def _vmware_vm_interfaces(vm, vim):
    by_mac = {}
    rows = []
    try:
        devices = getattr(getattr(vm, "config", None), "hardware", None)
        devices = getattr(devices, "device", []) or []
        for dev in devices:
            if not isinstance(dev, vim.vm.device.VirtualEthernetCard):
                continue
            mac = norm_mac(getattr(dev, "macAddress", ""))
            label = clean(getattr(getattr(dev, "deviceInfo", None), "label", "")) or "nic"
            network = ""
            backing = getattr(dev, "backing", None)
            network = clean(getattr(backing, "deviceName", ""))
            row = {"name": label, "mac": mac, "network": network, "ips": [], "management": False}
            rows.append(row)
            if mac:
                by_mac[mac] = row
    except Exception:
        pass

    try:
        guest_nets = getattr(getattr(vm, "guest", None), "net", []) or []
        for idx, gnet in enumerate(guest_nets):
            mac = norm_mac(getattr(gnet, "macAddress", ""))
            row = by_mac.get(mac)
            if row is None:
                row = {
                    "name": "nic{0}".format(idx),
                    "mac": mac,
                    "network": clean(getattr(gnet, "network", "")),
                    "ips": [],
                    "management": False,
                }
                rows.append(row)
                if mac:
                    by_mac[mac] = row
            if not row.get("network"):
                row["network"] = clean(getattr(gnet, "network", ""))
            ip_cfg = getattr(gnet, "ipConfig", None)
            for ip_obj in getattr(ip_cfg, "ipAddress", []) or []:
                rec = normalize_ip_record(
                    getattr(ip_obj, "ipAddress", ""),
                    getattr(ip_obj, "prefixLength", None),
                    False,
                )
                if rec and rec not in row["ips"]:
                    row["ips"].append(rec)
    except Exception:
        pass

    fallback = valid_ip(getattr(getattr(vm, "guest", None), "ipAddress", ""))
    if fallback and rows:
        found = False
        for row in rows:
            for iprow in row.get("ips", []):
                if fallback == iprow.get("address"):
                    iprow["primary"] = True
                    found = True
                    break
            if found:
                break
        if not found:
            rec = normalize_ip_record(fallback, None, True)
            if rec:
                rows[0]["ips"].append(rec)
    return rows


def _vmware_vm_disk_gb(vm, vim):
    total_kb = 0
    try:
        hw = getattr(getattr(vm, "config", None), "hardware", None)
        for dev in getattr(hw, "device", []) or []:
            if isinstance(dev, vim.vm.device.VirtualDisk):
                total_kb += safe_int(getattr(dev, "capacityInKB", 0), 0)
    except Exception:
        return 0
    return round(float(total_kb) / 1024.0 / 1024.0, 2)


def check_vmware(source):
    si, disconnect = _vmware_connect(source)
    try:
        content = si.RetrieveContent()
        about = content.about
        return {
            "ok": True,
            "provider": "vmware",
            "product": clean(getattr(about, "fullName", "")),
            "version": clean(getattr(about, "version", "")),
            "endpoint": clean(source.get("endpoint")),
        }
    finally:
        disconnect(si)


def collect_vmware(source):
    try:
        from pyVmomi import vim
    except Exception as exc:
        raise RuntimeError("pyVmomi indisponível: {0}".format(exc))
    si, disconnect = _vmware_connect(source)
    try:
        content = si.RetrieveContent()
        about = content.about
        hosts = []
        vms = []
        clusters = {}

        for host in _vmware_list(content, vim.HostSystem):
            summary = getattr(host, "summary", None)
            hardware = getattr(summary, "hardware", None)
            config = getattr(summary, "config", None)
            runtime = getattr(summary, "runtime", None)
            system_info = getattr(getattr(host, "hardware", None), "systemInfo", None)
            cluster = _vmware_cluster(host, vim)
            datacenter = _vmware_datacenter(host, vim)
            if cluster:
                clusters[(datacenter, cluster)] = {
                    "name": cluster,
                    "datacenter": datacenter,
                    "provider": "vmware",
                }
            product = getattr(config, "product", None)
            interfaces = _vmware_host_interfaces(host)
            hosts.append({
                "provider": "vmware",
                "source_id": source.get("id"),
                "name": clean(getattr(config, "name", "")) or clean(getattr(host, "name", "")),
                "serial": _vmware_host_serial(host),
                "uuid": clean(getattr(system_info, "uuid", "")),
                "manufacturer": clean(getattr(hardware, "vendor", "")) or "Generic",
                "model": clean(getattr(hardware, "model", "")) or "VMware ESXi Host",
                "platform": "VMware ESXi",
                "platform_version": clean(getattr(product, "version", "")),
                "platform_build": clean(getattr(product, "build", "")),
                "datacenter": datacenter,
                "cluster": cluster,
                "status": clean(getattr(runtime, "connectionState", "")),
                "maintenance": bool(getattr(runtime, "inMaintenanceMode", False)),
                "cpu_count": safe_int(getattr(hardware, "numCpuCores", 0), 0),
                "memory_mb": int(safe_float(getattr(hardware, "memorySize", 0), 0.0) / 1024.0 / 1024.0),
                "interfaces": interfaces,
            })

        for vm in _vmware_list(content, vim.VirtualMachine):
            cfg = getattr(vm, "config", None)
            if bool(getattr(cfg, "template", False)):
                continue
            runtime = getattr(vm, "runtime", None)
            host = getattr(runtime, "host", None)
            cluster = _vmware_cluster(host, vim) if host else ""
            datacenter = _vmware_datacenter(host or vm, vim)
            guest = getattr(vm, "guest", None)
            hardware = getattr(cfg, "hardware", None)
            uuid = clean(getattr(cfg, "instanceUuid", "")) or clean(getattr(cfg, "uuid", ""))
            stable_serial = uuid
            vms.append({
                "provider": "vmware",
                "source_id": source.get("id"),
                "kind": "vm",
                "name": clean(getattr(vm, "name", "")),
                "serial": stable_serial,
                "uuid": uuid,
                "host_name": clean(getattr(host, "name", "")) if host else "",
                "cluster": cluster,
                "datacenter": datacenter,
                "status": clean(getattr(runtime, "powerState", "")),
                "platform": clean(getattr(guest, "guestFullName", "")) or clean(getattr(cfg, "guestFullName", "")),
                "vcpus": safe_float(getattr(hardware, "numCPU", 0), 0.0),
                "memory_mb": safe_int(getattr(hardware, "memoryMB", 0), 0),
                "disk_gb": _vmware_vm_disk_gb(vm, vim),
                "interfaces": _vmware_vm_interfaces(vm, vim),
            })

        return {
            "stage": "HYPERVISOR_DISCOVERY",
            "collector_version": COLLECTOR_VERSION,
            "generated_at": utc_now(),
            "provider": "vmware",
            "source_id": source.get("id"),
            "endpoint": clean(source.get("endpoint")),
            "manager": {
                "product": clean(getattr(about, "fullName", "")),
                "version": clean(getattr(about, "version", "")),
            },
            "clusters": list(clusters.values()),
            "hosts": hosts,
            "vms": vms,
            "errors": [],
            "netbox_write": False,
        }
    finally:
        disconnect(si)


class ProxmoxClient(object):
    def __init__(self, source):
        self.source = source
        endpoint = clean(source.get("endpoint"))
        if "://" in endpoint:
            parsed = urllib.parse.urlparse(endpoint)
            scheme = parsed.scheme or "https"
            host = parsed.hostname or endpoint
            port = parsed.port or safe_int(source.get("port"), 8006) or 8006
        else:
            scheme = clean(source.get("scheme") or "https")
            host = endpoint_host(endpoint)
            port = safe_int(source.get("port"), 8006) or 8006
        self.base = "{0}://{1}:{2}/api2/json".format(scheme, host, port)
        self.verify_ssl = bool(source.get("verify_ssl", False))
        self.context = ssl.create_default_context() if self.verify_ssl else ssl._create_unverified_context()
        self.headers = {"Accept": "application/json"}
        auth = clean(source.get("auth") or "token").lower()
        if auth == "token":
            self.headers["Authorization"] = "PVEAPIToken={0}!{1}={2}".format(
                source.get("username"), source.get("token_id"), source.get("secret")
            )
        else:
            payload = urllib.parse.urlencode({
                "username": source.get("username"),
                "password": source.get("secret"),
            }).encode("utf-8")
            data = self._request("POST", "/access/ticket", payload, {"Content-Type": "application/x-www-form-urlencoded"})
            ticket = clean(data.get("ticket"))
            csrf = clean(data.get("CSRFPreventionToken"))
            if not ticket:
                raise RuntimeError("Proxmox não retornou ticket de autenticação")
            self.headers["Cookie"] = "PVEAuthCookie={0}".format(ticket)
            if csrf:
                self.headers["CSRFPreventionToken"] = csrf

    def _request(self, method, path, body=None, extra_headers=None, allow_error=False):
        url = self.base + "/" + path.lstrip("/")
        headers = dict(self.headers)
        headers.update(extra_headers or {})
        req = urllib.request.Request(url=url, data=body, headers=headers)
        req.get_method = lambda: method
        try:
            response = urllib.request.urlopen(req, context=self.context, timeout=60)
            raw = response.read().decode("utf-8", errors="replace")
            parsed = json.loads(raw) if raw else {}
            if isinstance(parsed, dict) and "data" in parsed:
                return parsed.get("data")
            return parsed
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            if allow_error:
                return None
            raise RuntimeError("Proxmox HTTP {0} em {1}: {2}".format(exc.code, url, raw[:500]))
        except urllib.error.URLError as exc:
            if allow_error:
                return None
            raise RuntimeError("Erro de conexão Proxmox {0}: {1}".format(url, exc))

    def get(self, path, allow_error=False):
        return self._request("GET", path, allow_error=allow_error)


def _parse_kv_string(value):
    out = {}
    parts = [x.strip() for x in clean(value).split(",") if x.strip()]
    for pos, part in enumerate(parts):
        if "=" in part:
            key, val = part.split("=", 1)
            out[key.strip()] = val.strip()
        elif pos == 0:
            out["value"] = part
    return out


def _parse_qemu_net(name, value, ipconfig_value=""):
    cfg = _parse_kv_string(value)
    mac = ""
    for key, val in cfg.items():
        candidate = norm_mac(val)
        if candidate:
            mac = candidate
            break
    row = {
        "name": name,
        "mac": mac,
        "network": clean(cfg.get("bridge")),
        "ips": [],
        "management": False,
    }
    ipcfg = _parse_kv_string(ipconfig_value)
    raw_ip = clean(ipcfg.get("ip"))
    if raw_ip and raw_ip.lower() not in ("dhcp", "manual"):
        try:
            iface = ipaddress.ip_interface(raw_ip)
            rec = normalize_ip_record(str(iface.ip), iface.network.prefixlen, False)
            if rec:
                row["ips"].append(rec)
        except Exception:
            pass
    return row


def _parse_lxc_net(name, value):
    cfg = _parse_kv_string(value)
    row = {
        "name": clean(cfg.get("name")) or name,
        "mac": norm_mac(cfg.get("hwaddr")),
        "network": clean(cfg.get("bridge")),
        "ips": [],
        "management": False,
    }
    raw_ip = clean(cfg.get("ip"))
    if raw_ip and raw_ip.lower() not in ("dhcp", "manual"):
        try:
            iface = ipaddress.ip_interface(raw_ip)
            rec = normalize_ip_record(str(iface.ip), iface.network.prefixlen, False)
            if rec:
                row["ips"].append(rec)
        except Exception:
            pass
    return row


def _qemu_agent_interfaces(client, node, vmid):
    data = client.get("/nodes/{0}/qemu/{1}/agent/network-get-interfaces".format(node, vmid), allow_error=True)
    if not isinstance(data, dict):
        return []
    result = data.get("result") or []
    rows = []
    for idx, item in enumerate(result):
        mac = norm_mac(item.get("hardware-address"))
        ips = []
        for iprow in item.get("ip-addresses") or []:
            rec = normalize_ip_record(iprow.get("ip-address"), iprow.get("prefix"), False)
            if rec:
                ips.append(rec)
        rows.append({
            "name": clean(item.get("name")) or "nic{0}".format(idx),
            "mac": mac,
            "network": "",
            "ips": ips,
            "management": False,
        })
    return rows


def _merge_interface_ips(base_rows, extra_rows):
    by_mac = dict((r.get("mac"), r) for r in base_rows if r.get("mac"))
    for extra in extra_rows:
        target = by_mac.get(extra.get("mac"))
        if target is None:
            base_rows.append(extra)
            continue
        for iprow in extra.get("ips") or []:
            if not any(x.get("address") == iprow.get("address") for x in target.get("ips") or []):
                target.setdefault("ips", []).append(iprow)
    return base_rows


def _proxmox_uuid(config):
    smbios = _parse_kv_string(config.get("smbios1", ""))
    return clean(smbios.get("uuid")) or clean(config.get("vmgenid"))


def _proxmox_stable_serial(source_id, vmid, uuid=""):
    uuid = clean(uuid)
    if uuid:
        return uuid
    digest = hashlib.sha1(clean(source_id).encode("utf-8")).hexdigest()[:12]
    return "PVE-{0}-{1}".format(digest, safe_int(vmid, 0))


def check_proxmox(source):
    client = ProxmoxClient(source)
    version = client.get("/version") or {}
    return {
        "ok": True,
        "provider": "proxmox",
        "product": "Proxmox VE",
        "version": clean(version.get("version")) or clean(version.get("release")),
        "endpoint": clean(source.get("endpoint")),
    }


def collect_proxmox(source):
    client = ProxmoxClient(source)
    version = client.get("/version") or {}
    cluster_status = client.get("/cluster/status", allow_error=True) or []
    cluster_name = ""
    node_ip = {}
    for row in cluster_status:
        if clean(row.get("type")) == "cluster":
            cluster_name = clean(row.get("name"))
        elif clean(row.get("type")) == "node":
            node_ip[clean(row.get("name"))] = valid_ip(row.get("ip"))

    clusters = []
    if cluster_name:
        clusters.append({"name": cluster_name, "datacenter": "", "provider": "proxmox"})

    hosts = []
    vms = []
    nodes = client.get("/nodes") or []
    for nrow in nodes:
        node = clean(nrow.get("node"))
        if not node:
            continue
        status = client.get("/nodes/{0}/status".format(urllib.parse.quote(node, safe="")), allow_error=True) or {}
        cpuinfo = status.get("cpuinfo") or {}
        memory = status.get("memory") or {}
        management_ip = node_ip.get(node, "")
        if not management_ip and len(nodes) == 1:
            management_ip = valid_ip(endpoint_host(source.get("endpoint")))
        interfaces = []
        if management_ip:
            rec = normalize_ip_record(management_ip, None, True)
            interfaces.append({
                "name": "management",
                "mac": "",
                "network": "",
                "ips": [rec] if rec else [],
                "management": True,
            })
        hosts.append({
            "provider": "proxmox",
            "source_id": source.get("id"),
            "name": node,
            "serial": "",
            "uuid": clean(status.get("id")),
            "manufacturer": "Generic",
            "model": "Proxmox VE Node",
            "platform": "Proxmox VE",
            "platform_version": clean(version.get("version")) or clean(status.get("pveversion")),
            "platform_build": "",
            "datacenter": "",
            "cluster": cluster_name,
            "status": clean(nrow.get("status")),
            "maintenance": False,
            "cpu_count": safe_int(nrow.get("maxcpu") or status.get("cpuinfo", {}).get("cpus"), 0),
            "memory_mb": int(safe_float(nrow.get("maxmem") or memory.get("total"), 0.0) / 1024.0 / 1024.0),
            "interfaces": interfaces,
        })

        qemu_rows = client.get("/nodes/{0}/qemu".format(urllib.parse.quote(node, safe="")), allow_error=True) or []
        for vmrow in qemu_rows:
            vmid = safe_int(vmrow.get("vmid"), 0)
            if not vmid:
                continue
            cfg = client.get("/nodes/{0}/qemu/{1}/config".format(urllib.parse.quote(node, safe=""), vmid), allow_error=True) or {}
            interfaces = []
            for key in sorted(cfg.keys()):
                if re.match(r"^net\d+$", key):
                    idx = key[3:]
                    interfaces.append(_parse_qemu_net(key, cfg.get(key), cfg.get("ipconfig{0}".format(idx), "")))
            agent_rows = _qemu_agent_interfaces(client, node, vmid)
            interfaces = _merge_interface_ips(interfaces, agent_rows)
            mem_mb = safe_int(cfg.get("memory") or int(safe_float(vmrow.get("maxmem"), 0) / 1024.0 / 1024.0), 0)
            vcpus = safe_float(vmrow.get("cpus") or (safe_int(cfg.get("cores"), 1) * safe_int(cfg.get("sockets"), 1)), 0.0)
            disk_gb = round(safe_float(vmrow.get("maxdisk"), 0.0) / 1024.0 / 1024.0 / 1024.0, 2)
            uuid = _proxmox_uuid(cfg)
            stable_serial = _proxmox_stable_serial(source.get("id"), vmid, uuid)
            vms.append({
                "provider": "proxmox",
                "source_id": source.get("id"),
                "kind": "vm",
                "name": clean(cfg.get("name")) or clean(vmrow.get("name")) or "VM-{0}".format(vmid),
                "serial": stable_serial,
                "uuid": uuid,
                "host_name": node,
                "cluster": cluster_name,
                "datacenter": "",
                "status": clean(vmrow.get("status")),
                "platform": clean(cfg.get("ostype")),
                "vcpus": vcpus,
                "memory_mb": mem_mb,
                "disk_gb": disk_gb,
                "interfaces": interfaces,
                "provider_id": str(vmid),
            })

        lxc_rows = client.get("/nodes/{0}/lxc".format(urllib.parse.quote(node, safe="")), allow_error=True) or []
        for vmrow in lxc_rows:
            vmid = safe_int(vmrow.get("vmid"), 0)
            if not vmid:
                continue
            cfg = client.get("/nodes/{0}/lxc/{1}/config".format(urllib.parse.quote(node, safe=""), vmid), allow_error=True) or {}
            interfaces = []
            for key in sorted(cfg.keys()):
                if re.match(r"^net\d+$", key):
                    interfaces.append(_parse_lxc_net(key, cfg.get(key)))
            interfaces = _merge_interface_ips(interfaces, [])
            disk_gb = round(safe_float(vmrow.get("maxdisk"), 0.0) / 1024.0 / 1024.0 / 1024.0, 2)
            vms.append({
                "provider": "proxmox",
                "source_id": source.get("id"),
                "kind": "container",
                "name": clean(cfg.get("hostname")) or clean(vmrow.get("name")) or "LXC-{0}".format(vmid),
                "serial": _proxmox_stable_serial(source.get("id"), vmid),
                "uuid": "",
                "host_name": node,
                "cluster": cluster_name,
                "datacenter": "",
                "status": clean(vmrow.get("status")),
                "platform": clean(cfg.get("ostype")) or "Linux",
                "vcpus": safe_float(vmrow.get("cpus") or cfg.get("cores"), 0.0),
                "memory_mb": safe_int(cfg.get("memory") or int(safe_float(vmrow.get("maxmem"), 0) / 1024.0 / 1024.0), 0),
                "disk_gb": disk_gb,
                "interfaces": interfaces,
                "provider_id": str(vmid),
            })

    return {
        "stage": "HYPERVISOR_DISCOVERY",
        "collector_version": COLLECTOR_VERSION,
        "generated_at": utc_now(),
        "provider": "proxmox",
        "source_id": source.get("id"),
        "endpoint": clean(source.get("endpoint")),
        "manager": {"product": "Proxmox VE", "version": clean(version.get("version"))},
        "clusters": clusters,
        "hosts": hosts,
        "vms": vms,
        "errors": [],
        "netbox_write": False,
    }


_HYPERV_POWERSHELL = r'''$ErrorActionPreference = "Stop"
$cs = Get-CimInstance Win32_ComputerSystem
$bios = Get-CimInstance Win32_BIOS
$csp = Get-CimInstance Win32_ComputerSystemProduct
$os = Get-CimInstance Win32_OperatingSystem
$clusterName = ""
try {
  if (Get-Command Get-Cluster -ErrorAction SilentlyContinue) {
    $clusterName = (Get-Cluster -ErrorAction Stop).Name
  }
} catch { $clusterName = "" }
$hostIfs = @()
try {
  foreach ($ipcfg in (Get-NetIPConfiguration -ErrorAction Stop)) {
    $adapter = Get-NetAdapter -InterfaceIndex $ipcfg.InterfaceIndex -ErrorAction SilentlyContinue
    foreach ($addr in @($ipcfg.IPv4Address)) {
      if ($null -ne $addr -and $addr.IPAddress -and $addr.IPAddress -notlike '169.254.*' -and $addr.IPAddress -ne '127.0.0.1') {
        $hostIfs += [pscustomobject]@{
          Name = if ($adapter) { $adapter.Name } else { "mgmt" }
          Mac = if ($adapter) { $adapter.MacAddress } else { "" }
          Address = $addr.IPAddress
          PrefixLength = $addr.PrefixLength
        }
      }
    }
  }
} catch {}
$vms = @()
foreach ($vm in @(Get-VM -ErrorAction Stop)) {
  $nics = @()
  try {
    foreach ($nic in @(Get-VMNetworkAdapter -VM $vm -ErrorAction Stop)) {
      $nics += [pscustomobject]@{
        Name = $nic.Name
        Mac = $nic.MacAddress
        SwitchName = $nic.SwitchName
        IPAddresses = @($nic.IPAddresses)
      }
    }
  } catch {}
  $diskBytes = [int64]0
  try {
    foreach ($drive in @(Get-VMHardDiskDrive -VM $vm -ErrorAction SilentlyContinue)) {
      if ($drive.Path) {
        try { $diskBytes += [int64](Get-VHD -Path $drive.Path -ErrorAction Stop).Size } catch {}
      }
    }
  } catch {}
  $vms += [pscustomobject]@{
    Name = $vm.Name
    Id = $vm.Id.Guid
    State = $vm.State.ToString()
    ProcessorCount = $vm.ProcessorCount
    MemoryMB = [int64]([math]::Round(([double]$vm.MemoryStartup / 1MB), 0))
    DiskBytes = $diskBytes
    Version = $vm.Version.ToString()
    Nics = $nics
  }
}
[pscustomobject]@{
  Host = [pscustomobject]@{
    Name = $env:COMPUTERNAME
    Manufacturer = $cs.Manufacturer
    Model = $cs.Model
    Serial = $bios.SerialNumber
    UUID = $csp.UUID
    OS = $os.Caption
    Version = $os.Version
    Cluster = $clusterName
    CPUCount = $cs.NumberOfLogicalProcessors
    MemoryMB = [int64]([math]::Round(([double]$cs.TotalPhysicalMemory / 1MB), 0))
    Interfaces = $hostIfs
  }
  VMs = $vms
} | ConvertTo-Json -Depth 8 -Compress
'''


def _hyperv_session(source):
    try:
        import winrm
    except Exception as exc:
        raise RuntimeError("pywinrm indisponível ({0}). Reinstale/atualize o produto.".format(exc))
    endpoint = clean(source.get("endpoint"))
    if "://" in endpoint:
        url = endpoint.rstrip("/")
    else:
        scheme = clean(source.get("scheme") or ("https" if safe_int(source.get("port"), 5986) == 5986 else "http"))
        port = safe_int(source.get("port"), 5986 if scheme == "https" else 5985)
        url = "{0}://{1}:{2}/wsman".format(scheme, endpoint_host(endpoint), port)
    validation = "validate" if bool(source.get("verify_ssl", False)) else "ignore"
    return winrm.Session(
        url,
        auth=(source.get("username"), source.get("secret")),
        transport=clean(source.get("transport") or "ntlm"),
        server_cert_validation=validation,
        read_timeout_sec=90,
        operation_timeout_sec=60,
    )


def _hyperv_json_output(result):
    if result.status_code != 0:
        err = result.std_err.decode("utf-8", errors="replace") if isinstance(result.std_err, bytes) else clean(result.std_err)
        raise RuntimeError("Hyper-V WinRM/PowerShell falhou: {0}".format(err[:1000]))
    out = result.std_out.decode("utf-8", errors="replace") if isinstance(result.std_out, bytes) else clean(result.std_out)
    out = out.strip()
    start = out.find("{")
    end = out.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError("Hyper-V não retornou JSON válido")
    return json.loads(out[start:end + 1])


def check_hyperv(source):
    session = _hyperv_session(source)
    result = session.run_ps('[pscustomobject]@{Name=$env:COMPUTERNAME;Version=(Get-CimInstance Win32_OperatingSystem).Version}|ConvertTo-Json -Compress')
    data = _hyperv_json_output(result)
    return {
        "ok": True,
        "provider": "hyperv",
        "product": "Microsoft Hyper-V",
        "version": clean(data.get("Version")),
        "host": clean(data.get("Name")),
        "endpoint": clean(source.get("endpoint")),
    }


def collect_hyperv(source):
    session = _hyperv_session(source)
    data = _hyperv_json_output(session.run_ps(_HYPERV_POWERSHELL))
    h = data.get("Host") or {}
    cluster = clean(h.get("Cluster"))
    host_ifs = []
    raw_ifs = h.get("Interfaces") or []
    if isinstance(raw_ifs, dict):
        raw_ifs = [raw_ifs]
    endpoint_ip = valid_ip(endpoint_host(source.get("endpoint")))
    for idx, row in enumerate(raw_ifs):
        row_ip = valid_ip(row.get("Address"))
        is_management = bool(endpoint_ip and row_ip == endpoint_ip)
        rec = normalize_ip_record(row_ip, row.get("PrefixLength"), is_management)
        host_ifs.append({
            "name": clean(row.get("Name")) or "mgmt{0}".format(idx),
            "mac": norm_mac(row.get("Mac")),
            "network": "",
            "ips": [rec] if rec else [],
            "management": is_management,
        })
    host_name = clean(h.get("Name")) or endpoint_host(source.get("endpoint"))
    hosts = [{
        "provider": "hyperv",
        "source_id": source.get("id"),
        "name": host_name,
        "serial": clean(h.get("Serial")),
        "uuid": clean(h.get("UUID")),
        "manufacturer": clean(h.get("Manufacturer")) or "Generic",
        "model": clean(h.get("Model")) or "Microsoft Hyper-V Host",
        "platform": "Microsoft Hyper-V",
        "platform_version": clean(h.get("Version")),
        "platform_build": "",
        "datacenter": "",
        "cluster": cluster,
        "status": "online",
        "maintenance": False,
        "cpu_count": safe_int(h.get("CPUCount"), 0),
        "memory_mb": safe_int(h.get("MemoryMB"), 0),
        "interfaces": host_ifs,
    }]

    vms = []
    raw_vms = data.get("VMs") or []
    if isinstance(raw_vms, dict):
        raw_vms = [raw_vms]
    for vm in raw_vms:
        ifs = []
        raw_nics = vm.get("Nics") or []
        if isinstance(raw_nics, dict):
            raw_nics = [raw_nics]
        for idx, nic in enumerate(raw_nics):
            ips = []
            raw_ips = nic.get("IPAddresses") or []
            if isinstance(raw_ips, str):
                raw_ips = [raw_ips]
            for raw_ip in raw_ips:
                rec = normalize_ip_record(raw_ip, None, False)
                if rec:
                    ips.append(rec)
            ifs.append({
                "name": clean(nic.get("Name")) or "nic{0}".format(idx),
                "mac": norm_mac(nic.get("Mac")),
                "network": clean(nic.get("SwitchName")),
                "ips": ips,
                "management": False,
            })
        uuid = clean(vm.get("Id"))
        vms.append({
            "provider": "hyperv",
            "source_id": source.get("id"),
            "kind": "vm",
            "name": clean(vm.get("Name")),
            "serial": uuid,
            "uuid": uuid,
            "host_name": host_name,
            "cluster": cluster,
            "datacenter": "",
            "status": clean(vm.get("State")),
            "platform": "",
            "vcpus": safe_float(vm.get("ProcessorCount"), 0.0),
            "memory_mb": safe_int(vm.get("MemoryMB"), 0),
            "disk_gb": round(safe_float(vm.get("DiskBytes"), 0.0) / 1024.0 / 1024.0 / 1024.0, 2),
            "interfaces": ifs,
        })

    clusters = []
    if cluster:
        clusters.append({"name": cluster, "datacenter": "", "provider": "hyperv"})
    return {
        "stage": "HYPERVISOR_DISCOVERY",
        "collector_version": COLLECTOR_VERSION,
        "generated_at": utc_now(),
        "provider": "hyperv",
        "source_id": source.get("id"),
        "endpoint": clean(source.get("endpoint")),
        "manager": {"product": "Microsoft Hyper-V", "version": clean(h.get("Version"))},
        "clusters": clusters,
        "hosts": hosts,
        "vms": vms,
        "errors": [],
        "netbox_write": False,
    }


def check_source(source):
    stype = clean(source.get("type")).lower()
    if stype == "vmware":
        return check_vmware(source)
    if stype == "proxmox":
        return check_proxmox(source)
    if stype == "hyperv":
        return check_hyperv(source)
    raise RuntimeError("Tipo não suportado: {0}".format(stype))


def collect_source(source):
    stype = clean(source.get("type")).lower()
    if stype == "vmware":
        return collect_vmware(source)
    if stype == "proxmox":
        return collect_proxmox(source)
    if stype == "hyperv":
        return collect_hyperv(source)
    raise RuntimeError("Tipo não suportado: {0}".format(stype))
