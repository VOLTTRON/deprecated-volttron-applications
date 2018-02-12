# 
# Copyright 2017 , UT-Battelle, LLC
# All rights reserved
# [Home Assistant- VOLTTRON Integration, Version 1.0]
# OPEN SOURCE LICENSE (Permissive)
# 
# Subject to the conditions of this License, UT-Battelle, LLC (the “Licensor”)
# hereby grants, free of charge, to any person (the “Licensee”) obtaining a copy
# of this software and associated documentation files (the "Software"), a perpetual,
# worldwide, non-exclusive, no-charge, royalty-free, irrevocable copyright license 
# to use, copy, modify, merge, publish, distribute, and/or sublicense copies of the
#  Software.
# 
# 1. Redistributions of Software must retain the above open source license grant, 
#    copyright and license notices, this list of conditions, and the disclaimer listed
#    below.  Changes or modifications to, or derivative works of the Software must be
#    noted with comments and the contributor and organization’s name.
# 
# 2. Neither the names of Licensor, the Department of Energy, or their employees may
#    be used to endorse or promote products derived from this Software without their
#    specific prior written permission.
# 
# 3. If the Software is protected by a proprietary trademark owned by Licensor or the
#    Department of Energy, then derivative works of the Software may not be distributed
#    using the trademark without the prior written approval of the trademark owner. 
#     
# 
# 
# ****************************************************************************************************************
# DISCLAIMER
# 
# UT-Battelle, LLC AND THE GOVERNMENT MAKE NO REPRESENTATIONS AND DISCLAIM ALL WARRANTIES,
# BOTH EXPRESSED AND IMPLIED.  THERE ARE NO EXPRESS OR IMPLIED WARRANTIES OF MERCHANTABILITY
# OR FITNESS FOR A PARTICULAR PURPOSE, OR THAT THE USE OF THE SOFTWARE WILL NOT INFRINGE ANY
# PATENT, COPYRIGHT, TRADEMARK, OR OTHER PROPRIETARY RIGHTS, OR THAT THE SOFTWARE WILL  
# ACCOMPLISH THE INTENDED RESULTS OR THAT THE SOFTWARE OR ITS USE WILL NOT RESULT IN INJURY
# OR DAMAGE.  The user assumes responsibility for all liabilities, penalties, fines, claims,
# causes of action, and costs and expenses, caused by, resulting from or arising out of, in
# whole or in part the use, storage or disposal of the SOFTWARE.
# 
# ****************************************************************************************************************
#

import logging
import sys
import json
import requests
from csv import DictReader
from StringIO import StringIO

from volttron.platform.vip.agent import Agent, Core, PubSub
from volttron.platform.agent import utils
from master_driver.interfaces import BaseInterface, BasicRevert, BaseRegister
from gevent.ares import result


utils.setup_logging()
_log = logging.getLogger(__name__)


class Register(BaseRegister):
    
    
    def __init__(self, read_only, volttron_point_name, units, description, point_name):
        
        super(Register, self).__init__("byte",
                                       read_only,
                                       volttron_point_name,
                                       units,
                                       description=description)
        self.path = point_name
        
        
        
class Interface(BasicRevert, BaseInterface):
    
    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        self.data = []
        self.url = ''


    def configure(self, config_dict, registry_config_str=''):
        
        self.url = config_dict['device_address']
        self.hassClimate = HASSClimate(self.url)
        self.GetData()
        self.register_components_information()
        
    
    
    def GetData(self):
        '''
            Get the current state for loaded components
            from Home Assistant API
        '''
        urlStates = self.url+'states'
        
        try:
            
            self.data = requests.get(urlStates).json()
                    
        except requests.exceptions.RequestException as e:
            print(e)        
    
    
    
    def register_components_information(self):
        '''
            Registers the information about  components loaded on HASS API
        '''
        
        msg = []
        
        self.GetData()
        
        try:
            
            if(self.data == []):
                
                msg = "No data was received from HASS API, Please check the connection to the API and the Agent configuration file"
                _log.error(msg)
                
            else: 
                
                msg = []
                
                for entry in self.data:
                   
                    entityId = entry['entity_id']
                    #print entry
