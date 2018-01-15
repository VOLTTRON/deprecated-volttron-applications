import datetime
import logging
import sys
import uuid
import math

from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod

from volttron.platform.messaging import topics, headers as headers_mod

from scipy.interpolate import interp1d

from cvxopt import matrix, solvers
from os.path import warnings

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.1'

def DatetimeFromValue(ts):
    ''' Utility for dealing with time
    '''
    if isinstance(ts, (int, long)):
        return datetime.utcfromtimestamp(ts)
    elif isinstance(ts, float):
        return datetime.utcfromtimestamp(ts)
    elif not isinstance(ts, datetime):
        raise ValueError('Unknown timestamp value')
    return ts

def HEMS_agent(config_path, **kwargs):

    config = utils.load_config(config_path)
    device_config = config['device']['units']
    if 'parameters' in config['device']:
        device_para = config['device']['parameters']
    house = config['device']['house']
    device_dict = {}
    device_topic_dict = {}
    # setpoint related values initialization
    device_setpoint_dict = {}
    device_setpoint_topic_dict = {}
    device_setpoint_val_dict = {}
    device_setpoint_val_ori_dict = {}
    diff = {}
    reductionE = {}
    disutility = {}
    # load consumption related values initialization
    device_load_topic_dict = {}
    device_load_val_dict = {}
    device_energy_dict = {}
    device_energy_dict_Period = {}
    device_energy_area = {}
    # pre-generated delta setpoint and delta power parameters
    device_para_dict = {}
    # beta values
    device_beta_topic_dict = {}
    device_beta_dict = {}
   
    for device_name in device_config:
        # setpoints topic
        setpointName = device_config[device_name][0]
        setpoint_topic = 'fncs/output/devices/fncs_Test/' + house + '/' + device_name + '/' + setpointName
        device_setpoint_topic_dict.update({device_name: setpoint_topic})
        device_setpoint_dict.update({device_name: setpointName})
        device_setpoint_val_dict.update({device_name: 0.0})
        device_setpoint_val_ori_dict.update({device_name: 0.0})
        diff.update({device_name: 0.0})
        reductionE.update({device_name: 0.0})
        disutility.update({device_name: 0.0})
               
        # Load topic full path
        loadName = device_config[device_name][1]
        load_topic = 'fncs/output/devices/fncs_Test/' + device_name + '/' + loadName
        device_load_topic_dict.update({device_name: load_topic})
        device_load_val_dict.update({device_name: 0.0})
        
        # beta topic
        betaName = device_config[device_name][2]
        beta_topic = house + '/' + device_name + '/' + betaName
        device_beta_topic_dict.update({device_name: beta_topic})
        
        # Intialize device energy consumption for the whole simulation time, and for the energy reduction time only
        device_energy_dict.update({device_name: 0.0})
        device_energy_dict_Period.update({device_name: 0.0})
        device_energy_area.update({device_name: 0.0}) # used to calculate average enery consumption after energy reduction start till the end of the day
        
        # Read in pre-generated device parameters for relationship between setpoint and power changes
        if 'parameters' in config['device']:
            if 'setpoint' in device_para[device_name]:
                device_setpoint_val_dict[device_name] = device_para[device_name]['setpoint']
                device_setpoint_val_ori_dict[device_name] = device_para[device_name]['setpoint']
            else:
                warnings.warn('Default setpoint is not given in config file, a base setpoint is needed from user') 
            if 'setpoint_delta' in device_para[device_name]:
                setpoint_list = device_para[device_name]['setpoint_delta']
            else:
                raise ValueError('setpoint list is not given in config file')
            if 'power_delta' in device_para[device_name]:
                power_list = device_para[device_name]['power_delta']
            else:
                raise ValueError('power list is not given in config file')
            if 'beta' in device_para[device_name]:
                beta = device_para[device_name]['beta']
                
            device_beta_dict.update({device_name: beta})
            setpoint_power_list = []
            setpoint_power_list.append(setpoint_list)
            setpoint_power_list.append(power_list)
            device_para_dict.update({device_name: setpoint_power_list})
        
    agent_id = config.get('agentid', 'HEMS_agent')

    class HEMS_agent_test(Agent):
        '''This agent is used to adjsust setpoint of appliances so that
        minimum disutility price can be achieved. 
        '''
    
        def __init__(self, **kwargs):
            super(HEMS_agent_test, self).__init__(**kwargs)
    
        @Core.receiver('onsetup')
        def setup(self, sender, **kwargs):
            self._agent_id = config['agentid']
        
        @Core.receiver('onstart')            
        def startup(self, sender, **kwargs):
            
            currTime = datetime.datetime.now()
            
            # Total scheduled energy reduction (kWh) by default
            self.P_total = 3.0
            
            # Initialize subscription function to change setpoints
            for device_name in device_setpoint_topic_dict:
                _log.info('Subscribing to ' + device_setpoint_topic_dict[device_name])
                setpoint_topic = device_setpoint_topic_dict[device_name]
                self.vip.pubsub.subscribe(peer='pubsub',
                                          prefix=setpoint_topic,
                                          callback=self.on_receive_setpoint_message_fncs)
            
            # Initialize subscription function to energy reduction amount
            _log.info('Subscribing to total energy reduction amount')
            P_topic = house + '/energy_reduction' 
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=P_topic,
                                  callback=self.on_receive_energy_reduction_message_fncs)
            
            # Initialize subscription function to change beta values
            for device_name in device_beta_topic_dict:
                _log.info('Subscribing to ' + device_beta_topic_dict[device_name])
                beta_topic = device_beta_topic_dict[device_name]
                self.vip.pubsub.subscribe(peer='pubsub',
                                          prefix=beta_topic,
                                          callback=self.on_receive_beta_message_fncs)
            
            # Initialize subscription function to record current loads from appliances
            self.loadChangeTime = {}
            self.energyPeriodCalculated = {}
            for device_name in device_load_topic_dict:
                _log.info('Subscribing to ' + device_load_topic_dict[device_name])
                self.vip.pubsub.subscribe(peer='pubsub',
                                          prefix=device_load_topic_dict[device_name],
                                          callback=self.on_receive_load_message_fncs)
                self.loadChangeTime[device_name] = currTime
                self.energyPeriodCalculated[device_name] = False
            
            # Initialize subscription function to fncs_bridge:
            topic = 'FNCS_Volttron_Bridge/simulation_end'
            _log.info('Subscribing to ' + topic)
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=topic,
                                          callback=self.on_receive_fncs_bridge_message_fncs)
            
                        
            # Set energy consumption time starts at 14 minutes after simulation begins, and lasts for 3 minutes
            _log.info('Simulation starts from: {}.'.format(str(currTime)))
            self.startEnergyReduction = currTime + datetime.timedelta(minutes=16)
            self.endEnergyReduction = currTime + datetime.timedelta(minutes=21)
            _log.info('Energy reduction starts from: {}.'.format(str(self.startEnergyReduction)))
            _log.info('Energy reduction ends at: {}.'.format(str(self.endEnergyReduction)))
            self.energyReduced = False
            self.energyPeriodCalculated = False
            self.energyCalTime = currTime
            
            # Conduct optimization problem with the default beta values, at the begining of the simulations
            self.energy_reduction()

                        
        def on_receive_setpoint_message_fncs(self, peer, sender, bus, topic, headers, message):
            """Subscribe to appliance setpoint and change the data accordingly 
            """    
