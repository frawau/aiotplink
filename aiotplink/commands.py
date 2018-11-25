#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#
# This library is an asyncio library to communicate with TP-Link devices
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

import datetime as dt
import json, logging, re

from enum import IntEnum
from struct import pack,unpack
from urllib.parse import urlparse

class TPLException(Exception):
    pass

class TPLCodec(object):

    @staticmethod
    def encrypt(string):
        key = 171
        result = pack('>I', len(string))
        for i in string:
            a = key ^ ord(i)
            key = a
            result += bytes([a])
        return result

    @staticmethod
    def decrypt(string):
        key = 171
        result = ""
        for i in string:
            a = key ^ i
            key = i
            result += chr(a)
        length = unpack('>I', string[:4])
        #assert length == len(result[4:])
        return result

class BasicCommand(object):
    """TP-Link commands are simply dictionaries of dictionaries.

    Here we have a simple structure to build commands

    """

    description = None

    def __init__(self):
        self.cmd = [[]]
        self.val = [{}]
        self.cmdlist=[self.__class__]
        self.translation={}
        self.vtranslation={}
        self.ignore = ["err_code"]

    def __repr__(self):
        return str(self.value)

    def _verify_value(self,val):
        return val

    @property
    def value(self):
        resu={}
        for lok,val in zip(self.cmd,self.val):
            thisval = val
            for k in lok[::-1]:
                thisval = {k:thisval}
            resu.update(thisval)
        return resu

    def translate(self, key):
        if key in self.translation:
            return self.translation[key]
        return key

    def vtranslate(self, key, val):
        if key in self.vtranslation:
            return self.vtranslation[key][val]
        return val

    @value.setter
    def value(self,val):
        """ Here setting a value replaces the Last value
        """
        self.val = self.val[:-1] + [self._verify_value(val)]


    def response(self,data,noskip=False,ignore=False):
        """Process received data"""
        if noskip:
            sidx=0
        else:
            sidx=4
        resp = json.loads(TPLCodec.decrypt(data[sidx:]))
        fullresp = {}
        for cmd in self.cmd:
            thisresp =resp
            for key in cmd:
                if key in thisresp:
                    thisresp=thisresp[key]
                else:
                    break

            if "err_code" in thisresp and thisresp["err_code"] != 0:
                if not ignore:
                    raise TPLException("Got error %d for command %s" % (thisresp["err_code"],key))
                else:
                    fullresp[cmd[0]] = ("err_msg" in thisresp and thisresp["err_msg"]) or thisresp["err_code"]
            for skey in thisresp:
                if skey not in self.ignore:
                    fullresp[self.translate(skey)] = self.vtranslate(skey, thisresp[skey])
        return fullresp

    @property
    def command(self):
        """Return the command to be sent down the wire"""
        return TPLCodec.encrypt(json.dumps(self.value))

    @property
    def pclass(self):
        return super().__class__

    def __add__(self, other):
        """Simply add cmd and value
        """
        #if self.pclass == other.pclass:
            #raise TPLException("Only different commands can be added (%s and %s)"%(self.pclass,other.pclass))

        self.cmd += other.cmd
        self.val += other.val
        self.cmdlist += other.cmdlist
        self.translation.update(other.translation)
        self.ignore += other.ignore
        return self

    def __iadd__(self,other):
        return self.__add__(other)


    #def __sub__(self, other):
        #""" Remove all instances in Other from self
        #"""
        #goon = True
        #while goon:
            #idx = 0
            #remove = -1
            #for acmd in self.cmd:
                #if acmd in other.cmd:
                    #remove = idx
                    #break
                #idx +=1

            #if remove > -1:
                #self.cmd = self.cmd[:remove]+self.cmd[remove+1:]
                #self.val = self.val[:remove]+self.val[remove+1:]
                #self.cmdlist = self.cmdlist[:remove]+self.cmdlist[remove+1:]
            #else:
                #goon = False



class SysCmd(BasicCommand):

    description = None

    def __init__(self):
        super().__init__()
        self.cmd[0].append("system")
        self.translation["led_off"]="led"
        self.translation["relay_state"]="state"
        self.translation["alias"]="name"
        self.translation["hw_ver"]="hardware version"
        self.translation["sw_ver"]="software version"
        self.translation["icon_hash"]="icon hash"
        self.vtranslation["relay_state"]={0:"off",1:"on"}
        self.vtranslation["led_off"]={1:"off",0:"on"}
        self.ignore=["feature","oemId","fwId","hwId","dev_name","latitude_i","longitude_i","ctrl_protocols","preferred_state"]

