#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#
# This library is an asyncio library to discover TP-Link Smart Home devices
#
# Copyright (c) 2018 François Wautier
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
import socket
from .commands import InfoCmd, GetPowerCmd

DFLTPORT = 9999
DFLTIP = '0.0.0.0'

DISCOVERY_CMD = InfoCmd() + GetPowerCmd()

class DFLTRegistrar(object):

    def register(self, info, addr):
         print("Registering %s from %s"%(info,addr))

    def unregister(self, mac_addr):
        print("Unregistering %s"%mac_addr)

class TPLinkDiscovery:

    def __init__(self, loop,registrar=DFLTRegistrar(), repeat=0):
        self.loop = loop
        self.registrar = registrar
        self.repeat = repeat
        self.known_devices=[]
        self.last_seen = []
        self.done= aio.Future()
        self.discovery = None

    def connection_made(self, transport):
        self.transport = transport
        sock = transport.get_extra_info("socket")
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.loop.call_soon(self.broadcast)

    def datagram_received(self, data, addr):
        response = DISCOVERY_CMD.response(data, noskip = True,ignore=True) #Ignore errors
        if "mac" in response:
            if response["mac"].lower() not in self.known_devices:
                self.known_devices.append(response["mac"].lower())
                self.registrar.register(response,addr)
            self.last_seen.append(response["mac"].lower())


    def broadcast(self):

        if not self.done.done():
            unregister = [ x for x in self.known_devices if x not in self.last_seen]
            self.known_devices = self.last_seen
            self.last_seen = []
            for x in unregister:
                self.registrar.unregister(x)
            self.transport.sendto(DISCOVERY_CMD.command[4:], ('255.255.255.255', 9999))
            if self.repeat:
                self.loop.call_later(self.repeat, self.broadcast)
            else:
                #Give it a few secs, 5 secs
                self.loop.call_later(5, self.close)

    def close(self):
        if not self.done.done():
            self.done.set_result(True)
        self.cleanup()

    def connection_lost(self,x):
        self.repeat = 0
        self.close()

    def start(self, listen_ip=DFLTIP, listen_port=DFLTPORT):
        """Start discovery task."""
        coro = self.loop.create_datagram_endpoint(
            lambda: self, local_addr=(listen_ip, listen_port))

        self.discovery = self.loop.create_task(coro)
        return self.discovery

    def cleanup(self):
        """Method to call to cleanly terminate the connection to the device.
        """
        if self.transport:
            self.transport.close()
            self.transport = None
        if self.discovery:
            self.discovery.cancel()
            self.discovery = None

if __name__ == "__main__":
    TIMEOUT = 10
    async def waitforme(future):
        await future

    loop = aio.get_event_loop()
    disco = TPLinkDiscovery(loop,repeat=TIMEOUT)

    try:
        xx= disco.start()
        loop.run_until_complete(aio.wait([disco.done]))
    except:
        print("Exiting cleanly")
        disco.close()
        loop.run_until_complete(aio.sleep(TIMEOUT))
    finally:
        loop.close()
