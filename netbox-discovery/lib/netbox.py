#!/usr/bin/env python3

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

from lib.config import load_config


class NetBoxError(Exception):
    pass


class NetBox:
    def __init__(self, config_file="/opt/netbox-discovery/config.yml"):
        config = load_config(config_file)
        netbox = config["netbox"]

        self.base_url = netbox["url"].rstrip("/") + "/api"
        self.token = netbox["token"]
        self.verify_ssl = netbox["verify_ssl"]

        if self.verify_ssl:
            self.ssl_context = ssl.create_default_context()
        else:
            self.ssl_context = ssl._create_unverified_context()

    def _url(self, endpoint):
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            return endpoint
        return self.base_url + "/" + endpoint.lstrip("/")

    def _request_once(self, method, endpoint, data=None):
        url = self._url(endpoint)
        headers = {
            "Authorization": "Token " + self.token,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        payload = json.dumps(data).encode("utf-8") if data is not None else None
        request = urllib.request.Request(url=url, data=payload, headers=headers, method=method)
        response = urllib.request.urlopen(request, context=self.ssl_context, timeout=60)
        body = response.read().decode("utf-8")
        if not body:
            return None
        return json.loads(body)

    def request(self, method, endpoint, data=None):
        url = self._url(endpoint)
        attempts = 3 if method.upper() == "GET" else 1
        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                return self._request_once(method, endpoint, data)
            except urllib.error.HTTPError as error:
                body = error.read().decode("utf-8", errors="replace")
                last_error = NetBoxError("HTTP %s em %s: %s" % (error.code, url, body))
                retryable = method.upper() == "GET" and error.code in (429, 502, 503, 504)
                if not retryable or attempt >= attempts:
                    raise last_error
            except urllib.error.URLError as error:
                last_error = NetBoxError("Erro de conexão com %s: %s" % (url, error))
                if method.upper() != "GET" or attempt >= attempts:
                    raise last_error
            except TimeoutError as error:
                last_error = NetBoxError("Timeout em %s: %s" % (url, error))
                if method.upper() != "GET" or attempt >= attempts:
                    raise last_error
            if attempt < attempts:
                time.sleep(attempt)
        raise last_error or NetBoxError("Falha inesperada em %s" % url)

    def get(self, endpoint):
        return self.request("GET", endpoint)

    def post(self, endpoint, data):
        return self.request("POST", endpoint, data)

    def patch(self, endpoint, data):
        return self.request("PATCH", endpoint, data)

    def delete(self, endpoint):
        return self.request("DELETE", endpoint)

    def get_all(self, endpoint):
        results = []
        url = endpoint
        while url:
            response = self.get(url)
            if not isinstance(response, dict):
                raise NetBoxError("Resposta inválida da API.")
            if "results" not in response:
                return response
            results.extend(response["results"])
            url = response.get("next")
        return results
