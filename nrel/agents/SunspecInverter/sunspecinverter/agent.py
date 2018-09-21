# Copyright  2017 Alliance for Sustainable Energy, LLC
#
# This computer software was produced by Alliance for Sustainable Energy, LLC
# under Contract No. DE-AC36-08GO28308 with the U.S. Department of Energy.
#
# For 5 years from the date permission to assert copyright was obtained, the
# Government is granted for itself and others acting on its behalf a nonexclusive,
# paid-up, irrevocable worldwide license in this software to reproduce, prepare
# derivative works, and perform publicly and display publicly, by or on behalf of
# the Government. There is provision for the possible extension of the term of
# this license. Subsequent to that period or any extension granted, the Government
# is granted for itself and others acting on its behalf a nonexclusive, paid-up,
# irrevocable worldwide license in this software to reproduce, prepare derivative
# works, distribute copies to the public, perform publicly and display publicly,
# and to permit others to do so. The specific term of the license can be
# identified by inquiry made to Contractor or DOE.
#
# NEITHER ALLIANCE FOR SUSTAINABLE ENERGY, LLC, THE UNITED STATES NOR
# THE UNITED STATES DEPARTMENT OF ENERGY, NOR ANY OF THEIR EMPLOYEES,
# MAKES ANY WARRANTY, EXPRESS OR IMPLIED, OR ASSUMES ANY LEGAL LIABILITY
# OR RESPONSIBILITY FOR THE ACCURACY, COMPLETENESS, OR USEFULNESS OF ANY DATA,
# APPARATUS, PRODUCT, OR PROCESS DISCLOSED, OR REPRESENTS THAT ITS USE WOULD
# NOT INFRINGE PRIVATELY OWNED RIGHTS.

# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

"""
This module controls a Sunspec Inverter.
"""

# !/usr/local/bin/python

import sys
import logging
import time
from datetime import datetime
import xmltodict
import requests
from OpenSSL import crypto

from helper import *
from DER import DERProgramList,DERControlBase
from TLS import Certificate_Mgmt
from Device import Inverter
from utilities import *

from volttron.platform.agent.utils import jsonapi
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.vip.agent import Agent, Core, RPC
from volttron.platform.vip.agent import *

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '4.0'
poll_interval = 600
pub_interval = 600


class SunspecAgent(Agent):
    def __init__(self, config_path, **kwargs):
        #TODO: cretae guid, lfid and sfid
        super(SunspecAgent, self).__init__(**kwargs)
        print("Init function called")
        config = utils.load_config(config_path)
        self.inverter = Inverter(config['device_type'], config['slave_id'], config['name'], config['pathlist'], config['baudrate'], config['parity'], config['ip'], config['port'], config['timeout'] )
        self.pin = config['pin']
        self.inverter_name = config['Inverter Name']
        self.server_ip = config['server_IP']
        self.server_port = config['server_port']
        self.device_capability_link = config['device_capability_link']
        self.poll_interval = 300
        self.DERPgm_list = None
        self.DER_list = None
	self.EndDev = None
        self.poll_list = []

    def create_cert(self):
        Cert = Certificate_Mgmt()
        Cert.cakey = Cert.createKeyPair(crypto.TYPE_RSA, 2048)
        Cert.careq = Cert.createCertRequest(Cert.cakey, CN='Certificate Authority')
        # CA certificate is valid for five years.
        Cert.cacert = Cert.createCertificate(Cert.careq, (Cert.careq, Cert.cakey), 0, (0, 60*60*24*365*5))


        with open('certificates/CA.pkey', 'w') as capkey:
            capkey.write(
                crypto.dump_privatekey(crypto.FILETYPE_ASN1, Cert.cakey).decode('utf-8')
            )

        print('Creating Certificate Authority certificate in "simple/CA.cert"')
        with open('certificates/CA.cert', 'w') as ca:
            ca.write(
                crypto.dump_certificate(crypto.FILETYPE_ASN1, Cert.cacert).decode('utf-8')
            )

    def initialize_comm(self):
        self.DevCap = DeviceCapability(self.device_capability_link)
        self.EndDev = EndDevice(self.DevCap.EndDeviceLink, self.inverter)
        for fsa in self.EndDev.FSAList.FSAs:
            global poll_interval
            poll_interval = fsa.DERProgramList.pollRate
            break

        self.DERControlBase = DERControlBase(self.inverter,{})
        self.DER_list = self.EndDev.DERList
	print("all classes init")

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        self.initialize_comm()

    @Core.receiver('onstop')
    def close_con(self,sender, **kwargs):
        if self.inverter is not None:
            self.inverter.close()

    @Core.periodic(60*10)
    def push_updates(self, **kwargs):
	if self.DER_list is not None:
	   self.DER_list.push_updates()

    @Core.periodic(poll_interval)
    def poll_controls(self, **kwargs):
	if self.EndDev is not None:
	   for fsa in self.EndDev.FSAList.FSAs:
            	fsa.DERProgramList.poll()
        
    @RPC.export
    def get_device_values(self, map):
        #Function for interface
        attr = map[0]
        package_type = map.get(attr)
        control_val = {
            'DER_Control': self.DERControlBase[attr],
            'DER_Availability': self.DER_list.DERAvailability[attr],
            'DER_Settings': self.DER_list.DERSettings[attr],
            'DER_Status': self.DER_list.DERStatus[attr],
            'DER_Capability': self.DER_list.DERCapability[attr]         
        }
        result = {attr: control_val[package_type]()}
        if result[attr] == None:
            _log.warning("Set value before reading")
        return result
        
    @RPC.export
    def set_device_values(self, map):
        if package_type == 'DER_Control':
            self.DERControlBase.set_controls(attr)
        else:
            _log.info("Not writable")
        
    def dict_control_values(self, map):
        control_stat = {}
        for k,v in map.items():
            control_stat[k] = self.get_device_values({k,v})
        return control_stat
    

def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.vip_main(SunspecAgent)

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass

