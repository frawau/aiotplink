#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#
# This library is an asyncio library to communicate with Xiaomi Yeelight
# LED lights.
#
# Copyright (c) 2017 François Wautier
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies
# or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR
# IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE

import asyncio as aio
from . import commands
import logging
import socket
from struct import pack

try:
    xx =aio.create_task
except:
    aio.create_task = aio.ensure_future

HBTIMEOUT = 30  #Poll the device every 30 secs by default
logging.getLogger('frawau.aiotplink').addHandler(logging.NullHandler())


TPLINK_BULBS = { 'LB100': {"temperature": False, "colour": False },
                 'LB110': {"temperature": False, "colour": False },
                 'LB120': {"temperature": (2700, 6500), "colour": False },
                 'LB130': {"temperature": (2500, 9000), "colour": True },
                 'LB200': {"temperature": False, "colour": False },
                 'LB230': {"temperature": (2500, 9000), "colour": True },
                 'KL110': {"temperature": False, "colour": False },
                 'KL120': {"temperature": (2700, 5000), "colour": False },
                 'KL130': {"temperature": (2500, 9000), "colour": True },
                 'KB100': {"temperature": False, "colour": False },
                 'KB130': {"temperature": (2500, 9000), "colour": True }}
TPLINK_PLUGS = { 'HS100' : {"led": True, "emeter": False},
                 'HS103' : {"led": True, "emeter": False},
                 'HS105' : {"led": False, "emeter": False},
                 'HS107' : {"led": True, "emeter": False},
                 'HS110' : {"led": True, "emeter": True},
                 'KP100' : {"led": False, "emeter": False},
    }

class TPProtocol(aio.Protocol):
    """The way the TP-Link protocol works, it opens a connection to the device, send a command
    wait for the response and finally closes the connection.  Here we take care of all this in an
    asyncio way. This behaviour implies that the device need to be polled for info.
    """
    def __init__(self, cmd, future):
        self.transport = None
        self.cmd = cmd
        self.future = future

    def connection_made(self, transport):
        self.transport = transport
        self.send(self.cmd.command)

    def send(self,data):
        self.transport.write(data)

    def data_received(self, data):
        self.future.set_result(self.cmd.response(data))
        logging.debug('We received: {}'.format(self.future.result()))

    def connection_lost(self, exc):
        logging.debug('The server closed the connection.')
        self.transport.close()

class TPDevice(object):
    """Define the common characteristics of TP-Link IoT devices"""

    def __init__(self, name, addr, hb = HBTIMEOUT, on_change=None):
        self.name = name
        self.addr, self.port  = addr
        self.hbto = hb
        self.state = None # device is on or off
        self.online = True # device is online
        self._exclusive = aio.Lock() #To make sure that we only have one connection at a time
        self.onCmd = commands.SetCmd
        self.on_change = on_change #Callback when state change is detected
        self.caps = {"emeter": False}
        self.is_light = False
        self.hb = aio.ensure_future(self.heartbeat())
        self.location = None
        self.mac = None
        self.led = None
        self._pending_value = {}


    async def _send_cmd(self, cmd, callb=None):
        async with self._exclusive:
            loop = aio.get_event_loop()
            resu = loop.create_future()
            coro = loop.create_connection(lambda: TPProtocol(cmd,resu),
                                            self.addr, self.port)
            t, p = await coro
            try:
                await resu
                if callb:
                    callb(resu.result())
            except Exception as e:
                logging.debug("Exception while sending: {}".format(e))
            return resu.result()


    def _set_state(self, val):
        if not self.online:
            raise commands.TPLException("Device is offline")
        if "state" in self._pending_value:
            self.state = self._pending_value["state"]
            del(self._pending_value["state"])


    def on(self):
        self._pending_value["state"] = "on"
        cmd = self.onCmd("on")
        ign = aio.create_task(self._send_cmd(cmd,self._set_state))

    def off(self):
        self._pending_value["state"] = "off"
        cmd = self.onCmd("off")
        ign = aio.create_task(self._send_cmd(cmd,self._set_state))


    def _set_name(self, val):
        if not self.online:
            raise commands.TPLException("Device is offline")
        if "name" in self._pending_value:
            self.name = self._pending_value["name"]
            del(self._pending_value["name"])


    def set_name(self, name):
        self._pending_value["name"] = name
        cmd = commands.SetNameCmd(name)
        ign = aio.create_task(self._send_cmd(cmd,self._set_state))


    async def heartbeat(self):
        wassent = False
        while True:
            #logging.debug("Heartbeat for {}".format(self.name))
            #if True:
            if self.is_light:
                cmd = commands.GetLigthStateCmd
            else:
                cmd = commands.InfoCmd()
            if self.caps["emeter"]:
                cmd += commands.GetPowerCmd()
            try:
                resu = await aio.wait_for(self._send_cmd(cmd),timeout=2)
                wassent = False
            except:
                logging.debug("Heartbeat timeout for {}".format(self.name))
                if self.on_change and not wassent:
                    self.state = None
                    self.on_change({"online":False})
                wassent = True
                self.online = False
            if not wassent and self.mac is None:
                if "mac" in resu:
                    self.mac = resu["mac"]
                if "latitude" in resu:
                    self.location = (resu["latitude"], resu["longitude"])
            schange={}

            if "led" in resu and resu["led"] != self.led :
                schange["led"] = resu["led"]
                self.led = resu["led"]
            if "state" in resu and resu["state"] != self.state :
                schange["state"] = resu["state"]
                self.state = resu["state"]
            if 'current' in resu:
                for key in ['current','voltage', 'power','total']:
                    try:
                        schange[key] = resu[key]
                    except:
                        pass

            if schange and self.on_change:
                self.on_change(schange)
            if self.hbto:
                await aio.sleep(self.hbto)

            else:
                break


