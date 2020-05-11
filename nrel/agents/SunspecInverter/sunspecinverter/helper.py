# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

import datetime
import xmltodict
import requests
import os
import logging
from Device import Inverter
from utilities import *
from DER import DERProgramList

from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC

DEBUG = True
xml_path = get_xml_path()
utils.setup_logging()
_log = logging.getLogger(__name__)

class DeviceCapability(object):
    def __init__(self, link, **kwargs):
        self.DeviceCapabilityLink = link 
        if DEBUG:
            self.resources = xmltodict.parse(open(os.path.join(xml_path,'DeviceCapability.xml')).read())
        else:
            self.resources = GET(link)

        self.EndDeviceLink = self.resources['DeviceCapability']['EndDeviceListLink']['@href']
        
class EndDevice(object):
    def __init__(self, href, inverter):
        if DEBUG:
            EndDevice = xmltodict.parse(open(os.path.join(xml_path,'EnddeviceList.xml')).read())
        else:
            EndDevice = GET(href)
        self.EndDevice = EndDevice['EndDeviceList']['EndDevice']
        self.lFDI = self.EndDevice['lFDI']
        self.sFDI = self.EndDevice['sFDI']
        self.DERList = DERList(self.EndDevice['DERListLink']['@href'], inverter)
        self.RegLink = self.register_device(self.EndDevice['RegistrationLink']['@href'])
        self.FSAList = FSAList(self.EndDevice['FunctionSetAssignmentsListLink']['@href'], inverter)

    def register_device(self, href):
        if DEBUG:
            pIN = xmltodict.parse(open(os.path.join(xml_path,'Registration.xml')).read())
        else:
            pIN = GET(href)
        self.pIN = pIN['Registration']['pIN']

class FSAList(object):
    def __init__(self, href, inverter):
        if DEBUG:
            FSAlist = xmltodict.parse(open(os.path.join(xml_path,'FSA.xml')).read())
        else:
            FSAlist = GET(href)
        self.FSAlist = FSAlist["FunctionSetAssignmentsList"]
        FSAs = self.FSAlist["FunctionSetAssignments"]
        self.FSAs = []
        self.FSAlist_link = self.FSAlist['@href']
        for fsa in FSAs:
            self.FSAs.append(FSA(fsa, inverter))

class FSA(object):
    def __init__(self, fsa, inverter):
        self.href = fsa['@href']
        self.mRID = fsa['mRID']
        self.des = fsa['description']
        self.DERProgramList = DERProgramList(fsa['DERProgramListLink'], inverter)
        self.TimeLink = fsa['TimeLink']

class DERList(object):
    def __init__(self, href, inverter):
        if DEBUG:
            DERList = xmltodict.parse(open(os.path.join(xml_path,'DERList.xml')).read())
        else:
            DERList = GET(href)
        self.DERList = DERList["DERList"]
        self.DER = self.DERList["DER"]
        self.href = href
        self.DERCapability = DERCapability(self.DER["DERCapabilityLink"]["@href"], inverter)
        self.DERAvailability = DERAvailability(self.DER["DERAvailabilityLink"]["@href"], inverter)
        self.DERStatus = DERStatus(self.DER["DERStatusLink"]["@href"], inverter)
        self.DERSettings = DERSettings(self.DER["DERSettingsLink"]["@href"], inverter)
    
    def push_updates(self):
        print("pushing updates")
        POST(self.DERCapability.href, get_xml("DERCapability" , self.DERCapability.__dict__))
        POST(self.DERAvailability.href, get_xml("DERAvailability", self.DERAvailability.__dict__))
        POST(self.DERStatus.href, get_xml("DERStatus", self.DERStatus.__dict__))
        POST(self.DERSettings.href, get_xml("DERSettings", self.DERSettings.__dict__))