################################################################################################################################################################

                    if(entityId.startswith("climate.")):
                        '''
                            registers data about the climate device with entity ID
                        '''
                        msg =  entry['attributes']
                        climatePointName = 'climate#' + entityId + '#'
                        
                        for key,value in msg.items():
                            
                            if key == "away_mode":
                                self.register_device(False, climatePointName + key, 'string','Shows the away mode value')
                            elif key == "operation_mode":
                                self.register_device(False, climatePointName + key, 'string','Shows the operation mode value')
                            elif key == "operation_list":
                                self.register_device(False, climatePointName + key, 'string','Shows the operation mode list value')
                            elif key == "fan_mode":
                                self.register_device(False, climatePointName + key, 'string','Shows the fan mode value')
                            elif key == "fan_list":
                                self.register_device(False, climatePointName + key, 'string','Shows the fan mode list value')
                            elif key == "swing_mode":
                                self.register_device(False, climatePointName + key, 'string','Shows the swing mode value')  
                            elif key == "swing_list":
                                self.register_device(False, climatePointName + key, 'string','Shows the swing mode list value')
                            elif key == "aux_heat":
                                 self.register_device(False, climatePointName + key, 'string','Shows the aux heat value value')
                            elif key == "state":
                                self.register_device(False, climatePointName + key, 'string','Shows the max state value')
                            elif key == "friendly_name":
                                self.register_device(False, climatePointName + key, 'string','Shows the friendly_name value')
                            elif key == "unit_of_measurement":
                                self.register_device(False, climatePointName + key, 'string','Shows the temperature unit of measurement')
                            elif key == "current_temperature":
                                self.register_device(False, climatePointName + key, 'float','Shows the current temperature value')
                            elif key == "temperature":
                                self.register_device(False, climatePointName + key, 'float','Shows the temperature value')
                            elif key == "max_temp":
                                 self.register_device(False, climatePointName + key, 'float','Shows the maximum temperature value')
                            elif key == "min_temp":
                                self.register_device(False, climatePointName + key, 'float','Shows the minimum temperature value')
                            elif key == "temperature":
                                self.register_device(False, climatePointName + key, 'float','Shows the target temperature value')
                            elif key == "target_temp_low":
                                self.register_device(False, climatePointName + key, 'float','Shows the target temperature low value')                            
                            elif key == "target_temp_high":
                                self.register_device(False, climatePointName + key, 'float','Shows the target temperature high value')
                            elif key == "max_temp":
                                self.register_device(False, climatePointName + key, 'float','Shows the maximum temperature value')
                            elif key == "min_temp":
                                self.register_device(False, climatePointName + key, 'float','Shows the minimum temperature value')
                            
