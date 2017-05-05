# This class serves as dummy for list sorting on control side of Volttron Bus

class Tstat6:
	
	def __init__(self, devID, current_priority, is_on, mode, switch_ok):
		self.devID = devID
		self.priority = current_priority
		self.is_on = is_on
		self.mode = mode
		self.can_switch = switch_ok