class DERCapability(object):
    def __init__(self, link, inverter):
        self.modesSupported = 'FFFFFFFF'
        self.href = link
        self.inverter = inverter
        self.refresh()

    def refresh(self):
        if self.inverter is not None:
            self.rtgA = self.inverter.read_point('nameplate', 'ARtg')
            self.rtgAh = self.inverter.read_point('nameplate', 'AhrRtg')
            self.rtgMaxChargeRate = self.inverter.read_point('nameplate', 'MaxChaRte')
            self.rtgMaxDischargeRate = self.inverter.read_point('nameplate', 'MaxDisChaRte')
            self.rtgMinPF = self.inverter.read_point('nameplate', 'PFRtgQ1') 
            self.rtgMinPFNeg = self.inverter.read_point('nameplate', 'PFRtgQ4') 
            self.rtgVA = self.inverter.read_point('nameplate', 'VARtg')
            self.rtgVAr = self.inverter.read_point('nameplate', 'VArRtgQ1')
            self.rtgVArNeg = self.inverter.read_point('nameplate', 'VArRtgQ4') 
            self.rtgW = self.inverter.read_point('nameplate', 'WRtg')
            self.rtgWh = self.inverter.read_point('nameplate', 'WHRtg')
            self.type = self.inverter.read_point('nameplate', 'DERTyp')

class StatusType(object):
    def __init__(self, value, dateTime):
        self.value = value
        self.dateTime = dateTime
            
class DERStatus(object):
    def __init__(self,link, inverter):
        self.href = link
        self.inverter = inverter
        self.refresh()
        
    def refresh(self):
        if self.inverter is not None:
            ECPstatus = self.inverter.read_point('status', 'ECPConn')
            self.genConnectStatus  = self.inverter.read_point('status', 'PVConn')
            self.inverterStatus = self.inverter.read_point('inverter', 'St')
            self.readingTime = self.inverter.read_point('status', 'Tms') 
            self.stateOfChargeStatus = self.inverter.read_point('storage', 'ChaState') 
            self.alarmStatus = self.inverter.read_point('inverter', 'Evt1') 
            
    
class DERAvailability(object):
    def __init__(self, link, inverter):
       self.href = link
       self.inverter = inverter
       self.refresh()

    def refresh(self):
        if self.inverter is not None:
            self.statVArAvail = self.inverter.read_point('status', 'VArAval')
            self.statWAvail = self.inverter.read_point('status', 'WAval')

class DERSettings(object):
    def __init__(self, link, inverter):
        self.href = link
        self.inverter = inverter
        self.refresh()

    def refresh(self):
        if self.inverter is not None:
            self.setGradW = self.inverter.read_point('settings', 'WGra')
            self.setMaxW = self.inverter.read_point('settings', 'WMax')
            self.setMinPFUnderExcited = max(self.inverter.read_point('settings', 'PFMinQ3'), self.inverter.read_point('settings', 'PFMinQ4'))
            self.setMinPFOverExcited = max(self.inverter.read_point('settings', 'PFMinQ1'), self.inverter.read_point('settings', 'PFMinQ2'))
            self.setMaxVarNeg = max(self.inverter.read_point('settings', 'VArMaxQ3'), self.inverter.read_point('settings', 'VArMaxQ4'))
            self.setMaxVar = max(self.inverter.read_point('settings', 'VArMaxQ1'), self.inverter.read_point('settings', 'VArMaxQ2'))
            self.setMaxVA = self.inverter.read_point('settings', 'VAMax')
            self.setMaxChargeRateW = self.inverter.read_point('storage', 'WChaGra')
            self.setMaxDischargeRateW = self.inverter.read_point('storage', 'WDisChaGra')
    
class Event(object):
    def __init__(self):
        self.creationTime = None
        self.interval = None
        
class RandomizableEvent(Event):
    def __init__(self):
        self.randomizeDuration = None
        self.randomizeStart = None

class Response(DeviceCapability):
    def __init__(self, createdDateTime, LFDI, status, mRID, **kwargs):
        self.ResponsesetListLink = self.resources['ResponseSetListLink']['@href']
        self.Responseset = {}
        self.createdDateTime = createdDateTime
        self.endDeviceLFDI = LFDI
        self.status = status
        self.subject = mRID

class LogEvents(EndDevice):
    def __init__(self, link, inverter):
        self.LogEventListLink = self.resources['LogEventListLink']['@href']
        self.inverter = inverter
        

class LogEvent(LogEvents):
    def __init__(self, dt, logID, exData=None, **kwargs):
        self.createdDateTime = get_current_time()
        self.extendedData = exData
        self.profileID = 2 
        self.functionSet = 2 
        self.logEventCode = self.inverter.read_point('inverter', 'Evt1')
        self.logEventID = logID  
        self.logEventPEN = 40732  