class TPSmartDevice(TPDevice):

    def __init__(self, name, addr, hb = HBTIMEOUT, on_change=None):
        super().__init__(name, addr, hb, on_change)
        self.caps["emeter"] = True

    def led_on(self):
        self._pending_value["led"] = "on"
        cmd = self.onCmd("on")
        ign = aio.create_task(self._send_cmd(cmd,self._set_state))

    def led_off(self):
        self._pending_value["led"] = "off"
        cmd = self.onCmd("off")
        ign = aio.create_task(self._send_cmd(cmd,self._set_state))

class TPLight(TPDevice):
    """Define the light characteristics"""

    def __init__(self, name, addr, hb = HBTIMEOUT, on_change=None):
        super().__init__(name, addr, hb, on_change)
        self.onCmd = commands.SetLightCmd
        self.is_light = True
        self.caps = {"colour": False, "temperature":(2700,5000), "emeter": False}
        self.colour = {"temperature":2700, "brightness": 100, "hue": 0, "saturation": 0}

    def _set_state(self, val):
        if not self.online:
            raise commands.TPLException("Device is offline")
        if self._pending_state:
            self.state = self._pending_state
            self._pending_state = None


    def _set_brightness(self, val):
        if not self.online:
            raise commands.TPLException("Device is offline")
        if "brightness" in self._pending_value:
            self.colour["brightness"] = self._pending_value["brightness"]
            del(self._pending_value["brightness"])

    def set_brightness(self, val):
        self._pending_value["brightness"] = val
        cmd = commands.SetLightStateCmdCmd({"brightness":val})
        ign = aio.create_task(self._send_cmd(cmd,self._set_brightness))

class TPWhiteLight(TPLight):
    """Define the light characteristics"""

    def __init__(self, name, addr, hb = HBTIMEOUT, on_change=None):
        super().__init__(name, addr, hb, on_change)
        self.caps["temperature"] = True

    def _set_temperature(self, val):
        if not self.online:
            raise commands.TPLException("Device is offline")
        if "temperature" in self._pending_value:
            self.colour["temperature"] = self._pending_value["temperature"]

            del(self._pending_value["temperature"])

    def set_temperature(self, val):
        self._pending_value["temperature"] = val
        cmd = commands.SetLightStateCmdCmd({"temperature":val})
        ign = aio.create_task(self._send_cmd(cmd,self._set_temperature))



class TPColourLight(TPWhiteLight):
    """Define the light characteristics"""

    def __init__(self, name, addr, hb = HBTIMEOUT, on_change=None):
        super().__init__(name, addr, hb, on_change)
        self.caps["colour"] = True

    def _set_colour(self, val):
        if not self.online:
            raise commands.TPLException("Device is offline")
        for key in ["hue","saturation","brightness"]:
            if key in self._pending_value:
                self.colour[key] = self._pending_value[key]
                del(self._pending_value[key])


    def set_colour(self, hue, saturation, value):
        self._pending_value["hue"] = hue
        self._pending_value["saturation"] = saturation
        self._pending_value["brightness"] = value
        cmd = commands.SetLightStateCmdCmd({"hue":hue,"":saturation,"brightness":value})


def GetDevice(addr,info,hb=HBTIMEOUT,on_change=lambda x: print(x)):
    """Based on infos returned from discovery, return a device"""
    if "model" in info:
        if info["model"][:2].upper() in ["HS","KP"]:
            #A plug"
            if TPLINK_PLUGS[info["model"][:5].upper()]["led"]:
                return TPSmartDevice(info["name"],addr,hb,on_change)
            else:
                return TPDevice(info["name"],addr,hb,on_change)
        elif info["model"][:2].lower() in ["LB","KL","KB"]:
            #A Light
            print("Light {}".format(info["model"]))
            if TPLINK_BULBS[info["model"][:5].upper()]["colour"]:
                return TPColourLight(info["name"],addr,hb,on_change)
            elif TPLINK_BULBS[info["model"][:5].upper()]["temperature"]:
                return TPWhiteLight(info["name"],addr,hb,on_change)
            else:
                return TPLight(info["name"],addr,hb,on_change)

    return None