#             _log.info("Whole message", topic, message)
#             #The time stamp is in the headers
#             _log.info('Date', headers['Date'])
            # Find the appliance name
            device = topic.split("/")[-2]
            # Update device setpoint
            setpoint = message[0]
            device_setpoint_val_dict.update({device: setpoint})
#             _log.info('Unit {0:s} setpoint changed to {1} at time {2} '.format(device, setpoint, str(datetime.datetime.now())))
    
        def on_receive_beta_message_fncs(self, peer, sender, bus, topic, headers, message):
            """Subscribe to appliance beta values based on slider bar changes
            """ 
            # Find the appliance name
            device = topic.split("/")[-2]
            
            # Update device beta value
            beta = message
            device_beta_dict.update({device: beta})
            _log.info('Unit {0:s} beta value changed to {1} at time {2} '.format(device, beta, str(datetime.datetime.now())))  
            
            # Re-conduct optimization problem with the updated beta values, only before energy reduction happens
            if (self.energyReduced == False) :
                # re-conduct optimization
                self.energy_reduction()
        
        def on_receive_energy_reduction_message_fncs(self, peer, sender, bus, topic, headers, message):
            """Subscribe to appliance setpoint and change the data accordingly 
            """    
            # Update energy reduction value
            self.P_total = float(message)
            
            # Re-conduct optimization problem with the updated energy reduction values, only before energy reduction happens
            if (self.energyReduced == False) :
                # re-conduct optimization
                self.energy_reduction()
                
            
        @Core.periodic(1)
        def change_setpoints(self):
            ''' This method publishes updated setpoint when the energy reduction starts
            '''            
            # Check if energy reduction time arrives
            if (self.energyReduced == False) and (datetime.datetime.now() >= self.startEnergyReduction):
                _log.info('Energy reduction begins at time {} '.format(str(datetime.datetime.now())))
                self.energyReduced = True # Set flag so that setpoint updates for energy reduction only changes once
                self.publish_setpoint()
            
