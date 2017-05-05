import Tstat6
import time

global MAX_PRIORITY
MAX_PRIORITY = 10

global MIN_PRIORITY
MIN_PRIORITY = 0

#format for lists is ID, priority, is on (1/0), mode, can switch (1/0)

global equip 

# Compare the priority of two devices. If priority is the same,
# prefer the device that we can actuate.
def compare_priority(first, second):

	priority1 = first.priority
	priority2 = second.priority

	can_switch1 = first.can_switch
	can_switch2 = second.can_switch

	return (priority1 > priority2 or (priority1 == priority2 and can_switch1 > can_switch2))

# Activate or deactivate equipment according to the control rule
def run_scheduler(equip,N):
	status = []

	for i in range(0,len(equip)):
		status.append(None)

	skip_list = [] 
	activate_list = []
	deactivate_list = []
	count = 0
	active_count = 0
	pending_active = 0
	
	switched_device = False

	#Scan all of the devices, discarded devices that fail to respond

	if not equip:
		assert(False)

	#Sort the devices by priority
	equip.sort(key = lambda tstat: tstat.priority, reverse=True)

	for i in range(0,len(equip)):
		for j in range(0, len(equip)):
			if equip[i].priority == equip[j].priority and i != j:
				if equip[i].can_switch > equip[j].can_switch:
					equip[i], equip[j] = equip[j],equip[i]
				else:
					pass
			else:
				pass


	if equip[0].priority < equip[len(equip)-1].priority:
		assert(False)

	#Find devices that can be shutdown or activated. Count the number of active devices and devices we would like to activate.
	for tstat in equip:
		if tstat.is_on == 1:
			active_count += 1
	
		count += 1
		
		if (tstat.is_on == 1 and tstat.priority != MAX_PRIORITY and tstat.can_switch == 1 and (tstat.priority == MIN_PRIORITY or count > N)):
		
			deactivate_list.insert(0,tstat); # List will be sorted from low priority to high priority
		
		elif (tstat.is_on == 0 and tstat.priority != MIN_PRIORITY and tstat.can_switch == 1 and (tstat.priority == MAX_PRIORITY or count <= N)):
		
			activate_list.append(tstat); # List will be sorted from high priority to low priority
			time.sleep(1)
			pending_active += 1

	
	if deactivate_list and len(deactivate_list) != 1 and (deactivate_list[0].priority > deactivate_list[len(deactivate_list)-1].priority):	
		assert(False)
	
	if activate_list != [] and (len(activate_list) != 1 and activate_list[0].priority < activate_list[len(activate_list)-1].priority):
		assert(False)

	# Shutdown priority zero devices and as many others as are needed to enable the new devices to run or get below our limit
	
	while deactivate_list:

		if deactivate_list[0].priority == MIN_PRIORITY or (active_count + pending_active) > N:

			if deactivate_list[0].priority >= MAX_PRIORITY:
				assert(False);
			try:
				status[deactivate_list[0].devID-1] = 'shutdown'

			except ValueError:
				pass
		
			switched_device = True

			if active_count <= 0:
				assert(False)
			active_count -= 1
			deactivate_list.pop(0)
	
	# Active as many devices as we can
	while activate_list:
		
		if activate_list[0].priority == MAX_PRIORITY or active_count < N:

			try:
				status[activate_list[0].devID-1] = 'activate'

			except ValueError:
				pass		

			switched_device = True
			active_count += 1
			activate_list.pop(0)

		else:
			break

	#If a device is active and has mode 2, give it the opportunity to switch to a less intense mode
	## CHANGED: If previously on mode 2 and told to shutdown, wont be changed to reactivate
	for tstat in equip:

		if ((tstat.is_on == 1 and abs(tstat.mode) == 2 and status[tstat.devID-1] != 'shutdown') or (tstat.is_on == 1 and abs(tstat.mode) == 1 and int(tstat.priority) == MAX_PRIORITY)):
			status[tstat.devID-1] = 'activate'
			switched_device = True

	# Report device stats
	if switched_device == True:
	
		#to do
		#Add in time since last report
		for tstat in equip:
			 print('i= ' + str(tstat.devID) + ",p=" + str(tstat.priority) + ",a=" + str(tstat.is_on) + ",s=" + str(tstat.can_switch) + '\n')
	

	#Check assumptions about scheduling invariant
	my_slot = 0
	for tstat in equip:
	
		my_slot =+ 1
		#All max priority devices are running or unable to be switched
		#assert(tstat.priority < MAX_PRIORITY or tstat.is_on == 1 or (tstat.is_on == 0 and tstat.can_switch == 0))
		#All zero priority devices are off or unable to be switched
		#assert(tstat.priority > MIN_PRIORITY or tstat.is_on == 0 or tstat.can_switch == 0)
		#If I am running and can be switched, then I have priority or no higher priority in the first N
		#slots can run
		if (my_slot > N and tstat.priority < MAX_PRIORITY and tstat.is_on == 1 and tstat.can_switch == 1):
		
			slot = 0
			for other in equip:
			
				slot =+ 1
				assert(other.priority >= tstat.priority)
				if (slot <= N):
				
					assert(other != tstat)
					assert(other.priority == tstat.priority or other.is_on or other.can_switch == 0);
				
				else: 
					break		
	
	#Put removed devices back into the list
	for d in skip_list:
	
		equip.append(d)

        print(str(status))

	return status
