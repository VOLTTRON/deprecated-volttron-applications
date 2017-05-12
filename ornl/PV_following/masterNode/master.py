import logging
import sys
import os
import os.path as p
import time
import json
import operator
import csv
import datetime
import gevent
import socket
import fcntl
import struct
from zmq.utils import jsonapi
from volttron.platform.vip.agent import *
from volttron.platform.agent.base_historian import BaseHistorian
from volttron.platform.agent import utils
from volttron.platform.messaging import topics, headers as headers_mod

utils.setup_logging()
Log = logging.getLogger(__name__)

def enum(**enums):
    return type('Enum', (), enums)

def get_ip_address(ifname):
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	return socket.inet_ntoa(fcntl.ioctl(
		s.fileno(),
		0x8915,
		struct.pack("256s", ifname[:15])
	)[20:24])
    
class MasterNode(Agent):
	
	class ModelNode:
	    def __init__(self, modelVIP):
                self.ID = modelVIP
		IP="tcp://"+self.ID+":22916"
                self.temp = 306
                self.setpoint = 298
                self.state = 0
                self.delta = self.temp - self.setpoint
                self.agent = Agent(address=IP)
                event = gevent.event.Event()
                self.agent.core.onstart.connect(lambda *a, **kw:event.set(), event)
                gevent.spawn(self.agent.core.run)
                event.wait()
    		
	def __init__(self, config_path, **kwargs):
	    super(MasterNode, self).__init__(**kwargs)
            self.Config = utils.load_config(config_path)
            self.numNodes = self.Config["numNodes"]
            self.AgentStatesEnum = enum(OFF = 0, 
            HEATING_STAGE_ONE =  6, 
            HEATING_STAGE_TWO =  3, 
            COOLING_STAGE_ONE = -3, 
            COOLING_STAGE_TWO = -6)
            self.initTimeStamp = time.time()
    	
	@Core.receiver('onsetup')
	def setup(self, sender, **kwargs):
	    f = os.popen('ifconfig eth0 | grep "inet\ addr" | cut -d: -f2 | cut -d" " -f1')
	    self.agentID = f.read().rstrip() #get_ip_address("eth0")
            self.Nodes = {}
            self.Nsim = 144
            
	    base_dir = p.abspath(p.dirname(__file__))
            regsignal_file = p.join(base_dir,self.Config['data_file'])

    	    # read regulation signal and downsample to 10 mins
    	    with open(regsignal_file, 'rb') as f:
    	    	reader = csv.reader(f)
    	    	Sig = list(reader)

    	    # downsample, 150 steps is 10 mins in this file
    	    self.Reg = []
    	    for i in range(1, 21602, 150):
    	    	self.Reg.append(float(Sig[i][0]))

    	    # initialize index counter for looping through regulation signal
    	    self.i = 0
    	
	#Assert alive for leadership
	@Core.periodic(3)
	def leader_assert(self):
	    headers = {'Zone' : self.agentID}
	    msg = {}
	    msg['ID'] = self.agentID
	    msg['Time'] = time.time()
	    for i in range(0,len(self.Nodes)):
	        node = self.Nodes.values()[i]
	        node.agent.vip.pubsub.publish('pubsub',topic = 'leader', headers = headers , message = msg)
	        Log.info("Leader assertion message is sent")	
	    
    	##Pulls temperatures from the bus
   	@PubSub.subscribe('pubsub','temperature')
   	def pull_temp(self, peer, sender, bus, topic, headers, message):
   	    if message['ID'] in self.Nodes.keys():
   	        node = self.Nodes[message["ID"]]
   	        Log.info("Node already exists")
   	    else:
   	        node = self.ModelNode(message["ID"])
   	        self.Nodes[node.ID] = node
   	        Log.info("Node is added")
   	    node.temp = message['temp']
   	    node.setpoint = message['setpoint']
   	    node.state = message['state']
   	    node.delta = node.temp - node.setpoint 
   	    Log.info("Temperature is read from " + node.ID)
	
	# every 10 seconds run the control!
	@Core.periodic(10)
	def RunControl(self):
	    i = self.i
	    Log.info( "Reg signal index :::::: " + str(i) )
	    for nodekey in self.Nodes:
	        node = self.Nodes[nodekey]
	        if node.temp >= node.setpoint + 1:
	            node.state = self.AgentStatesEnum.COOLING_STAGE_ONE # % decision for bldg j
	        elif node.temp <= node.setpoint - 0.5:
	            node.state = self.AgentStatesEnum.OFF # % decision for bldg j
            	else:
                    node.state = node.state # % decision for bldg j; stay the same
                    Log.info("NODE STATE: "+str(node.state))
	    # sort by deltas ascending
            OrderAsc = sorted(self.Nodes.values(), key=operator.attrgetter('delta'))
            # reverse asc order to get desc order, ordered by highest temp diffrence
            OrderDesc = sorted(self.Nodes.values(), key=operator.attrgetter('delta'), reverse=True)

            # no of buildings reqd to satisfy reg signal,
            # bcoz bldgs go up or down in 3 kw increments, divide by 3 to get no of bldgs
            
            # scale bldgs to regulation signal
            regSignal = self.Reg[i] * len(self.Nodes) * 3
            ReqBld = int(abs(round(regSignal/3.0)))
            Log.info("No of required bldgs: " +str(ReqBld) + ", regulation need of: " + str(self.Reg[i]))

            count = 0
            if self.Reg[i] > 0:
         	# increase power consumption starting with highest temp difference
                for node in OrderDesc:
                    if node.state == self.AgentStatesEnum.OFF:
                        node.state = self.AgentStatesEnum.COOLING_STAGE_ONE
                        count = count + 1
                    elif node.state == self.AgentStatesEnum.COOLING_STAGE_ONE:
                        node.state = self.AgentStatesEnum.COOLING_STAGE_TWO
                        count = count + 1
                    if count >= ReqBld:
                        break
            if self.Reg[i] < 0:
        	 # decrease power consumption, aka switch off equipment, starting with lowest temp difference for comfort
              	 for node in OrderAsc:
                    if node.state == self.AgentStatesEnum.COOLING_STAGE_ONE:
                        node.state = self.AgentStatesEnum.OFF
                        count = count + 1
                    elif node.state == self.AgentStatesEnum.COOLING_STAGE_TWO:
                        node.state = self.AgentStatesEnum.COOLING_STAGE_ONE
                        count = count + 1
                    if count >= ReqBld:
                        break

            # send out decisions
            Log.info ("Sending decisions")
            for nodekey in self.Nodes:
         	node = self.Nodes[nodekey]
                msg = {}
                msg['ID'] = node.ID
                msg['action'] = node.state
                headers = {"FROM": self.agentID}
                try:
                    node.agent.vip.pubsub.publish(
                    'pubsub', topic='masternode/command', headers=headers, message=msg).get(timeout=60)
                except Exception as e:
                    Log.error(e)
            Log.info("Decisions sent")
            self.i = self.i + 1
            if self.i == self.Nsim:
         	self.i = 0
	
def main(argv=sys.argv):
	try:
		utils.vip_main(MasterNode)
	except Exception as e:
		Log.exception("Unhandled exception")

if __name__ == "__main__":
	#Entry point for script
	try:
		sys.exit(main())
	except KeyboardInterrupt:
		pass