class InfoCmd(SysCmd):

    description = "Get device info."

    def __init__(self):
        super().__init__()
        self.cmd[0].append("get_sysinfo")

    def _verify_value(self,val):
        raise ValueError("Info command should not have a value")

class RebootCmd(SysCmd):

    description = "Reboot device."

    def __init__(self, delay = 1):
        super().__init__()
        self.cmd[0].append("reboot")
        self.cmd[0].append("delay")
        self.val[0] = delay

    def _verify_value(self,val):
        if not isinstance(val,int):
            raise ValueError("Reboot command delay value must be an integer")
        return val

class ResetCmd(SysCmd):

    description = "Reset device"

    def __init__(self, delay = 1):
        super().__init__()
        self.cmd[0].append("reset")
        self.cmd[0].append("delay")
        self.val[0] = delay

    def _verify_value(self,val):
        if not isinstance(val,int):
            raise ValueError("Reset command delay value must be an integer")
        return val

class SetCmd(SysCmd):

    description = "Set device state (On/Off)."

    def __init__(self,val=0):
        super().__init__()
        self.cmd[0].append("set_relay_state")
        self.cmd[0].append("state")
        self.val[0] = self._verify_value(val)

    def _verify_value(self,val):
        if isinstance(val,str):
            if val.lower() in ["on","off"]:
                return (val.lower()=="on" and 1) or 0
            else:
                raise ValueError("Set command value must be \"on\"/1/True or \"off\"/0/False")

        if isinstance(val,bool):
                return (val and 1) or 0

        if not isinstance(val,int) or val not in [0,1]:
            raise ValueError("Set command value must be \"on\"/1/True or \"off\"/0/False")
        return val


class SetLedCmd(SysCmd):

    description = "Set device LED (On/Off)."

    def __init__(self,val=0):
        super().__init__()
        self.cmd[0].append("set_led_off")
        self.cmd[0].append("off")
        self.val[0] = self._verify_value(val)

    def _verify_value(self,val):
        if isinstance(val,str):
            if val.lower() in ["on","off"]:
                return (val.lower()=="off" and 1) or 0
            else:
                raise ValueError("SetLed command value must be \"on\"/1/True or \"off\"/0/False")

        if isinstance(val,bool):
                return (not val and 1) or 0

        if not isinstance(val,int) or val not in [0,1]:
            raise ValueError("SetLed command value must be \"on\"/1/True or \"off\"/0/False")
        return 0 if val else 1


class SetNameCmd(SysCmd):

    description = "Set device friendly name."

    def __init__(self,val="TP-Link Device"):
        super().__init__()
        self.cmd[0].append("set_dev_alias")
        self.cmd[0].append("alias")
        self.val[0] = val

    def _verify_value(self,val):
        if not isinstance(val,str):
            raise ValueError("SetName command value must be a string")
        return val


class SetMacCmd(SysCmd):

    description = "Set device MAC address"

    def __init__(self,val="00:00:00:00:00:00"):
        super().__init__()
        self.cmd[0].append("set_mac_addr")
        self.cmd[0].append("mac")
        self.val[0] = val

    def _verify_value(self,val):
        regex = r"(?:[0-9A-F]{2}[:]){5}(?:[0-9A-F]{2})"
        if not isinstance(val,str) or not re.match(regex,val,re.IGNORECASE):
            raise ValueError("SetAlias command value must be a string")
        return val.lower()


class SetLocationCmd(SysCmd):

    description = "Set device GEO location."

    def __init__(self,val={"latitude": 48.8614 , "longitude": 2.3933}):
        super().__init__()
        self.cmd[0].append("set_dev_location")
        self.val[0] = val

    def _verify_value(self,val):
        if not isinstance(val,dict):
            raise ValueError("SetLocation command value must be a dictionary %s"% self.val[0])
        if not set(['latitude', 'longitude']).issuperset(set(val.keys())):
            raise ValueError("SetLocation command value must be a dictionary  %s"% self.val[0])
        if val == {}:
            return self.val[0]
        self.val.update(val)
        return self.val


class GetIconCmd(SysCmd):

    description = "Get device icon."

    def __init__(self):
        super().__init__()
        self.cmd[0].append("get_dev_icon")

    def _verify_value(self,val):
        raise ValueError("GetIcon command does not need a value")


