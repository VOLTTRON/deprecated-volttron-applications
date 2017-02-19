#!env/bin/python
import sys
import logging
from volttron.platform.messaging import headers as headers_mod, topics
from volttron.platform.vip.agent import Agent, PubSub, Core, RPC
from volttron.platform.agent import utils
import datetime
import common

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = "0.1"

class FncsProxy(Agent):
    
    def __init__(self, **kwargs):
        super(FncsProxy,self).__init__(**kwargs)
        
    @Core.receiver('onstart')
    def start(self, sender, **kwargs):
        fncsDevicesTopic = common.FNCS_DEVICES()
        self.vip.pubsub.subscribe(peer = 'pubsub',
                                  prefix = fncsDevicesTopic,
                                  callback = self.onmessage).get(timeout=5)

    def onmessage(self, peer, sender, bus, topic, headers, message):
        # listen to fncs/output/devices
        # publish to devices
        devices_topic = topic.replace('fncs/output/devices/unit/',
                'devices/campus/building/unit/')
        self.vip.pubsub.publish('pubsub', devices_topic, headers, message).get(timeout=5)
        _log.debug('fncs/output/devices -> devices:\ntopic: %s\nmessage: %s'%(devices_topic, str(message)))
    
    @RPC.export
    def set_point(self, requester_id, topic, value, **kwargs):
        # publishes to the fncs/input/ subtopic for information
        # that goes to the bridge to pass to fncs message bus
        fncsInputTopic = common.FNCS_INPUT_PATH(path = topic)#this assumes topic starts with /devices/
        utcnow = datetime.datetime.utcnow()
        fncsHeaders = {}
        fncsHeaders['time'] = utils.format_timestamp(utcnow)
        if requester_id is not None:
            fncsHeaders['requesterID'] = requester_id
        self.vip.pubsub.publish('pubsub', fncsInputTopic, fncsHeaders, value).get(timeout=5)
        _log.debug('set_point -> fncs/input/topic:\ntopic: %s\nMessage: %s'%(fncsInputTopic, str(value)))
        return value
    
    @RPC.export
    def request_new_schedule(self, requester_id, task_id, priority, requests):
        # actuator stubb that needs to return success
        result = {'result' : 'SUCCESS',
                  'data' : {},
                  'info' : ''} 
        return result

    
    @RPC.export
    def request_cancel_schedule(self, requester_id, task_id):
        # actuator stub that needs to return success
        result = {'result' : 'SUCCESS',
                  'data' : {},
                  'info' : ''} 
        return result

    
def fncs_proxy(**kwargs): 
    return FncsProxy(identity='platform.actuator')


def main():
    '''Main method to start the agent'''
    utils.vip_main(fncs_proxy)
    
if  __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
