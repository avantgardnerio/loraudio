# Shared helper: enumerate only Espressif serial devices.
# Source this, then call `esp_devices` to populate the DEVS array.
#
# Filters /dev/ttyACM* and /dev/ttyUSB* down to USB vendor 303a (Espressif),
# so non-ESP serial gadgets (e.g. a Z-Wave dongle) are never touched.

ESP_VENDOR_ID="303a"

# Populates the global DEVS array with matching device paths.
# Returns 1 (and leaves DEVS empty) if none are found.
esp_devices() {
    DEVS=()
    local dev vid
    for dev in /dev/ttyACM* /dev/ttyUSB*; do
        [[ -e "$dev" ]] || continue
        vid=$(udevadm info -q property -n "$dev" 2>/dev/null \
              | sed -n 's/^ID_VENDOR_ID=//p')
        [[ "$vid" == "$ESP_VENDOR_ID" ]] && DEVS+=("$dev")
    done
    [[ ${#DEVS[@]} -gt 0 ]]
}