class FWSetUrlCmd(SysCmd):

    description = "Set firmware download URL."

    def __init__(self,val="http://a.com/firmware.bin"):
        super().__init__()
        self.cmd[0].append("download_firmware")
        self.cmd[0].append("url")
        self.val[0] = val

    def _verify_value(self,val):
        try:
            purl = urlparse(val)
        except:
            raise ValueError("FWSetUrl command requires a URL for  value")

        if purl.scheme not in ["http","https"]:
            raise ValueError("FWSetUrl command requires a URL for  value")
        return val


class FWDownloadStateCmd(SysCmd):

    description = "Get firmware download progress."

    def __init__(self):
        super().__init__()
        self.cmd[0].append("get_download_state")

    def _verify_value(self,val):
        raise ValueError("FWDownloadState command does not need a value")


class FWFlashCmd(SysCmd):

    description = "Flash downloaded firmware."

    def __init__(self,):
        super().__init__()
        self.cmd[0].append("flash_firmware")

    def _verify_value(self,val):
        raise ValueError("FWFlash command does not need a value")



class WlanCmd(BasicCommand):

    description = None

    def __init__(self):
        super().__init__()
        self.cmd[0].append("netif")


class ScanCmd(WlanCmd):

    description = "Scan for available SSID."

    def __init__(self):
        super().__init__()
        self.cmd[0].append("get_scaninfo")
        self.cmd[0].append("refresh")
        self.val[0] = 1

    def _verify_value(self,val):
        raise ValueError("Scan command does not need a value")

class ENCRYPT(IntEnum):
    NONE = 0
    WEP = 1
    WPA = 2
    WPA2 = 3

class SetWifiCmd(WlanCmd):

    description = "Configure WiFi access."

    def __init__(self,val={'ssid':'Wakanda', 'password':'Really Great P@$$w0Rd!', 'key_type': ENCRYPT.WPA2}):
        super().__init__()
        self.cmd[0].append("set_stainfo")
        self.val[0] = val

    def _verify_value(self,val):
        if not isinstance(val,dict):
            raise ValueError("SetWifi command value must be a dictionary %s"% self.val[0])
        if not set(['ssid', 'password','key_type']).issuperset(set(val.keys())):
            raise ValueError("SetWifi command value must be a dictionary %s"% self.val[0])
        if val == {}:
            return self.val[0]
        self.val.update(val)
        return self.val


class CloudCmd(BasicCommand):

    description = None

    def __init__(self):
        super().__init__()
        self.cmd[0].append("cnCloud")


class CloudInfoCmd(CloudCmd):

    description = "Get cloud info."

    def __init__(self):
        super().__init__()
        self.cmd[0].append("get_info")

    def _verify_value(self,val):
        raise ValueError("CloudInfo command does not need a value")


class FWInfoCmd(CloudCmd):

    description = "Get available firmwares."

    def __init__(self):
        super().__init__()
        self.cmd[0].append("get_intl_fw_list")

    def _verify_value(self,val):
        raise ValueError("FWInfo command does not need a value")

class SetUrlCmd(CloudCmd):

    description = "Set cloud server."

    def __init__(self,val="devs.tplinkcloud.com"):
        super().__init__()
        self.cmd[0].append("set_server_url")
        self.cmd[0].append("server")
        self.val[0] = val

    def _verify_value(self,val):
        try:
            purl = urlparse(val)
        except:
            raise ValueError("SetUrl command requires a URL for  value")
        return val

class ConnectCmd(CloudCmd):

    description = "Login to cloud server."

    def __init__(self,val={'username':'BruceWayne', 'password':'Really Great P@$$w0Rd!'}):
        super().__init__()
        self.cmd[0].append("bind")
        self.val[0] = 1

    def _verify_value(self,val):
        if not isinstance(val,dict):
            raise ValueError("Connect command value must be a dictionary %s"% self.val[0])
        if not set(['username', 'password']).issuperset(set(val.keys())):
            raise ValueError("Connect command value must be a dictionary %s"% self.val[0])
        if val == {}:
            return self.val[0]
        self.val.update(val)
        return self.val


class DisconnectCmd(CloudCmd):

    description = "Logout from cloud server."

    def __init__(self):
        super().__init__()
        self.cmd[0].append("unbind")

    def _verify_value(self,val):
        raise ValueError("Disconnect command does not need a value")

# Time Commands

class TimeCmd(BasicCommand):

    description = None

    def __init__(self):
        super().__init__()
        self.cmd[0].append("time")


