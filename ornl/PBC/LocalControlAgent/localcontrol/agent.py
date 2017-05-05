import datetime
import logging
import sys
import gevent
import traceback
import time
from settings import settings
from volttron.platform.vip.agent import Agent, PubSub, Core,RPC,Unreachable
from volttron.platform.agent import utils
from volttron.platform.keystore import KeyStore

utils.setup_logging()
Log = logging.getLogger(__name__)

ks = KeyStore()

class LocalControl_Agent(Agent):

    	def __init__(self, config_path, **kwargs):
		super(LocalControl_Agent, self).__init__(**kwargs)
		self.Config = utils.load_config(config_path)
		self.zonenum = self.Config["zonenum"]
		self.deadband = settings[2]
		self.min_switch_time = settings[1]
		self.setpoint = settings[0]
		
		self.last_switch_time = time.time()

		self.usr_mode = 0


	@Core.periodic(10)
	def compute_control(self):
		
		current_time = time.time()

		temp = self.vip.rpc.call('thermostatz'+str(self.zonenum),'read_temp').get()
		temp = float(temp[0])

                headers = {"Zone":self.zonenum}

		if temp > self.setpoint+self.deadband and temp <= self.setpoint+1 and (current_time-self.last_switch_time) > self.min_switch_time:
			self.vip.pubsub.publish('pubsub', 'local', headers, 'cool1').get(timeout=5)
		
		elif temp > self.setpoint+1 and (current_time-self.last_switch_time) > self.min_switch_time:
			self.vip.pubsub.publish('pubsub', 'local', headers, 'cool2').get(timeout=5)
			self.last_switch_time = time.time()

		elif temp <= self.setpoint + self.deadband and (current_time-self.last_switch_time) > self.min_switch_time:
			self.vip.pubsub.publish('pubsub', 'local', headers, 'off').get(timeout=5)
			self.last_switch_time = time.time()

	@RPC.export
        def set_setpoint(self,setpoint):
		self.setpoint = float(setpoint)

		#fix into persistent memory
		settings[0] = self.setpoint
		f = open('settings.py')
		f.write('settings = ' + str(settings))
		f.close()

	@RPC.export
        def set_mode(self,mode):
		self.usr_mode=mode

def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(LocalControl_Agent)
    except Exception as e:
	Log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