################################################################################################################################################################
                                
        except requests.exceptions.RequestException as e:
            print(e)   
     
    
    def register_device(self, read_only, point_name, units,description):
            '''
                Register the information about the point name
            '''
            register = Register(
                read_only,
                point_name,
                units,
                description,
                point_name)

            self.insert_register(register)
            
   
    def get_point(self, point_name, **kwargs):
        '''
            returns the value for the point_name
        '''
        
        pointNameInfo = point_name.split('#')
        if(len(pointNameInfo) < 3):
            _log.error("invalid point_name format")
            return 
        
        val = self.get_point_name_value(pointNameInfo[0], point_name)

        return str(val)
    
                    
    def get_point_name_value(self, component_type, point_name):
        '''
            Get the current value for loaded point_name
            with component type loaded on  Home Assistant API
        '''      

        msg = []
        
        self.GetData()
        
        try:
            
            if(self.data == []):
                
                msg = "No data was received from HASS API, Please check the connection to the API and the Agent configuration file"
                _log.error(msg)
                
            else: 
                
                msg = []
                
                pointNameInfo =  point_name.split('#')
                if(len(pointNameInfo) < 3):
                    _log.error("invalid point_name format")
                    return 
                
                entityId = pointNameInfo[1]
                property= pointNameInfo[2]
                
                for entry in self.data:
                   
                    if entityId == entry['entity_id']:
                        deviceInfo =  entry['attributes']
                        if(property in deviceInfo):
                            
                            if(property == 'unit_of_measurement'):
                                return deviceInfo[property].encode('utf8')
                            
                            return deviceInfo[property]
                        else:
                            return "N/A"
                        
        except requests.exceptions.RequestException as e:
            print(e)
            

    def _set_point(self, point_name, value, **kwargs):
        '''
            sets the value for the point_name
        '''
        
        pointNameInfo = point_name.split('#')
        if(len(pointNameInfo) < 3):
            _log.error("invalid point_name format")
            return 
        
        componentType = pointNameInfo[0]
        entityId = pointNameInfo[1]
        property = pointNameInfo[2]
        
        if (componentType == "climate"):
            
            if property == "away_mode":
                self.hassClimate.SetAwayMode(entityId, value)
                return str(value)
            
            elif property == "aux_heat":
                self.hassClimate.SetAuxHeat(entityId,value)
                return str(value)
            
            elif property == "fan_mode":
                self.hassClimate.SetFanMode(entityId, value)
                
            elif property == "swing_mode":
                self.hassClimate.SetSwingMode(entityId, value)
                
            elif property == "operation_mode":
                self.hassClimate.SetOperationMode(entityId, value)
                 
            elif property == "temperature":
                pointNamePrefix = pointNameInfo[0] + '#' + pointNameInfo[1] + '#'
                operation_mode = self.get_point(pointNamePrefix + 'operation_mode')
                self.hassClimate.SetTargetTemperature(entityId, value, operation_mode)
                return str(value)
            
            elif property == "target_temp_low":
                pointNamePrefix = pointNameInfo[0] + '#' + pointNameInfo[1] + '#'
                operation_mode = self.get_point(pointNamePrefix + 'operation_mode')
                self.hassClimate.SetSetPointLow(entityId, value, operation_mode)
                return str(value)
            
            elif property == "target_temp_high":
                pointNamePrefix = pointNameInfo[0] + '#' + pointNameInfo[1] + '#'
                operation_mode = self.get_point(pointNamePrefix + 'operation_mode')
                self.hassClimate.SetSetPointHigh(entityId, value, operation_mode)
                return str(value)   
            

    def _scrape_all(self):
        results = {}
        for point in self.point_map.keys():
            print(point)
            results[point] = self.get_point(point)
            
            
        return results


