"""The blueconnectha_ble integration models."""
from __future__ import annotations

from dataclasses import dataclass

from blueconnectha_ble import PushLock


@dataclass
class BlueConnectBLEData:
    """Data for the Blue Connect ble integration."""

    title: str
    lock: PushLock
    always_connected: bool
