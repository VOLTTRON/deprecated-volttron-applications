# !/usr/local/bin/python

import logging 
import sunspec.core.client as client
import sunspec.core.util as util
from sunspec.core.client import SunSpecClientError

from volttron.platform.vip.agent import *
from volttron.platform.agent import utils

utils.setup_logging()
_log = logging.getLogger(__name__)

DEBUG = True

class Inverter(object):
    def __init__(self, conn_type=None, slave_id=126, name=None, pathlist=None, baudrate=None, parity=None, ip=None, port=None, timeout=60, trace=False):
        '''
        Creates an Sunspec client instance to communicate with the Inverter
        '''
        self.device = None        
        try:
            conn = client.TCP
            if conn_type == "TCP":
                conn = client.TCP
            elif conn_type == "RTU":
                conn = client.RTU
            elif conn_type == "MAPPED":
                conn = client.MAPPED
            if not DEBUG:
		self.device = client.SunSpecClientDevice(conn,slave_id, name, pathlist, baudrate, parity, ip, port, timeout, trace)
		self.model_map = self.get_device_models()
		_log.info("Available models in the inverter: %s"%self.device.models)

        except SunSpecClientError,s:
            if device_type == client.MAPPED:
                _log.error("Map file required")
            else:
                _log.error("Inverter failed to initialize%s"%s)
            

    def refresh_values(self):
        '''
        Refreshes all the parameters by reading the current status of the inverter
        '''
        if self.device == None:
            return "Inverter not initialized"
        try:
            self.device.read()
        except SunSpecClientError,s:
            print(s)
        
    def get_device_models(self):
        '''
        Returns a dictionary of model id number and object
        '''
        if self.device is not None:
            return self.device.device.models

    def get_model_points(self,model):
        '''
        Returns the list of points available in the model
        '''
        if self.device is not None:
            point_list = model.points_list
            return [x.sf_point for x in point_list] 

    def read_point(self, model_name, point_name):
	'''
	Read a point of the model 
	'''
        if self.device is None:
            return "Inverter not initialized"

        if hasattr(self.device, model_name):
            model = getattr(self.device, model_name)
            self.refresh_values()
            if hasattr(model, point_name):
                value = getattr(model, point_name)
                return value
            else:
                _log.warning("Invalid point")
        else:
            _log.warning("%s is not supported by this device"%model)

    def write_point(self, model_name, point_name, value):
	'''
	Write to a point on the model 
	'''
        if self.device is None:
            return "Inverter not initialized"
        try:
            if hasattr(self.device, model_name):
                model = getattr(self.device, model_name)
                if hasattr(model, point_name):
                    setattr(model, point_name, value)
                else:
                    _log.warning("Please check the point name")
            else:
                _log.warning("%s is not an model of this device"%model)
        except SunSpecClientError,s:
            _log.error(s)

    def close(self):
	'''
	Close connection to the device
	'''
        self.device.close()
