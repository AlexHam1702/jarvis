import tinytuya

# Use the generic Device class, not OutletDevice
d = tinytuya.Device(
    dev_id="bf102fc8f2d338afefrhan", 
    address="192.168.1.166", 
    local_key="'(hz(6/^vPp2e!UR", 
    version=3.4
)

print(d.status())