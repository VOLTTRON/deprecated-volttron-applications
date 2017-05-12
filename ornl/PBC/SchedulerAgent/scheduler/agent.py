import datetime
import logging
import sys
import control
import Tstat6
import gevent
import settings
import traceback
import time
from datetime import datetime
from volttron.platform.vip.agent import Agent, PubSub, Core, RPC, Unreachable
from volttron.platform.agent import utils
from volttron.platform.keystore import KeyStore

utils.setup_logging()
Log = logging.getLogger(__name__)

ks = KeyStore()

class Scheduler_Agent(Agent):

    	def __init__(self, config_path, **kwargs):
		super(Scheduler_Agent, self).__init__(**kwargs)
		self.Config = utils.load_config(config_path)
		self.numNodes = self.Config["numNodes"]
		self.zonenum = self.Config["zonenum"]
		self.control_period = self.Config["control_period"]
		self.maxNodes = self.Config["MaxNodes"]

		self.data = []

		##Collections of poll data
		for i in range(0,self.numNodes):
			self.data.append(None)
		
		##Collection of all platforms on network
                self.platforms=[]
                for i in range(0,self.numNodes):
                        self.platforms.append(0)

		##Times of last message recieved
		self.poll_time = []
		for i in range(0, self.numNodes):
                        self.poll_time.append(time.time())

		##Whether platform is alive or dead
		self.platform_status = []
		for i in range(0, self.numNodes):
                        self.platform_status.append(1)
		
		##Connect to external platforms
                self.platform_timeouts=[]
                for i in range(0,self.numNodes):
                        self.platform_timeouts.append(0)

                for idx,platform in enumerate(self.platforms):

                        if(not platform and (time.time() - self.platform_timeouts[idx]) <=30):
                        	continue

                        elif(not platform and (time.time()-self.platform_timeouts[idx])>30):
                        	self.remote_setup(idx+1)


	##Establish network connection
	def remote_setup(self, z):
                if(z == self.zonenum):
                        return

                else:
                        try:
                                Log.info("Connecting to Zone: " + str(z))
                                VIP = self.Config["modelnode_z"+str(z)] + "?serverkey=" + \
					self.Config["serverkey_z"+str(z)] + "&publickey=" + \
					ks.public + "&secretkey=" + ks.secret
                                event = gevent.event.Event()
                                node = Agent(address=VIP, enable_store=False, identity=self.Config["identity"])
                                node.core.onstart.connect(lambda *a, **kw: event.set(),event)
                                gevent.spawn(node.core.run)
                                event.wait(timeout=5)
                                self.platforms[z-1] = node
				self.platform_status[z-1] = 1

                        except gevent.Timeout:
                                Log.exception("Platform Connection Timeout")
				self.platform_status[z-1] = 0 #note that platform is down


	#Assert alive for leadership
        @Core.periodic(10)
	def leader_assert(self):

		headers = {'Zone' : self.zonenum}
		msg = self.zonenum

                for idx,platform in enumerate(self.platforms):
                        if idx+1 == self.zonenum:
				try:
					self.vip.pubsub.publish('pubsub', 'leader', headers, msg)

				except Exception:
					Log.error('failed to publish to local bus')
                        
                        elif(not platform and (time.time() - self.platform_timeouts[idx]) <=30):
                        	continue

                        elif(not platform and (time.time()-self.platform_timeouts[idx])>30):
                                self.remote_setup(idx+1)

                        else:
                                Log.info('attempting publish to external platforms: Zone '+str(idx+1)+'/'+str(len(self.platforms)))

                                with gevent.Timeout(3):

                                        try:
                                                self.platforms[idx].vip.pubsub.publish('pubsub', 'leader', headers, msg)
                                                time.sleep(0.25)
                                        except NameError:
                                                Log.exception('no data to publish')

                                        except gevent.Timeout:
                                                Log.exception("timeout")

                                                self.platform_timeouts[idx]=time.time()
                                                self.platforms[idx]=0
                                                platform.core.stop()  



	##Pulls poll data posted to bus and compiles into list
	@PubSub.subscribe('pubsub','poll')
	def pull_poll(self, peer, sender, bus, topic, headers, message):
		self.data[headers["Zone"]-1] = message #note the message
		self.poll_time[headers["Zone"]-1] = time.time()	#note the time
		self.platform_status[headers["Zone"]-1] = 1 #note the platform is alive

	##Publish control decisions
	@Core.periodic(60)
	def publish_schedule(self):

        	equip = []

		##check to make sure thermostats are publishing
                for idx,droptime in enumerate(self.poll_time):
                        if time.time()-droptime > 60:
                                Log.info('tstat dropped off network')
                                #dummy report if timed out to keep control going
				self.data[idx] = [idx+1,0,0,0,0]
				
				self.platform_status[idx] = 0 #note time out

		#Aggregate the thermostat scans
		for msgs in self.data:
			try:
				equip.append(Tstat6.Tstat6(msgs[0], msgs[1], msgs[2], 
								msgs[3], msgs[4]))

			except Exception:
				Log.exception('')

                #Run scheduler
                #if data hasnt been gathered yet, equip list wont be populated
                try:
                        status = control.run_scheduler(equip,2)
			             
		except AssertionError:
			_, _, tb = sys.exc_info()
    			traceback.print_tb(tb) # Fixed format
			tb_info = traceback.extract_tb(tb)
			filename, line, func, text = tb_info[-1]
    			Log.info('An error occurred in {} on line {} in statement {}'.format(filename, line, text))

                for idx,platform in enumerate(self.platforms):
                        if idx+1 == self.zonenum:
				try:
					headers = {'Zone' : idx+1}
					self.vip.pubsub.publish('pubsub', 'status/z'+str(self.zonenum), headers, status[idx])

				except Exception:
					Log.error('failed to publish to local bus')
                        
                        elif(not platform and (time.time() - self.platform_timeouts[idx]) <=30):
                        	continue

                        elif(not platform and (time.time()-self.platform_timeouts[idx])>30):
                                self.remote_setup(idx+1)

			else:
                                Log.info('attempting publish to external platforms: Zone '+str(idx+1)+'/'+str(len(self.platforms)))

                                with gevent.Timeout(3):

                                        try:
                                                headers = {'Zone' : idx+1}                                                
						self.platforms[idx].vip.pubsub.publish('pubsub','status/z'+str(self.zonenum),headers,status[idx])
                                                print("Zone"+str(self.zonenum)+": "+str(status[idx]))
                                                time.sleep(0.25)
                                        except NameError:
                                                Log.exception('no data to publish')

                                        except gevent.Timeout:
                                                Log.exception("timeout")

                                                self.platform_timeouts[idx]=time.time()
                                                self.platforms[idx]=0
                                                platform.core.stop()



def main(argv=sys.argv):
	'''Main method called by the eggsecutable.'''
	try:
		utils.vip_main(Scheduler_Agent)
	except Exception as e:
		Log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
