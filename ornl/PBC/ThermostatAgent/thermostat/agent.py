from datetime import datetime
import logging
import sys
import tstat_scan
import time
import gevent
import signal
import os
from settings import settings

from volttron.platform.vip.agent import Agent, PubSub, Core, RPC, Unreachable
from volttron.platform.agent import utils
from volttron.platform.keystore import KeyStore

utils.setup_logging()
Log = logging.getLogger(__name__)

ks = KeyStore()

class Thermostat_Agent(Agent):

	def __init__(self, config_path, **kwargs):
		super(Thermostat_Agent, self).__init__(**kwargs)

                self.cwd = os.getcwd()
		
		self.Config = utils.load_config(config_path)
		self.numNodes = self.Config["numNodes"]
		self.zonenum = self.Config["zonenum"]
		self.coord_status = 0
		self.local_status = 0
		self.user_mode = settings[0]

		#create link to local thermostat
		try:
			self.instance = tstat_scan.tstat(self.zonenum)

		except Exception:
			Log.exception("broken connection to device")

		#local control if set to 1
		#coordinated control if set to 0
		self.local_control =  settings[2]

		#tstats are autoset to 1 initially
		#seperate var helps with scheduler auto setting to coordinated
		#has to do with coord control dropping to local when units
		#drops below threshold
		self.usr_local_control = settings[2] 
		
		#Keep track of timings for scheduling agents
		self.timecheck = []
		for i in range(0,self.numNodes):
			self.timecheck.append(time.time())

		##Leader list for scheduler agents
		self.leader = []
		for i in range(0,self.numNodes):
			self.leader.append(999)

		##Collection of all platforms on network
                self.platforms=[]
                for i in range(0,self.numNodes):
                        self.platforms.append(0)

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

	##Open a connection to an external platform on network
	##IP addresses contained in config file
        def remote_setup(self, node):
                if(node == self.zonenum):
                        return

                else:
                        try:
                                Log.info("Connecting to Zone: " + str(node))
                                masterVIP = (self.Config["masternode_z"+str(node)] 
							+ "?serverkey=" + self.Config["serverkey_z"+str(node)] 
							+ "&publickey=" + ks.public + "&secretkey=" + ks.secret)

                                event = gevent.event.Event()
                                masternode = Agent(address=masterVIP, enable_store=False, 
							identity=self.Config["identity"])
                                masternode.core.onstart.connect(lambda *a, **kw: event.set(),event)
                                gevent.spawn(masternode.core.run)
                                event.wait(timeout=5)
                                self.platforms[node-1] = masternode

                        except gevent.Timeout:
                                Log.exception("Platform Connection Timeout")

	###Subsribe to leader channel heartbeat
	@PubSub.subscribe('pubsub','leader')
	def leader_check(self, peer, sender, bus, topic, headers, message):

		self.leader[headers["Zone"]-1] = message

		self.timecheck[headers["Zone"]-1] = time.time()
		
		#To reset leader after time threshold(10 scan periods) is passed
                for idx,drop_time in enumerate(self.timecheck):
			if time.time() - drop_time > 60:
				self.leader[idx] = 999

		self.leader_sorted = sorted(self.leader)

		#if no leader available, swictch to local control
		if self.leader_sorted[0]==999:
			self.local_status=1

	###Publish data from thermostats to bus
	@Core.periodic(15)
	def publish_poll(self):

		poll = self.instance.poll_request()

                Log.info("POLL DATA (Z" + str(self.zonenum)+": " + str(poll))
		
		headers = {'Zone': self.zonenum}

		for idx,platform in enumerate(self.platforms):

			if idx+1 == self.zonenum:
				try:
                                        self.vip.pubsub.publish('pubsub', 'poll', headers, poll)

                                except Exception:
                                        Log.error('failed to publish to local bus')
                        
			##connection timeouts
                        elif(not platform and (time.time() - self.platform_timeouts[idx]) <=30):
                                continue
                        elif(not platform and (time.time()-self.platform_timeouts[idx])>30):
                                self.remote_setup(idx+1)

                        else:
                                Log.info('attempting publish to external platforms: Zone '+str(idx+1)+'/'+str(len(self.platforms)))

                                with gevent.Timeout(3):
                                        try:
                                                platform.vip.pubsub.publish('pubsub','poll',headers,poll)
                                                time.sleep(0.25)

                                        except NameError:
                                                Log.exception('no data to publish')

                                        except gevent.Timeout:
                                                Log.exception("timeout")

                                                self.platform_timeouts[idx]=time.time()
                                                self.platforms[idx]=0
                                                platform.core.stop()
	
	###Subscribe to the scheduler channel of leader for operating instruction
	###Leader is top of sorted leader list
	@PubSub.subscribe('pubsub','status')
	def pull_control(self, peer, sender, bus, topic, headers, message):
		Log.info('leader rank = ' + str(self.leader_sorted))
		if topic == 'status/z'+str(self.leader_sorted[0]):
                        print("Coordinating Zones")
                        if headers["Zone"] == self.zonenum:
				###Make sure we're collecting info for UI plots
				if message == 'activate' and (self.user_mode =='COOL' or self.user_mode=='HEAT'):
					self.coord_status = 1

					if not self.local_control:
                                       		mode = self.instance.activate()

				elif(message =='shutdown' or self.user_mode=='OFF'):
					self.coord_status = 0
	
					if not self.local_control:
                                        	mode = self.instance.shutdown()


        @PubSub.subscribe('pubsub','local')
        def pull_local_control(self, peer, sender, bus, topic, headers, message):
                if headers["Zone"]==self.zonenum:
			print("LOCAL CONTROL SAYS: " + str(message))
                        if message=='cool1' and self.user_mode =='COOL':
				self.local_status = 1
				if self.local_control:
                               		self.instance.set_mode(-1)
					print("Local Control setting mode to -1")

                        elif message=='cool2' and self.user_mode =='COOL':
				self.local_status = 1
				if self.local_control:
                                	self.instance.set_mode(-2)
					print("Local Control setting mode to -2")

                        elif message=='off' or self.user_mode == 'OFF':
				self.local_status = 0
				if self.local_control:
                                	self.instance.set_mode(0)
					print("Local Control setting mode to 0")
                      
	###Methods used for interfacing with web server
        @RPC.export
        def set_local_control(self,status):
		print("Setting local control to "+str(status))
		self.usr_local_control = int(status)
                self.local_control = self.usr_local_control

		#fix into persistent memory
		settings[2] = self.usr_local_control
		f = open(self.cwd+'/../thermostat/settings.py','w')
		f.write('settings = ' + str(settings))
		f.close()

	@RPC.export
        def read_local(self):
		if self.local_control:
                	return "LOCAL",self.usr_local_control
		elif not self.local_control:
			return "COORDINATING",self.usr_local_control

	@RPC.export
        def read_temp(self):
		temp = self.instance.read_temp()
                return str(temp),str(settings[1])

	@RPC.export
        def read_mode(self):
		mode_dict = {-2:"COOL2",-1:"COOL1",0:"OFF",
				1:"HEAT1",2:"HEAT2"}
		mode = self.instance.get_mode()
		msg = mode_dict[mode]
		msg = str(len(msg))+msg+self.user_mode
		return msg

	@RPC.export
        def set_mode(self,mode):
		self.user_mode =str(mode)

		#fix into persistent memory
		settings[0] = self.user_mode
		f = open(self.cwd+'/../thermostat/settings.py','w')
		f.write('settings = ' + str(settings))
		f.close()

	@RPC.export
        def set_setpoint(self,setpoint):
		self.instance.set_setpoint(float(setpoint))

		#fix into persistent memory
		settings[1] = float(setpoint)
		f = open(self.cwd+'/../thermostat/settings.py','w')
		f.write('settings = ' + str(settings))
		f.close()

	@RPC.export
	def get_coord_state(self):
		return str(self.coord_status)

	@RPC.export
	def get_local_state(self):
		return str(self.local_status)


def main(argv=sys.argv):
	'''Main method called by the eggsecutable.'''
	try:
		utils.vip_main(Thermostat_Agent)
	except Exception as e:
		Log.exception('unhandled exception')


if __name__ == '__main__':
	# Entry point for script
	sys.exit(main())