#             # Check if energy reduction time ends
#             if (datetime.datetime.now() >= self.endEnergyReduction) and (self.energyPeriodCalculated == False):
#                 self.energyPeriodCalculated = True # Set flag so that total energy consumption is ony displayed once
#                 now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
#                 headers = {
#                     headers_mod.DATE: now
#                 }
#                 index = 0
#                 for device_name in device_setpoint_dict:
#                     # Publish the original setpoints:
#                     pub_topic = 'fncs/input/house/' + device_name + '/' + device_setpoint_dict[device_name]
#                     self.vip.pubsub.publish('pubsub', pub_topic, headers, device_setpoint_val_ori_dict[device_name])
#                     _log.info('HEMS agent publishes updated setpoints {0} to unit {1:s} with topic: {2}'.format(device_setpoint_val_ori_dict[device_name], device_name, pub_topic))
#                     index += 1 
#                     # Also update final energy consumption values
#                     load_curr = device_load_val_dict[device_name]
#                     energy_ori = device_energy_dict_Period[device_name]
#                     timediff = self.cal_time_diff(self.endEnergyReduction, self.loadChangeTime[device_name])
#                     energy_update = energy_ori + load_curr * timediff / 60
#                     device_energy_dict_Period.update({device_name: energy_update})
#                     _log.info('unit {0:s} total energy consumption during the energy reduction period is {1:f}'.format(device_name, device_energy_dict_Period[device_name]))
#         
        # ====================Obtain values from fncs_bridge ===========================
        def on_receive_fncs_bridge_message_fncs(self, peer, sender, bus, topic, headers, message):
            """Subscribe to fncs_bridge publications, change appliance setpoints back, and summarize the total energy reduction
            """    
            val =  message[0] # value True
            if (val == 'True'):
                _log.info('----------------- HEMS agent recieves from fncs_bridge the siimulation ending signal.-----------------------')
                
                # Calculate and publish the total energy reduction at the end of the day
                now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
                headers = {
                    headers_mod.DATE: now
                }
                
                currTime = datetime.datetime.now()

                for device_name in device_setpoint_dict:
                    # Publish the original setpoints:
                    pub_topic = 'fncs/input/house/' + device_name + '/' + device_setpoint_dict[device_name]
                    self.vip.pubsub.publish('pubsub', pub_topic, headers, device_setpoint_val_ori_dict[device_name])
                    _log.info('HEMS agent publishes updated setpoints {0} to unit {1:s} with topic: {2}'.format(device_setpoint_val_ori_dict[device_name], device_name, pub_topic))
                    
                    # Also update final energy consumption values
                    load_curr = device_load_val_dict[device_name]
                    energy_ori = device_energy_dict_Period[device_name]
                    timediff = self.cal_time_diff(currTime, self.loadChangeTime[device_name])
                    energy_update = energy_ori + load_curr * timediff / 60
                    device_energy_dict_Period.update({device_name: energy_update})
                    _log.info('unit {0:s} total energy consumption after the energy reduction starts is {1:f} kWh'.format(device_name, device_energy_dict_Period[device_name]))
                    
                    # Calculation of energy area accumulation
                    area = (energy_update - energy_ori) / 2 * timediff / 60 + energy_ori * timediff / 60 
                    device_energy_area[device_name] += area
                    _log.info('unit {0:s} total energy area after the energy reduction starts is {1:f}'.format(device_name, device_energy_area[device_name]))
                    
                # Stop HEMS agent
                self.core.stop() 
                
        def cal_time_diff(self, t1, t2):
            '''Calculate the time difference in seconds
            '''
            t1_tuple = datetime.datetime.timetuple(t1)
            t2_tuple = datetime.datetime.timetuple(t2)
            timediff = (t1_tuple.tm_mday - t2_tuple.tm_mday) * 24 * 3600 + \
                       (t1_tuple.tm_hour - t2_tuple.tm_hour) * 3600 + \
                       (t1_tuple.tm_min - t2_tuple.tm_min) * 60 + \
                       (t1_tuple.tm_sec - t2_tuple.tm_sec)
                       
            return timediff
                         
        def on_receive_load_message_fncs(self, peer, sender, bus, topic, headers, message):
            """Subscribe to appliance loads and record the load data accordingly 
            """               
            
            currTime = datetime.datetime.now()
            now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
            
            # Find the appliance name
            device_name = topic.split("/")[-2]
            _log.info('unit {0:s} changes load to {1:f} at time {2:s}'.format(device_name, message[0], str(currTime)))
            
            # Check if energy consumption calculation after the enery reduction period starts
            if (currTime >= self.startEnergyReduction):
                load_curr = device_load_val_dict[device_name]
                energy_ori = device_energy_dict_Period[device_name]
                # Calculate time difference based on whether energy accumulation was done last time after energy reduction has started
                if (self.loadChangeTime[device_name] < self.startEnergyReduction): 
                    timediff = self.cal_time_diff(currTime, self.startEnergyReduction)
                else:
                    timediff = self.cal_time_diff(currTime, self.loadChangeTime[device_name])
                # Calculation of energy accumulation
                energy_update = energy_ori + load_curr * timediff / 60
                device_energy_dict_Period.update({device_name: energy_update})
                # Calculation of energy area accumulation
                area = (energy_update - energy_ori) / 2 * timediff / 60 + energy_ori * timediff / 60   
                device_energy_area[device_name] += area
                
            # Write to log the total energy consssumption whenever load changes during the simulation
            load_curr = device_load_val_dict[device_name]
            energy_ori = device_energy_dict[device_name]
            timediff = self.cal_time_diff(currTime, self.energyCalTime)
            energy_update = energy_ori + load_curr * timediff / 60
            device_energy_dict.update({device_name: energy_update})
            self.energyCalTime = currTime
            _log.info('unit {0:s}: total energy consumption is {1:f} kWh, load changed to {3:f} kW, at time {2:s}'.format(device_name, device_energy_dict[device_name], str(datetime.datetime.now()), message[0]))
            
            # Publish the energy consumption as well as the load to the message bus, whenever the load changes
            headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
            # devices/all/wh-9845/office/skycentrics
            topicLoad = 'house/{0:s}/load(kW)'.format(device_name)
            mesgLoad = {'load(kW)': load_curr}
            topicEnergy = 'house/{0:s}/Energy(kWH)'.format(device_name)
            mesgEnergy = {'Energy(kWH)': energy_update}

            topicAll = 'devices/all/{0:s}/office/skycentrics'.format(device_name)
            mesgAll =  [{'InstantaneousElectricityConsumption': load_curr,
                        'TotalEnergyStorageCapacity': energy_update},
                       {'InstantaneousElectricityConsumption': {'units': 'kW', 'tz': 'UTC', 'type': 'float'},
                        'TotalEnergyStorageCapacity': {'units': 'kWh', 'tz': 'UTC', 'type': 'float'}
                        }]
            self.vip.pubsub.publish('pubsub', topicLoad, headers, mesgLoad)
            self.vip.pubsub.publish('pubsub', topicEnergy, headers, mesgEnergy)
            # Publish all messages
            self.vip.pubsub.publish('pubsub', topicAll, headers, mesgAll)
            
            # Update device load (kW)
            device_load_val_dict.update({device_name: message[0]})
            self.loadChangeTime[device_name] = currTime
        
        def congestion(self, lambda_avg, lambda_sigma):
            '''
            Try diferrent values of clearing price lambda, to get the closest total energy reduction to the desired amount
            '''
            lambdas =  [x * 0.01 for x in range(0, 101)]
            errors = [None] * len(lambdas)
            lambda_2 = 0
            
            for i in range(0, len(lambdas)):
            
                Esum = 0
                
                # loop through each device
                for device_name in device_beta_dict:
                
                    beta = device_beta_dict[device_name]
                    
                    # Calculate corresponding energy reduction and setpoint changes                
                    delta_E, delta_T = self.energy_response(device_name, beta, lambdas[i], lambda_avg, lambda_sigma)
