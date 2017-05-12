#This building library is intended for a serial network of
#TStat 6 thermostats.

#import minimalmodbus
import math
import time
import datetime
import sht21
import relays
from settings import settings

class tstat():

        temp_sensor = sht21.SHT21(1)

	TempRange = 2.0
	MAX_PRIORITY = 10
	MIN_PRIORITY = 0

	HEAT1 = 1
	HEAT2 = 2
	COOL1 = -1
	COOL2 = -2
	IDLE = 0

        COOLING1_RELAY = 2
        COOLING2_RELAY = 3
        HEATING1_RELAY = 4
        HEATING2_RELAY = 5
        FAN_RELAY = 1

	HEAT_MODE = 2
	COOL_MODE = 1
	OFF_MODE = 0
	
	last_switch_time = time.time() #initialize last switch time

	tempData = 0
	requested_mode = 0


	def __init__(self,z):
		self.zonenum = z
		self.setPoint = settings[1]
		self.deadband = settings[4]
		self.min_switch_time = settings[3]
		self.set_to_manual()

	def set_to_manual(self):
		relays.relaySetup()
	
		#Turn off rtu for fresh start
		self.set_mode(self.IDLE)

	def read_temp(self):
                temp = float(self.temp_sensor.read_temperature())
                return temp

	def set_setpoint(self,setpoint):
		if setpoint >80:
			setpoint = 80

		if setpoint < 60:
			setpoint = 60
		
		self.setPoint=setpoint
		

        def read_setpoint(self):
		return self.setPoint

        def heat_cool_request(self):
        
                #only activate if 0.1 degree(F) over setpoint
                if self.temp > self.read_setpoint()+self.deadband:
                        return self.COOL_MODE

                elif self.temp < self.read_setpoint()-self.deadband:
                        return self.HEAT_MODE

                else:
                        return self.OFF_MODE


	def get_mode(self):
		return self.read_mode()

        ##Read Mode
	def read_mode(self):
		#Read the relays
                c1 = relays.relayRead(self.COOLING1_RELAY)
                c2 = relays.relayRead(self.COOLING2_RELAY)
                h1 = relays.relayRead(self.HEATING1_RELAY)
                h2 = relays.relayRead(self.HEATING2_RELAY)
	
		if (h1 == 0 and c1 == 0 and h2 == 0 and c2 == 0):
			mode = self.IDLE
	
		elif (h1 != 0 and c1 == 0 and c2 == 0):
	
			if (h2 != 0):
				mode = self.HEAT2
			else: 
				mode = self.HEAT1
		
		elif (h1 == 0 and c1 != 0 and h2 == 0):
	
			if (c2 != 0): 
				mode = self.COOL2
			else:
				mode = self.COOL1
	
		else:
			assert(False)
	
		return mode

	##Find if tstat is active
	def is_active(self):

		current_mode = self.read_mode()

		if(current_mode != self.IDLE):
			is_on = 1
		elif(current_mode == self.IDLE):
			is_on = 0

		return is_on

	#Find if tstat can switch
	#last_switch_time assigned in activate method
	def switchable(self):
		if(time.time()-self.last_switch_time > self.min_switch_time):	#sets short cycle limits (has been at 10min)	
			can_switch = 1
		elif(time.time()-self.last_switch_time <= self.min_switch_time):
			can_switch = 0
		return can_switch


        def set_mode(self,hvac_mode):

                print("SETTING MODE " + str(hvac_mode))

		heat1_relay = self.HEATING1_RELAY
		heat2_relay = self.HEATING2_RELAY
		cool1_relay = self.COOLING1_RELAY
		cool2_relay = self.COOLING2_RELAY

		if (hvac_mode == self.COOL1):
	
			relays.relayClear(heat1_relay) # Heater 1 off
			relays.relayClear(heat2_relay) # Heater 2 off
			relays.relayClear(cool2_relay) # Cooler 2 off
			relays.relaySet(cool1_relay) # Cooler 1 on
	
		elif (hvac_mode == self.COOL2):
	
			relays.relayClear(heat1_relay) # Heater 1 off
			relays.relayClear(heat2_relay) # Heater 2 off
			relays.relaySet(cool2_relay) # Cooler 2 on
			relays.relaySet(cool1_relay) # Cooler 1 on
	
		elif (hvac_mode == self.HEAT1):
	
			relays.relayClear(heat2_relay) # Heater 2 off
			relays.relayClear(cool1_relay) # Cooler 1 off
			relays.relayClear(cool2_relay) # Cooler 2 off
			relays.relaySet(heat1_relay) # Heater 1 on
	
		elif (hvac_mode == self.HEAT2):
	
			relays.relayClear(cool1_relay) # Cooler 1 off
			relays.relayClear(cool2_relay) # Cooler 2 off
			relays.relaySet(heat1_relay) # Heater 1 on
			relays.relaySet(heat2_relay) # Heater 2 on
	
		else:
	
			relays.relayClear(cool1_relay) # Cooler 1 off
			relays.relayClear(cool2_relay) # Cooler 2 off
			relays.relayClear(heat1_relay) # Heater 1 off
			relays.relayClear(heat2_relay) # Heater 2 off

		# Actuate the fan if fan is in auto mode
		if (hvac_mode == self.IDLE):
			relays.relayClear(self.FAN_RELAY); # Fan off
		else:
			relays.relaySet(self.FAN_RELAY); # Fan on
			
        #Calculate priority
	def calculate_priority(self):
		
		min_prior = self.MIN_PRIORITY
		max_prior = self.MAX_PRIORITY

		tempData = self.read_temp()
		setP = self.read_setpoint()

		requested_mode = self.heat_cool_request()
		
		current_priority = 0
		temp_per_priority = self.TempRange/(max_prior-min_prior)
		temp_diff = tempData - setP

		if (requested_mode == self.HEAT_MODE and temp_diff < 0.0):
			current_priority = min_prior+math.ceil(-temp_diff/temp_per_priority);
	
		elif (requested_mode == self.COOL_MODE and temp_diff > 0.0):
			current_priority = min_prior+math.ceil(temp_diff/temp_per_priority);
	
		else:
			current_priority = 0.0

		if (current_priority > max_prior):
			current_priority = max_prior

		#was causing an issue distinguishing between floats and ints
		if(current_priority == max_prior):
			current_priority = int(current_priority)

		return current_priority


        ##Scan for operating data
	def poll_request(self):

		#method will return poll (list of scan data)
		#format for lists is ID, priority, is on (bool), mode, can switch (bool)
		poll = []
		for i in range(0,5):
			poll.append(None)

		poll[0] = self.zonenum
		
		priority = self.calculate_priority()
		poll[1] = priority

		active_status = self.is_active()
		poll[2] = active_status

		current_mode = self.read_mode()
		poll[3] = current_mode

		switch_abil = self.switchable()
		poll[4] = switch_abil

                #Check to see if hvac unit has been turned off
                #if(settings.heat_cool == 'OFF'):
                        #self.set_mode(self.IDLE)

                ##Add FAN ONLY check option
                #elif(settings.heat_cool == 'FAN ONLY'):
                        #self.set_mode(self.IDLE)
                        #time.sleep(.25)
                #       relays.relaySet(self.FAN_RELAY)
                        
		return poll



        def activate(self):
                try:
                        tempData = self.read_temp()
                except IOError:
                        print("Failed to read temp sensor")
                        time.sleep(0.35)
                        self.activate()

		setPoint = self.read_setpoint()
		current_mode = self.read_mode()
		requested_mode = self.heat_cool_request()

		if(self.switchable() == 0):
			return
		
		temp_diff = tempData-setPoint

		if(temp_diff > 0.0 and requested_mode == self.COOL_MODE):
			if(temp_diff > self.TempRange):
				hvac_mode = self.COOL2
			else:
				hvac_mode = self.COOL1

		elif(temp_diff < 0.0 and requested_mode == self.HEAT_MODE):
			if(-temp_diff > self.TempRange):
				hvac_mode = self.HEAT2
			else:
				hvac_mode = self.HEAT1

		else:
			hvac_mode = self.IDLE;

		if(current_mode != hvac_mode):
			current_mode = hvac_mode
			self.last_switch_time = time.time()
			self.set_mode(hvac_mode)

        def shutdown(self):

		if(self.switchable() == 0):
			return
		if (self.read_mode() != self.IDLE):
			current_mode = self.IDLE
			self.last_switch_time = time.time();
			self.set_mode(self.IDLE)


if __name__ == "__main__":
        try:
                tmp = tstat(1)
                poll = tmp.poll_request()
                print(str(poll))

                print(tmp.read_temp())

        except IOError, e:
                print e
