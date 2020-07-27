#Interface to the Masterdriver agent
from master_driver.interfaces import BaseInterface, BaseRegister
from master_driver.driver_exceptions import DriverConfigError
from volttron.platform.vip.agent import errors
from csv import DictReader
from StringIO import StringIO
import logging


class Register(BaseRegister):
    def __init__(self, control_type, read_only, pointName, units, description = ''):
        '''
        read_only - True or False
        register_type - "bit" or "byte", used by the driver sub-agent to help deduce some meta data about the point.
        point_name - Name of the point on the device. Used by the base interface for reference.
        units - units of the value, meta data for the driver
        description - meta data for the driver
        python_type - python type of the point, used to produce meta data. This must be set explicitly otherwise it default to int.
        '''
        super(Register, self).__init__("byte", read_only, pointName, units, description = '')
        self.control_type = control_type
        self.read_only = read_only
        self.pointName = pointName
        self.description = description
        self.units = units
        self.value = 0

class Interface(BaseInterface):
    def __init(self):
	print("Sunspec interface initiated")

    def configure(self, config_dict, registry_config_str):
        self.device_address = config_dict['device_address']
        self.agent_id = config_dict['agent_id']
        for controls in registry_config_str:
        	self.parse_config(registry_config_str)

    def parse_config(self, config_string):
        if config_string is None:
            return

        f = StringIO(config_string) #Python's CSV file parser wants a file like object.

        configDict = DictReader(f) #Parse the CVS file contents.

        for regDef in configDict:
            read_only = regDef['Writable'].lower() != 'true'
            point_name = regDef['Volttron Point Name']
            description = regDef['Notes']
            units = regDef['Units']
            control_type = regDef['Control Type']
            register = Register(control_type, read_only, point_name, units, description = description)

            self.insert_register(register)

    def get_point(self, point_name):
        '''
        Gets the value of a point from a device and returns it.
        The Register instance for the point can be retrieved with self.get_register_by_name(point_name)
        Failure should be indicated by a useful exception being raised
        '''
        register = self.get_register_by_name(point_name)
        point_map = {point_name:[register.control_type]}

        result = self.vip.rpc.call(self.agent_id, 'get_device_values', point_map).get() 
        self.get_register_by_name(point_name).value = result['value']
        return result[point_name]

    def set_point(self, point_name, value):
        '''
        Sets the value of a point on a device and ideally returns the actual value set if different.
        Failure should be indicated by a useful exception being raised
        '''
        register = self.get_register_by_name(point_name)
        if register.read_only:
            raise  IOError("Trying to write to a point configured read only: "+point_name)
        args = [register.point_name, value, register.control_type]
        result = self.vip.rpc.call(self.agent_id, 'set_device_values', *args).get()
        self.get_register_by_name(point_name).value = result['value']
        return result

    def scrape_all(self):
        '''
        This must return a dictionary mapping point names to values for ALL registers.
        '''
        point_map = {}
        read_registers = self.get_registers_by_type("byte", True)
        write_registers = self.get_registers_by_type("byte", False)
        for register in read_registers + write_registers:
            point_map[register.point_name] = [register.control_type]

        result = self.vip.rpc.call(self.agent_id, 'dict_device_values', point_map).get()
        return result

    
    def revert_all(self, priority=None):
        """Revert entrire device to it's default state"""
        write_registers = self.get_registers_by_type("byte", False)
        for register in write_registers:
            self.revert_point(register.point_name, priority=priority)

    def revert_point(self, point_name, priority=None):
        """Revert point to it's default state"""
        self.set_point(point_name, None, priority=priority)