#                     print [delta_E, delta_T]
                
                    Esum += delta_E
                    
                # Check error
                errors[i] = Esum - self.P_total # Esum total reduction is positive value
                if (errors[i] >= 0):
                    break
            
            if (errors[i] == 0):
                lambda_2 = lambdas[i]
                return lambda_2
            
            if (errors[i] > 0):
                if (errors[i] > abs(errors[i - 1])):
                    lambda_2 = lambdas[i - 1]
                else:
                    lambda_2 = lambdas[i]
            
            if (lambda_2 == 0):
                warnings.warn('lambda_2 value is zero, meaning that all calcualted total energy reduction is less than the desired value')
                
            return lambda_2
        
        def energy_response(self, device_name, beta, lambdai, lambda_avg, lambda_sigma):
            '''
            This function calculate the corresponding energy reduction and setpoint changes based on given market cleared price
            '''
            # From control response curve, obtain deltaT with lambda
            deltaT = self.deltaT_response(device_name, beta, lambdai, lambda_avg, lambda_sigma)
            
            # From deltaT, and relationship between deltaT and deltaE, obtain deltaE
            setpoint_list = device_para[device_name]['setpoint_delta']
            power_list = device_para[device_name]['power_delta']
            interp_func = interp1d(setpoint_list, power_list)
            deltaE = interp_func(deltaT)
            
            return deltaE, deltaT
        
        def deltaT_response(self, device_name, beta, lambdai, lambda_avg, lambda_sigma):
            '''
            This function calculate the corresponding setpoint changes based on given market cleared price, and control response function
            '''
            setpoint_list = device_para[device_name]['setpoint_delta']
            deltaT = abs(setpoint_list[-1]) * lambdai / (lambda_avg + beta * lambda_sigma)
            if (deltaT <= abs(setpoint_list[0])):
                deltaT = abs(setpoint_list[0])
            elif (deltaT >= abs(setpoint_list[-1])):
                deltaT = abs(setpoint_list[-1])
            
            if (setpoint_list[-1] < 0): # Consider WH case when energy reduction results from Decrease of setpointsssssssssssssssssssssssss
                deltaT = -deltaT
                
            return deltaT
        
        def cal_disutility(self, device_name, beta, delta_T, lambda_avg, lambda_sigma):
            '''
            Calculate disutility based on integral of Cleared Price * Cleared quantity
            '''
            T = self.frange(0, abs(delta_T), 0.1)
            disutility = 0
            E = [None] * len(T)
            lambdas = [None] * len(T)
            
            setpoint_list = device_para[device_name]['setpoint_delta']
            power_list = device_para[device_name]['power_delta']
            interp_func = interp1d(setpoint_list, power_list)
            
            for i in range(0, len(T)):
                
                lambdas[i] = (lambda_avg + beta * lambda_sigma) * T[i] / abs(setpoint_list[-1]) 
                # From deltaT, and relationship between deltaT and deltaE, obtain deltaE
                if (setpoint_list[-1] < 0):
                    E[i] = interp_func(-T[i])
                else:
                    E[i] = interp_func(T[i])
                if i >= 1:
                    disutility += lambdas[i - 1] * (E[i] - E[i - 1])
                    
            return disutility

        def energy_reduction(self): 
            '''
            This function calculate the setpoint change of each device, so that total energy reduction can achieve the desired amount
            '''
            # ======================== Test code ===========================================================#