class GetTimeCmd(TimeCmd):

    description = "What time is it?"

    def __init__(self):
        super().__init__()
        self.cmd[0].append("get_time")

    def _verify_value(self,val):
        raise ValueError("GetTime command does not need a value")


class GetTimeZoneCmd(TimeCmd):

    description = "Get device timezone."

    def __init__(self):
        super().__init__()
        self.cmd[0].append("get_timezone")

    def _verify_value(self,val):
        raise ValueError("GetTimeZone command does not need a value")


class SetTimeCmd(TimeCmd):

    description = "Set device time/timezone."

    def __init__(self):
        super().__init__()
        self.cmd[0].append("set_timezone")
        now = dt.datetime.now()
        self.val[0] = {"year":now.year,"month":now.month,"mday":now.day,"hour":now.hour,"min":now.minute,"sec":now.second,"index":42}

    def _verify_value(self,val):
        if not isinstance(val,dict):
            raise ValueError("SetTime command value must be a dictionary %s"% str(self.val[0]))
        if not set(['year', 'month', 'mday', 'hour', 'min', 'sec', 'index']).issuperset(set(val.keys())):
            raise ValueError("SetTime command value must be a dictionary %s"% str(self.val[0]))
        if val == {}:
            return self.val[0]
        self.val.update(val)
        return self.val

# Power meter commands

class MeterCmd(BasicCommand):

    description = None

    def __init__(self,is_light=False):
        super().__init__()
        if is_light:
            self.cmd[0].append("smartlife.iot.common.emeter")
        else:
            self.cmd[0].append("emeter")

class GetPowerCmd(MeterCmd):

    description = "Get current meter status."

    def __init__(self, is_light=False):
        super().__init__(is_light)
        self.cmd[0].append("get_realtime")

    def _verify_value(self,val):
        raise ValueError("GetPower command does not need a value")

class GetGainCmd(MeterCmd):

    description = "Get meter voltage/current gain."

    def __init__(self, is_light=False):
        super().__init__(is_light)
        self.cmd[0].append("get_vgain_igain")

    def _verify_value(self,val):
        raise ValueError("GetGain command does not need a value")


class SetGainCmd(MeterCmd):

    description = "Set meter voltage/current gain."

    def __init__(self,val={'vgain':13462,'igain':16835}, is_light=False):
        super().__init__(is_light)
        self.cmd[0].append("set_vgain_igain")
        self.val[0] = val

    def _verify_value(self,val):
        if not isinstance(val,dict):
            raise ValueError("SetGain command value must be a dictionary %s"% self.val[0])
        if not set(['vgain', 'igain']).issuperset(set(val.keys())):
            raise ValueError("SetGain command value must be a dictionary %s"% self.val[0])
        if val == {}:
            return self.val[0]
        self.val.update(val)
        return self.val


class CalibrateCmd(MeterCmd):

    description = "Calibrate meter voltage/current gain."

    def __init__(self,val={'vtarget':13462,'itarget':16835}, is_light=False):
        super().__init__(is_light)
        self.cmd[0].append("start_calibration")
        self.val[0] = val

    def _verify_value(self,val):
        if not isinstance(val,dict):
            raise ValueError("Calibrate command value must be a dictionary %s"% self.val[0])
        if not set(['vtarget', 'itarget']).issuperset(set(val.keys())):
            raise ValueError("Calibrate command value must be a dictionary %s"% self.val[0])
        if val == {}:
            return self.val[0]
        self.val.update(val)
        return self.val


class GetStatsCmd(MeterCmd):

    description = "Get daily power usage."

    def __init__(self, is_light=False):
        super().__init__(is_light)
        self.cmd[0].append("get_daystat")
        now = dt.datetime.date()
        self.val[0] = {"month":now.month,"year":now.year}

    def _verify_value(self,val):
        if not isinstance(val,dict):
            raise ValueError("GetStats command value must be a dictionary %s"% self.val[0])
        if not set(['month', 'year']).issuperset(set(val.keys())):
            raise ValueError("GetStats command value must be a dictionary %s"% self.val[0])
        if val == {}:
            return self.val[0]
        self.val.update(val)
        return self.val

