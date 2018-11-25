# aiotplink
Library to communicate with TP-Link Smart Plugs and similar devices
## Features

* Supports TPLink Smart Switches and Lights
* Python API to interact with device at a low level using asyncio

## About this library

Based on th ework done by [SoftSCheck](https://github.com/softScheck/tplink-smartplug)
 and [GadgetReactor](https://github.com/GadgetReactor/pyHS100)

## Installation
```
$ sudo pip3 install aiotplink

```

At this point you should be able to use

You can try:
```
python3 -m aioyplink
```
And you should be able to turn On/Off your devices

## Using the library.

To make things simple, you create a class with 2 methods, "register" and "unregister"

    class devices():
        """ A simple class with a register and  unregister methods
        """
        def __init__(self):
            self.devices={}
            self.doi=None #device of interest

        def register(self,info, addr):
            if "mac" in info and info["mac"].lower() not in self.devices:
                self.devices[info["mac"].lower()] = aiot.GetDevice(addr,info,hb=10)
            else:
                self.devices[info["mac"].lower()].addr = addr

        def unregister(self,mac):
            if mac.lower() in self.devices:
                print ("%s is gone"% self.devices[mac.lower()].name)
                self.devices[mac.lower()].stop()
                del(self.devices[mac.lower()])

        def stop(self):
            for dev in self.devices.values():
                dev.stop()

When registering, you get an dictionary with the flatten out info from a TP-Link device, and an address with
the format (<ip address>, <port>). You can pass those information directly to 'GetDevice' to get the correct object.

'GetDevice" is defined like so

    GetDevice(addr,info,hb=HBTIMEOUT,on_change=lambda x: print(x))

With addr, the address pair, info, the flatten out informaton from discovery, hb, a heatbeat timeout in secs and
on_change a function that will react to whatever is produced by the heartbeat. Note that if the device has an energy meter,
those values will automatically be produced with the heartbeat.

After that it is quite simple.

    MyDevices= devices()
    loop = aio.get_event_loop()
    discovery = aiot.TPLinkDiscovery(loop, MyDevices, repeat=15)
    try:
        loop.add_reader(sys.stdin,readin)
        discovery.start()
        print("Hit \"Enter\" to start")
        print("Use Ctrl-C to quit")
        loop.run_forever()
    except:
        print("Exiting at user's request.")
    finally:
        MyDevices.stop()
        discovery.cleanup()
        loop.remove_reader(sys.stdin)
        loop.run_until_complete(aio.sleep(10))
        loop.close()

Create a registrar instance
Create a TPLinkDiscovery instance passing the registrar and how often to run discovery
Start discovery, and you are on your merry way.

The various device object will have these methods available.

      on(): Turning the device on
      off(): Turning the device off
      led_on(): Turn the LED light on (AKA "Night mode" off)
      led_off : Turn the LED light off (AKA "Night mode" on)
      set_name(name)
      set_brighness)
      set_temperature()
      set_colour(hue, saturation, value)

depending on their capabilities.

Most commands are defined in the commands.py file.


## Troubleshooting

Open an issue and I'll try to help.