#             device_para['AC1']['setpoint_delta'] = [0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0]
#             device_para['AC1']['power_delta'] = [0,0.153484954,0.306724537,0.460570602,0.617362269,0.776594907,0.927584491,1.079421296,1.233296296,1.401094907,1.55643287,1.694083333,1.832385417,1.974203704,2.11971875,2.298293981,2.440744213]
#             device_para['AC2']['setpoint_delta'] = [0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]
#             device_para['AC2']['power_delta'] = [0,0.116864583,0.234591435,0.352828704,0.470645833,0.581621528,0.703003472,0.809390046,0.916498843,1.025902778,1.137876157,1.26200463,1.371810185]
#             device_para['WH1']['setpoint_delta'] = [0, -0.5, -1.0, -1.5, -2.0, -2.5,-3.0, -3.5, -4.0, -4.5, -5.0, -5.5, -6.0, -6.5, -7.0, -7.5, -8.0, -8.5, -9.0, -9.5, -10]
#             device_para['WH1']['power_delta'] = [0,0.050699074,0.103472222,0.156386574,0.21721875,0.254753472,0.280082176,0.315210648,0.342613426,0.375969907,0.407893519,0.440503472,0.514478009,0.588524306,0.599260417,0.610091435,0.616633102,0.635606481,0.636326389,0.637357639,0.642358796]

            # ======================== Test code ===========================================================#
            
            
            # Predeined market clearing price lambda1
            lambda_e = 0.10
            lambda_u = 0.05
            
            # define average and standard deviation of the market clearing price over the past period of time
            lambda_avg = 0.15
            lambda_sigma = 0.01
            
            # Obtain two market clearing prices lambda1 and lambda2
            lambda_1 = lambda_e + lambda_u
            lambda_2 = self.congestion(lambda_avg, lambda_sigma)
            
            # Determine the market clearing price by the smaller lambda value
            # If maximum total energy reduction is less than the desired amount, directly use the given utility price
            if (lambda_2 == 0):
                lambdaMin = lambda_1
            else:
                lambdaMin = min(lambda_1,lambda_2)
            
            # Based on determined cleared price, find the corresponding energy reduction, setpoint changes, and disutility for each device
            totalE = 0
            for device_name in device_beta_dict:
            
                beta = device_beta_dict[device_name]
                
                # Calculate corresponding energy reduction and setpoint changes                
                delta_E, delta_T = self.energy_response(device_name, beta, lambdaMin, lambda_avg, lambda_sigma)
                diff[device_name] = delta_T
                reductionE[device_name] = delta_E.item()
                totalE += delta_E.item()
                
                # Calculate disutility based on integral of Cleared Price*cleared quantity
                disutility[device_name] = self.cal_disutility(device_name, beta, delta_T, lambda_avg, lambda_sigma)
                
            # Prediction based on determined market cleared price
            revenue = totalE * lambda_1
            disutilitySum = sum(disutility.values())
            net_revenue = revenue - disutilitySum
            _log.info('Desired energy reduction is {1:f} kWh, total energy reduction is {1:f} kWh, with compensation price {2:f} $/kWh'.format(self.P_total, totalE, lambdaMin))
            _log.info('Based on determined market cleared price, revenue {0:f} $ can be obtained, with total disutility {1:f} $. Total net revenue is {2:f} $'.format(revenue, disutilitySum, net_revenue))
                 
            # Send the determined values
            now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
            headers = {
                headers_mod.DATE: now
            }
            
            # Publish the calculated minimum compensation for the occupant
            # _log.info('Total minimum compensation for the occupant with chosen preferences [{1:f}, {2:f}, {3:f}] is {0:f} $'.format(sol['primal objective'], beta_1, beta_2, beta_3))
            # pub_topic = 'fncs/input/house/minimum_disutility'
            # print("================================================")
            # print(sol['primal objective'])
            # self.vip.pubsub.publish('pubsub', pub_topic, headers, sol['primal objective'])
            
            # Publish the total energy reduction expected
            pub_topic = 'fncs/input/house/energy_reduction'
            self.vip.pubsub.publish('pubsub', pub_topic, headers, totalE)
        
        def publish_setpoint(self): 
            
            # At the energy reduction time, publish the changed setpoints based on optimization function
            now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
            headers = {
                headers_mod.DATE: now
            }

            for device_name in device_setpoint_dict:
                # First update the setpoints based on cauclated setpoint change from optimization problem
                setpoint = device_setpoint_val_dict[device_name]
                device_setpoint_val_ori_dict.update({device_name: setpoint})
                device_setpoint_val_dict.update({device_name: setpoint + diff[device_name]})
                # Publish the changed setpoints:
                pub_topic = 'fncs/input/house/' + device_name + '/' + device_setpoint_dict[device_name]
                _log.info('HEMS agent publishes updated setpoints {0} to unit {1:s} with topic: {2}'.format(device_setpoint_val_dict[device_name], device_name, pub_topic))
                self.vip.pubsub.publish('pubsub', pub_topic, headers, setpoint + diff[device_name])
                
        def frange(self, start, end, step):
            num = int(float(end - start) / step) + 1
            list = [None] * num
            temp = start
            ct = 0
            while(ct < num):
                list[ct] = temp
                temp += step
                ct += 1   
            return list
                   
    Agent.__name__ = 'HEMSAgent'    
    return HEMS_agent_test(**kwargs)
              
def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(HEMS_agent)
    except Exception as e:
        print e
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
   
            
            