class GetMonthStatsCmd(MeterCmd):

    description = "Get monthly power usage."

    def __init__(self, is_light=False):
        super().__init__(is_light)
        self.cmd[0].append("get_monthstat")
        now = dt.datetime.date()
        self.val[0] = {"year":now.year}

    def _verify_value(self,val):
        if not isinstance(val,dict):
            raise ValueError("GetMonthStats command value must be a dictionary %s"% self.val[0])
        if not set(['year']).issuperset(set(val.keys())):
            raise ValueError("GetMonthStats command value must be a dictionary %s"% self.val[0])
        if val == {}:
            return self.val[0]
        self.val.update(val)
        return self.val


class ResetStatsCmd(MeterCmd):

    description = "Reset power usage stats."

    def __init__(self, is_light=False):
        super().__init__(is_light)
        self.cmd[0].append("erase_emeter_stat")

    def _verify_value(self,val):
        raise ValueError("ResetStats command does not need a value")

# Light Commands

class LightCmd(BasicCommand):

    description = None

    def __init__(self):
        super().__init__()
        self.cmd[0].append("smartlife.iot.smartbulb.lightingservice")
        self.translation["on_off"]="state"


class GetLigthStateCmd(LightCmd):

    description = "Get light state information."

    def __init__(self):
        super().__init__()
        self.cmd[0].append("get_light_state")

    def _verify_value(self,val):
        raise ValueError("GetLightState command does not need a value")

class SetLightStateCmd(LightCmd):

    description = "Set light state (colour, brighness, temperature, on, off)."

    def __init__(self, val=0):
        super().__init__()
        self.cmd[0].append("transition_light_state")
        self.val[0] = self._verify_value({"on_off": val})

    def _verify_value(self,val):
        if not isinstance(val,dict):
            raise ValueError("SetLightState command value must be a dictionary")

        if val == {}:
            return self.val[0]

        if set(['hue', 'saturation', 'value']) == set(val.keys()):
            thisval={"color_temp": 0}
            if not isinstance(val["hue"],int) or val["hue"] < 0  or val["hue"] > 360:
                raise ValueError("SetLightState command value for hue must be an integer between 0 and 360.")
            else:
                thisval["hue"] = val["hue"]

            if not isinstance(val["saturation"],int) or val["saturation"] < 0  or val["saturation"] > 100:
                raise ValueError("SetLightState command value for saturation must be an integer between 0 and 100.")
            else:
                thisval["saturation"] = val["saturation"]

            if not isinstance(val["value"],int) or val["value"] < 0  or val["value"] > 100:
                raise ValueError("SetLightState command value for value must be an integer between 0 and 100.")
            else:
                thisval["brightness"] = val["value"]
            return thisval

        if set(['brightness']) == set(val.keys()):
            if not isinstance(val["brightness"],int) or val["brightness"] < 0  or val["brightness"] > 100:
                raise ValueError("SetLightState command value for brightness must be an integer between 0 and 100.")
            return val

        if set(['temperature']) == set(val.keys()):
            if not isinstance(val["temperature"],int) or val["temperature"] < 2500  or val["temperature"] > 9000:
                raise ValueError("SetLightState command value for temperature must be an integer between 2500 and 9000.")
            return {"color_temp": val["temperature"]}


        if set(['state']) == set(val.keys()):
            thisval=val["state"]
            if isinstance(thisval,str):
                if thisval.lower() in ["on","off"]:
                   val["on_off"] = (thisval.lower()=="on" and 1) or 0
                else:
                    raise ValueError("SetLightState command value for on_off must be \"on\"/1/True or \"off\"/0/False")

            elif isinstance(thisval,bool):
                val["on_off"] = (val and 1) or 0

            elif not isinstance(thisval,int) or thisval not in [0,1]:
                raise ValueError("SetLightState command value for on_off must be \"on\"/1/True or \"off\"/0/False")
            return val

        raise ValueError("SetLightState command value does not contain the proper key combination")

class SetLightCmd(SetLightStateCmd):
    """ A shortcut"""

    description = "Set light state (On/Off)."

    def __init__(self,val=0):
        super().__init__()
        self.cmd[0].append("set_relay_state")
        self.cmd[0].append("state")
        self.val[0] = self._verify_value(val)

    def _verify_value(self,val):
        if isinstance(val,str):
            if val.lower() in ["on","off"]:
                return {"on_off" :(val.lower()=="on" and 1) or 0}
            else:
                raise ValueError("Set command value must be \"on\"/1/True or \"off\"/0/False")

        if isinstance(val,bool):
                return {"on_off" :(val and 1) or 0}

        if not isinstance(val,int) or val not in [0,1]:
            raise ValueError("Set command value must be \"on\"/1/True or \"off\"/0/False")
        return {"on_off": val}
