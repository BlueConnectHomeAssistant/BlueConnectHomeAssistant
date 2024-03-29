"""Support for blueconnectha ble sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from blueconnectha_ble import ConnectionInfo, LockInfo, LockState

from homeassistant import config_entries
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricPotential,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import BLUECONNECTBLEEntity
from .models import BlueConnectBLEData


@dataclass(frozen=True)
class BlueConnectBLERequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[LockState, LockInfo, ConnectionInfo], int | float | None]


@dataclass(frozen=True)
class BlueConnectBLESensorEntityDescription(
    SensorEntityDescription, BlueConnectBLERequiredKeysMixin
):
    """Describes Blue Connect Bluetooth sensor entity."""


SENSORS: tuple[BlueConnectBLESensorEntityDescription, ...] = (
    BlueConnectBLESensorEntityDescription(
        key="",  # No key for the original RSSI sensor unique id
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_registry_enabled_default=False,
        value_fn=lambda state, info, connection: connection.rssi,
    ),
    BlueConnectBLESensorEntityDescription(
        key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda state, info, connection: state.battery.percentage
        if state.battery
        else None,
    ),
    BlueConnectBLESensorEntityDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_registry_enabled_default=False,
        value_fn=lambda state, info, connection: state.battery.voltage
        if state.battery
        else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Blue Connect Bluetooth sensors."""
    data: BlueConnectBLEData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(BlueConnectBLESensor(description, data) for description in SENSORS)


class BlueConnectBLESensor(BLUECONNECTBLEEntity, SensorEntity):
    """Blue Connect Bluetooth sensor."""

    entity_description: BlueConnectBLESensorEntityDescription

    def __init__(
        self,
        description: BlueConnectBLESensorEntityDescription,
        data: BlueConnectBLEData,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        super().__init__(data)
        self._attr_unique_id = f"{data.lock.address}{description.key}"

    @callback
    def _async_update_state(
        self, new_state: LockState, lock_info: LockInfo, connection_info: ConnectionInfo
    ) -> None:
        """Update the state."""
        self._attr_native_value = self.entity_description.value_fn(
            new_state, lock_info, connection_info
        )
        super()._async_update_state(new_state, lock_info, connection_info)
