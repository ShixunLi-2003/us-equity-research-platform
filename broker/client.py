"""Alpaca REST boundary. Credentials stay in memory; only paper trading is allowed."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field
import os
import json
from pathlib import Path
import threading
import time

from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

PAPER_URL = "https://paper-api.alpaca.markets"
DATA_URL = "https://data.alpaca.markets"


class BridgeError(RuntimeError):
    pass


class APIError(BridgeError):
    def __init__(self, status, service, path):
        self.status = int(status)
        super().__init__("{} {} HTTP {}".format(service, path, status))


@dataclass(repr=False)
class Credentials:
    key: str = field(repr=False)
    secret: str = field(repr=False)


def decrypt_dpapi(path):
    if os.name != "nt":
        raise BridgeError("DPAPI requires the Windows user who saved the credentials")
    raw = Path(path).read_text(encoding="utf-8-sig").strip()
    try:
        blob = bytes.fromhex(raw)
    except ValueError:
        raise BridgeError("Invalid DPAPI file format") from None

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
    source = Blob(len(blob), buffer)
    target = Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt.CryptUnprotectData.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(Blob)]
    crypt.CryptUnprotectData.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if not crypt.CryptUnprotectData(ctypes.byref(source), None, None, None, None,
                                   1, ctypes.byref(target)):
        raise BridgeError("DPAPI decrypt failed: run as the Windows user who saved the keys")
    try:
        return ctypes.string_at(target.data, target.size).decode("utf-16-le")
    finally:
        ctypes.memset(target.data, 0, target.size)
        kernel.LocalFree(target.data)


def load_credentials(directory=None):
    base = os.environ.get("APCA_API_BASE_URL", PAPER_URL).rstrip("/")
    if base != PAPER_URL:
        raise BridgeError("Live or custom trading endpoint refused; paper endpoint required")
    key, secret = os.environ.get("APCA_API_KEY_ID"), os.environ.get("APCA_API_SECRET_KEY")
    if bool(key) != bool(secret):
        raise BridgeError("Both environment credentials must be set together")
    if not key:
        root = Path(directory) if directory else Path(os.environ["APPDATA"]) / "US500" / "Alpaca"
        key = decrypt_dpapi(root / "key.dpapi")
        secret = decrypt_dpapi(root / "secret.dpapi")
    if not key or not secret:
        raise BridgeError("Empty credentials")
    return Credentials(key.strip(), secret.strip())


class RateLimiter:
    def __init__(self, rpm=150):
        self.interval = 60.0 / rpm
        self.next_at = 0.0
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            delay = max(0.0, self.next_at - time.monotonic())
            self.next_at = max(self.next_at, time.monotonic()) + self.interval
        if delay:
            time.sleep(delay)


class AlpacaClient:
    def __init__(self, credentials=None, limiter=None):
        credentials = credentials or load_credentials()
        self.headers = {"APCA-API-KEY-ID": credentials.key,
                        "APCA-API-SECRET-KEY": credentials.secret}
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        self.opener = build_opener(NoRedirect())
        self.limiter = limiter or RateLimiter()

    def get(self, path, params=None, data=False):
        if (not path.startswith("/v2/") and not (data and path == "/v1/corporate-actions")) or "?" in path or ".." in path:
            raise BridgeError("Invalid API path")
        base = DATA_URL if data else PAPER_URL
        for attempt in range(5):
            self.limiter.wait()
            try:
                url = base + path + (("?" + urlencode(params)) if params else "")
                with self.opener.open(Request(url, headers=self.headers), timeout=90) as response:
                    return json.load(response)
            except HTTPError as exc:
                status, headers = exc.code, exc.headers
                exc.close()
            except (URLError, TimeoutError, OSError):
                if attempt == 4:
                    raise BridgeError("Alpaca network request failed after retries") from None
                time.sleep(min(2 ** attempt, 8))
                continue
            except ValueError:
                raise BridgeError("Alpaca returned invalid JSON") from None
            if status == 429 or status >= 500:
                if attempt < 4:
                    try:
                        delay = float(headers.get("Retry-After", 2 ** attempt))
                    except ValueError:
                        delay = 2 ** attempt
                    time.sleep(min(max(delay, 1), 30))
                    continue
            raise APIError(status, "data" if data else "paper", path)
        raise BridgeError("Alpaca request retries exhausted")

    def bars(self, symbols, start, end, timeframe="1Min", feed="sip", adjustment="raw", asof="-"):
        if feed not in {"sip", "iex"} or adjustment not in {"raw", "split", "all"}:
            raise BridgeError("Unsupported feed or adjustment")
        params = {"symbols": ",".join(symbols), "start": start, "end": end,
                  "timeframe": timeframe, "feed": feed, "adjustment": adjustment,
                  "limit": 10000, "sort": "asc", "asof": asof}
        seen = set()
        while True:
            payload = self.get("/v2/stocks/bars", params, data=True)
            yield payload.get("bars") or {}
            token = payload.get("next_page_token")
            if not token:
                break
            if token in seen:
                raise BridgeError("Repeated pagination token")
            seen.add(token)
            params["page_token"] = token
