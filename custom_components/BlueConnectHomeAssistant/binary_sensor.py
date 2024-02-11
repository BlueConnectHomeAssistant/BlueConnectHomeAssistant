ale"""Support for blueconnectha ble binary sensors."""
from __future__ import annotations

from blueconnectha_ble import ConnectionInfo, DoorStatus, LockInfo, LockState

from homeassistant import config_entries
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import BLUECONNECTBLEEntity
from .models import BlueConnectBLEData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Blue Connect binary sensors."""
    data: BlueConnectBLEData = hass.data[DOMAIN][entry.entry_id]
    lock = data.lock
    if lock.lock_info and lock.lock_info.door_sense:
        async_add_entities([BlueConnectBLEDoorSensor(data)])


class BlueConnectBLEDoorSensor(BLUECONNECTBLEEntity, BinarySensorEntity):
    """Blue Connect BLE binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.DOOR

    @callback
    def _async_update_state(
        self, new_state: LockState, lock_info: LockInfo, connection_info: ConnectionInfo
    ) -> None:
        """Update the state."""
        self._attr_is_on = new_state.door == DoorStatus.OPENED
        super()._async_update_state(new_state, lock_info, connection_info)
