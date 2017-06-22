'''
Implemented by Helia Zandi
email: zandih@ornl.gov

This material was prepared by UT-Battelle, LLC (UT-Battelle) under Contract DE-AC05-00OR22725
with the U.S. Department of Energy (DOE). All rights in the material are reserved by DOE on 
behalf of the Government and UT-Battelle pursuant to the contract. You are authorized to use
the material for Government purposes but it is not to be released or distributed to the public.
NEITHER THE UNITED STATES NOR THE UNITED STATES DEPARTMENT OF ENERGY, NOR UT-Battelle, NOR ANY
OF THEIR EMPLOYEES, MAKES ANY WARRANTY, EXPRESS OR IMPLIED, OR ASSUMES ANY LEGAL LIABILITY OR
RESPONSIBILITY FOR THE ACCURACY, COMPLETENESS, OR USEFULNESS OF ANY INFORMATION, APPARATUS, 
PRODUCT, OR PROCESS DISCLOSED, OR REPRESENTS THAT ITS USE WOULD NOT INFRINGE PRIVATELY OWNED RIGHTS.
'''

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
                    
################################################################################################################################################################

                    if(entityId.startswith("climate.")):
                        '''
                            registers data about the climate device with entity ID
                        '''
                        msg =  entry['attributes']
                        climatePointName = 'climate/' + entityId + '/'
                        
                        for key,value in msg.items():
                            
                            if key == "away_mode":
                                self.register_device(False, climatePointName + key, 'string','Shows the away mode value')
                            elif key == "operation_mode":
                                self.register_device(False, climatePointName + key, 'string','Shows the operation mode value')
                            elif key == "fan_mode":
                                self.register_device(False, climatePointName + key, 'string','Shows the fan mode value')
                            elif key == "unit_of_measurement":
                                self.register_device(False, climatePointName + key, 'string','Shows the temperature unit of measurement')
                            elif key == "current_temperatuure":
                                self.register_device(False, climatePointName + key, 'float','Shows the current temperature value')
                            elif key == "aux_heat":
                                 self.register_device(False, climatePointName + key, 'string','Shows the aux heat value value')
                            elif key == "max_temp":
                                 self.register_device(False, climatePointName + key, 'float','Shows the max temperature value')
                            elif key == "min_temp":
                                self.register_device(False, climatePointName + key, 'float','Shows the min temperature value')
                            elif key == "temperature":
                                self.register_device(False, climatePointName + key, 'float','Shows the target temperature value')
                            elif key == "swing_mode":
                                self.register_device(False, climatePointName + key, 'string','Shows the swing mode value')  
                            elif key == "target_temp_low":
                                self.register_device(False, climatePointName + key, 'float','Shows the target temperature low value')                            
                            elif key == "target_temp_high":
                                self.register_device(False, climatePointName + key, 'float','Shows the target temperature high value')
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
        
        pointNameInfo = entityId = point_name.split('/')
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
                
                pointNameInfo =  point_name.split('/')
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
        
        pointNameInfo = point_name.split('/')
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
                
            elif property == "temperature":
                pointNamePrefix = pointNameInfo[0] +'/'+pointNameInfo[1] + '/' + pointNameInfo[2] + '/'
                temp_high = self.get_point(pointNamePrefix + 'target_temp_high')
                temp_low = self.get_point(pointNamePrefix + 'target_temp_low')
                operation_mode = self.get_point(pointNamePrefix + 'operation_mode')
                self.hassClimate.SetTemperature(entityId, temp_low, temp_high, value, operation_mode)
                return str(value)
            
            elif property == "target_temp_low":
                pointNamePrefix = pointNameInfo[0] +'/'+pointNameInfo[1] + '/' + pointNameInfo[2] + '/'
                temperature = self.get_point(pointNamePrefix + 'temperature')
                temp_high = self.get_point(pointNamePrefix + 'target_temp_high')
                operation_mode = self.get_point(pointNamePrefix + 'operation_mode')
                self.hassClimate.SetTemperature(entityId, value, temp_high, temperature, operation_mode)
                return str(value)
            
            elif property == "target_temp_high":
                pointNamePrefix = pointNameInfo[0] +'/'+pointNameInfo[1] + '/' + pointNameInfo[2] + '/'
                temperature = self.get_point(pointNamePrefix + 'temperature')
                temp_low = self.get_point(pointNamePrefix + 'target_temp_low')
                operation_mode = self.get_point(pointNamePrefix + 'operation_mode')
                self.hassClimate.SetTemperature(entityId, temp_low, value, temperature, operation_mode)
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
        
        
        
    def SetTemperature(self, entityId, setPointLow, setpointHigh, targetTemp, opMode):
        '''
            Sets temperature value for set point high, set point low, target temperature
            for  the climate.entityId device
        '''
        
        if setpointHigh is None or setPointLow is None or targetTemp is None:
            return
        
        urlServices = self.url+'services/climate/set_temperature'
        
        try:
            
            jsonMsg = json.dumps({"entity_id" : entityId, "temperature": targetTemp, "target_temp_low":setPointLow, 
                         "target_temp_high": setpointHigh, "operation_mode":  opMode})
            
            header = {'Content-Type': 'application/json'}
            
            requests.post(urlServices, data = jsonMsg, headers = header)
            
            self.on_publish_topic()
            
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
            
            self.on_publish_topic()
            
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
            
            self.on_publish_topic()
            
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
            
            self.on_publish_topic()
            
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
            
            self.on_publish_topic()
            
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
            
            self.on_publish_topic()
            
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
            
            self.on_publish_topic()
            
        except requests.exceptions.RequestException as e:
            print(e)
