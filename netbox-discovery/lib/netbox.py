#!/usr/bin/env python3

import json
import ssl
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

    def request(self, method, endpoint, data=None):
        url = self._url(endpoint)

        headers = {
            "Authorization": "Token " + self.token,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        payload = None
        if data is not None:
            payload = json.dumps(data).encode("utf-8")

        request = urllib.request.Request(
            url=url,
            data=payload,
            headers=headers,
            method=method,
        )

        try:
            response = urllib.request.urlopen(
                request,
                context=self.ssl_context,
                timeout=60,
            )

            body = response.read().decode("utf-8")

            if not body:
                return None

            return json.loads(body)

        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            raise NetBoxError(
                "HTTP %s em %s: %s" % (error.code, url, body)
            )

        except urllib.error.URLError as error:
            raise NetBoxError(
                "Erro de conexão com %s: %s" % (url, error)
            )

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