class HASSClimate(object):
    
    
    def __init__(self, url):
        
        self.url = url

        
    def SetTargetTemperature(self, entityId, targetTemp, opMode):
        '''
            Sets temperature value for  target temperature
            for  the climate.entityId device in operation mode opMode
        '''
        
        if targetTemp is None or (targetTemp == "N/A"):
            return
        
        urlServices = self.url+'services/climate/set_temperature'
        
        try:   
            jsonMsg = json.dumps({"entity_id" : entityId, "temperature": targetTemp, "operation_mode":  opMode})
            
            header = {'Content-Type': 'application/json'}
            
            requests.post(urlServices, data = jsonMsg, headers = header)
            
        except requests.exceptions.RequestException as e:
            print(e)
            
            
    def SetSetPointLow(self, entityId, setPointLow,  opMode):
        '''
            Sets temperature value for set point low
            for  the climate.entityId device at operation mode
        '''
        
        if setPointLow is None or setPointLow == "N/A":
            return
        
        urlServices = self.url+'services/climate/set_temperature'
        
        try:   
            jsonMsg = json.dumps({"entity_id" : entityId, "target_temp_low":setPointLow, "operation_mode":  opMode})
            
            header = {'Content-Type': 'application/json'}
            
            requests.post(urlServices, data = jsonMsg, headers = header)
            
        except requests.exceptions.RequestException as e:
            print(e)
            
            
    def SetSetPointHigh(self, entityId, setpointHigh, opMode):
        '''
            Sets temperature value for set point high for  the climate.entityId device
            in current operation mode
        '''
        
        if setpointHigh is None or setpointHigh == "N/A":
            return
        
        urlServices = self.url+'services/climate/set_temperature'
        
        try:   
            jsonMsg = json.dumps({"entity_id" : entityId, "target_temp_high": setpointHigh, "operation_mode":  opMode})
            
            header = {'Content-Type': 'application/json'}
            
            requests.post(urlServices, data = jsonMsg, headers = header)
            
        except requests.exceptions.RequestException as e:
            print(e)
        
        
        
    def SetFanMode(self, entityId, fanMode):
        '''
            Sets fan mode value for the climate.entityId device
        '''
        
        if fanMode is None:
            return
        
        urlServices = self.url+'services/climate/set_fan_mode'
        
        try:
            
            jsonMsg = json.dumps({"entity_id" : entityId, "fan": fanMode})
            
            header = {'Content-Type': 'application/json'}
            
            requests.post(urlServices, data = jsonMsg, headers = header)

        except requests.exceptions.RequestException as e:
            print(e)
            
            
            
    def SetOperationMode(self, entityId, opMode):
        '''
            Sets operation mode value for the climate.entityId device
        '''
        
        if opMode is None:
            return
        
        urlServices = self.url+'services/climate/set_operation_mode'
        
        try:
            
            jsonMsg = json.dumps({"entity_id" : entityId, "operation_mode": opMode})
            
            header = {'Content-Type': 'application/json'}
            
            requests.post(urlServices, data = jsonMsg, headers = header)
            
        except requests.exceptions.RequestException as e:
            print(e)
            
            

    def SetAuxHeat(self, entityId, auxHeatOn):
        '''
            Turn aux heat on/ off for the climate.entityId device
        '''
        
        if auxHeatOn is None:
            return
        
        urlServices = self.url+'services/climate/set_aux_heat'
        
        try:
            
            jsonMsg = json.dumps({"entity_id" : entityId, "aux_heat": auxHeatOn})
            
            header = {'Content-Type': 'application/json'}
            
            requests.post(urlServices, data = jsonMsg, headers = header)
            
        except requests.exceptions.RequestException as e:
            print(e)
            
        
            
    def SetAwayMode(self, entityId, awayMode):
        '''
            Sets away mode value for the climate.entityId device
        '''
        
        if awayMode is None:
            return
        
        urlServices = self.url+'services/climate/set_away_mode'
        
        try:
            
            jsonMsg = json.dumps({"entity_id" : entityId, "away_mode": awayMode})
            
            header = {'Content-Type': 'application/json'}
            
            requests.post(urlServices, data = jsonMsg, headers = header)
            
        except requests.exceptions.RequestException as e:
            print(e)
            
            
  
    def SetHumidityValue(self, entityId, humidityValue):
        '''
            Sets the humidity value for the climate.entityId device
        '''
        
        if humidityValue is None:
            return
        
        urlServices = self.url+'services/climate/set_humidity'
        
        try:
            
            jsonMsg = json.dumps({"entity_id" : entityId, "humidity": humidityValue})
            
            header = {'Content-Type': 'application/json'}
            
            requests.post(urlServices, data = jsonMsg, headers = header)
            
        except requests.exceptions.RequestException as e:
            print(e)
            
            
           
    def SetSwingMode(self, entityId, swingMode):
        '''
            Sets swing mode value for the climate.entityId device
        '''
        
        if swingMode is None:
            return
        
        urlServices = self.url+'services/climate/set_swing_mode'
        
        try:
            
            jsonMsg = json.dumps({"entity_id" : entityId, "swing_mode": swingMode})
            
            header = {'Content-Type': 'application/json'}
            
            requests.post(urlServices, data = jsonMsg, headers = header)
            
        except requests.exceptions.RequestException as e:
            print(e)
            
            
            
