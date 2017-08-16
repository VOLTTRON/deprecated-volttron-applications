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

from volttron.platform.vip.agent import Agent, Core, PubSub
from volttron.platform.agent import utils
from . import settings

import requests

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.0'
record_topic = 'record/'

class HASSLockAgent(Agent):
    
    
    def __init__(self, config_path, **kwargs):
        '''
            Initializes the HASS Lock Agent for communicating with HASS API
            regarding lock components
        '''
        
        super(HASSLockAgent, self).__init__(**kwargs)
        
        self.config = utils.load_config(config_path)
        self.agentId = self.config['agentId']
        self.hassConfig = self.config['hassConfigPath']
        self.url = self.config['url']
        self.urlPass = self.config['urlPass'] 
        self.data  = []
        
        self.GetData()
        
        
        
    @PubSub.subscribe('pubsub', record_topic + 'hass/lock/')
    def on_match(self, peer, sender, bus,  topic, headers, message):
        '''
        subscribes to the messages received from HASS Agent about the lock components loaded on HASS API
        '''
        
        #For testing purposes only print the messages for now
        print('Peer: {0}, Sender: {1}:, Bus: {2}, Topic: {3}, Headers: {4}, Message: {5}'.format
              (peer, sender, bus, topic, headers, message))  
        
        
    
    def on_publish_topic(self):
        '''
            Publishes the information about lock components loaded on HASS API
        '''
        
        msg = []
        
        self.GetData()
        
        try:
            
            if(self.data == []):
                
                msg = "No data was received from HASS API, Please check the connection to the API and the Agent configuration file"
                
                self.vip.pubsub.publish(peer = 'pubsub',
                                topic = record_topic + 'hass/error',
                                message = msg,
                                headers = {'AgentId':self.agentId}).get(timeout=10)
            
            else: 
                
                msg = []
                
                for entry in self.data:
                   
                    entityId = entry['entity_id']
                    
                    if(entityId.startswith("lock.")):
                        '''
                            publishes data about lock device
                        '''
                        msg =  entry['attributes']
                        
                        self.vip.pubsub.publish(peer = 'pubsub',
                                topic = record_topic + 'hass/lock/' + entityId,
                                message = msg,
                                headers = {'AgentId':self.agentId}).get(timeout=10)              
                                
        except requests.exceptions.RequestException as e:
            print(e)



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
            
            
            
    def Lock(self, entityId, lockCode):
        '''
            Locks the lock.entityId device
        '''
        
        if lockCode is None:
            return
        
        urlServices = self.url+'services/lock/lock'
        
        try:
            
            jsonMsg = json.dumps({"entity_id" : entityId, "code": lockCode})
            
            header = {'Content-Type': 'application/json'}
            
            requests.post(urlServices, data = jsonMsg, headers = header)
            
            self.on_publish_topic()
            
        except requests.exceptions.RequestException as e:
            print(e)
        
        
        
    def Unlock(self, entityId, unlockCode):
        '''
            Unlocks the lock.entityId device
        '''
        
        if lockCode is None:
            return
        
        urlServices = self.url+'services/lock/unlock'
        
        try:
            
            jsonMsg = json.dumps({"entity_id" : entityId, "code": unlockCode})
            
            header = {'Content-Type': 'application/json'}
            
            requests.post(urlServices, data = jsonMsg, headers = header)
            
            self.on_publish_topic()
            
        except requests.exceptions.RequestException as e:
            print(e)    
            
            
                                         
def main(argv=sys.argv):
    '''Main method called by the platform.'''
    utils.vip_main(HASSClimateAgent,version=__version__)



if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass                 
