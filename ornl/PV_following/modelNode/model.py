import logging
import sys
import time
import json
import random
import uuid
import socket
import fcntl
import struct 
import serial
import gevent
import datetime
import ast
import os.path
from operator import itemgetter
from zmq.utils import jsonapi
from volttron.platform.vip.agent import *
from volttron.platform.agent.base_historian import BaseHistorian
from volttron.platform.agent import utils
from volttron.platform.messaging import topics, headers as headers_mod

utils.setup_logging()
Log = logging.getLogger(__name__)

def enum(**enums):
    return type('Enum', (), enums)
# Function to get IP address
def get_ip_address(ifname):
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	return socket.inet_ntoa(fcntl.ioctl(
		s.fileno(),
		0x8915,
		struct.pack("256s", ifname[:15])
	)[20:24])

class ModelNode(Agent):
    def __init__(self, config_path, **kwargs):
        super(ModelNode, self).__init__(**kwargs)
        self.Config = utils.load_config(config_path)
        self.AgentStatesEnum = enum(
            OFF = 0,
            HEATING_STAGE_ONE =  6,
            HEATING_STAGE_TWO =  3,
            COOLING_STAGE_ONE = -3,
            COOLING_STAGE_TWO = -6
        )
        self.initTimeStamp = time.time()
        self.leader_sorted = []
        self.leader = []
        self.masters = []
        self.numNodes = self.Config["numNodes"]
        self.scanPeriod = self.Config["scanPeriod"]
    
    ##On Agent start, create objects and connect to Masters
    @Core.receiver('onsetup')
    def setup(self, sender, **kwargs):
	# agentID is set to the node's VIP address
        # get own IP address and create the VIP address
	f = os.popen('ifconfig eth0 | grep "inet\ addr" | cut -d: -f2 | cut -d" " -f1')
        self.agentID = f.read().rstrip()#get_ip_address('eth0')
	# get initial room temperature and setpoint
        self.temp = 306
        self.setpoint = self.Config["setPoint"]
        # set initial state
        # Note that for the purposes of this experiment, only the cooling condition is used.
        if self.temp > self.setpoint:
            self.u0 = -3
            self.SetCool(self.AgentStatesEnum.COOLING_STAGE_ONE)
        else:
            self.u0 = 0
            self.SetOff()

        # setup masternode connections
        for inst in range(0,self.numNodes):
            masterVIP = self.Config[str("masterVIP"+str(inst+1))]
            self.masternode = Agent(address=masterVIP)
	    self.masters.append(self.masternode)	
            event = gevent.event.Event()
            self.masternode.core.onstart.connect(lambda *a, **kw:event.set(), event)
            gevent.spawn(self.masternode.core.run)
            event.wait()  
        
    def SetOff(self):
        self.agentState = self.AgentStatesEnum.OFF
        
    def SetCool(self, stage):
        if stage == self.AgentStatesEnum.COOLING_STAGE_ONE:
            self.agentState = self.AgentStatesEnum.COOLING_STAGE_ONE
        elif stage == self.AgentStatesEnum.COOLING_STAGE_TWO:
            self.agentState = self.AgentStatesEnum.COOLING_STAGE_TWO
        else:
            Log.error(self, "Invalid cooling command/argument")

    def SetHeat(self, stage):
        if stage == self.AgentStatesEnum.HEATING_STAGE_ONE:
            self.agentState = self.AgentStatesEnum.HEATING_STAGE_ONE
        elif stage == self.AgentStatesEnum.HEATING_STAGE_TWO:
            self.agentState = self.AgentStatesEnum.HEATING_STAGE_TWO
        else:
            Log.error(self, "Invalid heating command/argument")
            
    # every 5 seconds
    @Core.periodic(5)
    def Update(self):
	# Update masternode of current temperature of the bldg/zone, etc.
        msg = {}
        msg['ID'] = self.agentID
        msg['temp'] = self.temp
        msg['setpoint'] = self.setpoint
        msg['state'] = self.agentState
        headers = {"FROM": self.agentID}
        Log.info("Sending is started-Model_to_Masters)
        for i in range(0,len(self.masters)):
            self.masternode = self.masters[i]
            self.masternode.vip.pubsub.publish('pubsub', topic='temperature', headers=headers, message=msg)
            Log.info("Sent data to masternodes")

    ##Subsribe to leader channel heartbeat
    ##Executes everytime a master agent pulses its hearbeat to bus
    @PubSub.subscribe('pubsub','leader')
    def leader_check(self, peer, sender, bus, topic, headers, message):
	if len(self.leader) < self.numNodes:
	    # First time adding the leaders in the list
		self.leader.append(message)
	else:
		(item for item in self.leader if item["ID"] == message["ID"]).next()["Time"]=message["Time"]
		##To reset leader after time threshold(3 scan periods) is passed
		for inst in range(0,self.numNodes):
			if(time.time() - self.leader[inst]["Time"] > 3*self.scanPeriod):
				#CHANGE self.leader[inst]["Time"] = 999
				self.leader[inst]["ID"] = 999	
		#Sort
		# CHANGE self.leader_sorted = sorted(self.leader, key=itemgetter('Time'))
		self.leader_sorted = sorted(self.leader, key=itemgetter("ID"), reverse=True)
		Log.info("Leader is " + str(self.leader_sorted[0]["ID"]))

    @PubSub.subscribe('pubsub','masternode/command')
    def ProcessIncomingCommand(self, peer, sender, bus,  topic, headers, message):
        #assumption is that leaders having 999 aren't publishing anything anyways
	if(self.leader[0]["Time"] == 999 or len(self.leader_sorted) == 0):
    	#CHANGE if(self.leader_sorted[0]["ID"] == 999 or len(self.leader_sorted) == 0):
            assert(False)
	if headers["FROM"]==str(self.leader_sorted[0]["ID"]): 
	    msg = message
	    if msg['ID'] == self.agentID:
                value = msg['action']
		if value == 0:
	           self.SetOff()
	           Log.info("OFF")
	        elif value == -3:
                    self.SetCool(self.AgentStatesEnum.COOLING_STAGE_ONE)
                    Log.info("COOL STAGE 1")
                elif value == -6:
                    self.SetCool(self.AgentStatesEnum.COOLING_STAGE_TWO)
                    Log.info("COOL STAGE 2")
                else:
                    Log.error("Invalid command received")
                    # Note that the heating condition is not considered here

def main(argv=sys.argv):
	try:
		utils.vip_main(ModelNode)
	except Exception as e:
		Log.exception("Unhandled exception")

if __name__ == "__main__":
	#Entry point for script
	try:
		sys.exit(main())
	except KeyboardInterrupt:
		pass





