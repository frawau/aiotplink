#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#
# This application is an example on how to use aiolifx
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
import sys
import asyncio as aio
import aiotplink as aiot
from functools import partial
import argparse

#Simple device control from console
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


def readin():
    """Reading from stdin and displaying menu"""

    selection = sys.stdin.readline().strip("\n")

    loaddr = [ x for x in MyDevices.devices.keys()]
    loaddr.sort()
    lov=[ x for x in selection.split(" ") if x != ""]
    if lov:
        if MyDevices.doi:
            #try:
            if int(lov[0]) == 0:
                MyDevices.doi=None
            elif int(lov[0]) == 1:
                if len(lov) >1:
                    if lov[1].lower() in ["1","on","true"]:
                        MyDevices.doi.on()
                    else:
                        MyDevices.doi.off()
                    MyDevices.doi=None
                else:
                    print("Error: For power you must indicate on or off\n")
            elif int(lov[0]) == 2:
                if len(lov) >1:
                    if lov[1].lower() in ["1","on","true"]:
                        MyDevices.doi.led_on()
                    else:
                        MyDevices.doi.led_off()
                    MyDevices.doi=None
                else:
                    print("Error: For led power you must indicate on or off\n")
            elif int(lov[0]) == 3:
                thisname=" ".join([x for x in lov[1:] if x])
                MyDevices.doi.set_name(thisname)
                MyDevices.doi=None
            #except:
                #print ("\nError: Selection must be a number.\n")
        else:
            try:
                if int(lov[0]) > 0:
                    if int(lov[0]) <=len(MyDevices.devices):
                        MyDevices.doi=MyDevices.devices[loaddr[int(lov[0])-1]]
                    else:
                        print("\nError: Not a valid selection.\n")

            except:
                print ("\nError: Selection must be a number.\n")


    if MyDevices.doi:
        print("Select Function for {}:".format(MyDevices.doi.name))
        print("\t[1]\tPower (0 or 1)")
        print("\t[2]\tLED State (0 or 1)")
        print("\t[3]\t<a name>")
        print("")
        print("\t[0]\tBack to device selection")
    else:
        idx=1
        print("Select Device:")
        for x in loaddr:
            print("\t[{}]\t{}".format(idx,MyDevices.devices[x].name or x))
            idx+=1
    print("")
    print("Your choice: ", end='',flush=True)

parser = argparse.ArgumentParser(description="Track and interact with TP-Link devices.")
try:
    opts = parser.parse_args()
except Exception as e:
    parser.error("Error: " + str(e))



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
