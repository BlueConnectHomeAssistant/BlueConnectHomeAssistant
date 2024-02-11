"""The Blue Connect Bluetooth integration."""
from __future__ import annotations

import asyncio

from blueconnectha_ble import (
    AuthError,
    ConnectionInfo,
    LockInfo,
    LockState,
    PushLock,
    BlueConnectBLEError,
    close_stale_connections_by_address,
    local_name_is_unique,
)

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import (
    CONF_ALWAYS_CONNECTED,
    CONF_KEY,
    CONF_LOCAL_NAME,
    CONF_SLOT,
    DEVICE_TIMEOUT,
    DOMAIN,
)
from .models import BlueConnectBLEData
from .util import async_find_existing_service_info, bluetooth_callback_matcher

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.LOCK, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Blue Connect Bluetooth from a config entry."""
    local_name = entry.data[CONF_LOCAL_NAME]
    address = entry.data[CONF_ADDRESS]
    key = entry.data[CONF_KEY]
    slot = entry.data[CONF_SLOT]
    has_unique_local_name = local_name_is_unique(local_name)
    always_connected = entry.options.get(CONF_ALWAYS_CONNECTED, False)
    push_lock = PushLock(
        local_name, address, None, key, slot, always_connected=always_connected
    )
    id_ = local_name if has_unique_local_name else address
    push_lock.set_name(f"{entry.title} ({id_})")

    # Ensure any lingering connections are closed since the device may not be
    # advertising when its connected to another client which will prevent us
    # from setting the device and setup will fail.
    await close_stale_connections_by_address(address)

    @callback
    def _async_update_ble(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Update from a ble callback."""
        push_lock.update_advertisement(service_info.device, service_info.advertisement)

    shutdown_callback: CALLBACK_TYPE | None = await push_lock.start()

    @callback
    def _async_shutdown(event: Event | None = None) -> None:
        nonlocal shutdown_callback
        if shutdown_callback:
            shutdown_callback()
            shutdown_callback = None

    entry.async_on_unload(_async_shutdown)

    # We may already have the advertisement, so check for it.
    if service_info := async_find_existing_service_info(hass, local_name, address):
        push_lock.update_advertisement(service_info.device, service_info.advertisement)

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_update_ble,
            bluetooth_callback_matcher(local_name, push_lock.address),
            bluetooth.BluetoothScanningMode.PASSIVE,
        )
    )

    try:
        await push_lock.wait_for_first_update(DEVICE_TIMEOUT)
    except AuthError as ex:
        raise ConfigEntryAuthFailed(str(ex)) from ex
    except (BlueConnectBLEError, asyncio.TimeoutError) as ex:
        raise ConfigEntryNotReady(
            f"{ex}; Try moving the Bluetooth adapter closer to {local_name}"
        ) from ex

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = BlueConnectBLEData(
        entry.title, push_lock, always_connected
    )

    @callback
    def _async_device_unavailable(
        _service_info: bluetooth.BluetoothServiceInfoBleak,
    ) -> None:
        """Handle device not longer being seen by the bluetooth stack."""
        push_lock.reset_advertisement_state()

    entry.async_on_unload(
        bluetooth.async_track_unavailable(
            hass, _async_device_unavailable, push_lock.address
        )
    )

    @callback
    def _async_state_changed(
        new_state: LockState, lock_info: LockInfo, connection_info: ConnectionInfo
    ) -> None:
        """Handle state changed."""
        if new_state.auth and not new_state.auth.successful:
            entry.async_start_reauth(hass)

    entry.async_on_unload(push_lock.register_callback(_async_state_changed))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_shutdown)
    )
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    data: BlueConnectBLEData = hass.data[DOMAIN][entry.entry_id]
    if entry.title != data.title or data.always_connected != entry.options.get(
        CONF_ALWAYS_CONNECTED
    ):
        await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
