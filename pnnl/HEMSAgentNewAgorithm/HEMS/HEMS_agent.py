import datetime, dateutil.parser
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

from Energy_predict import Energy_predict

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

    # pre-generated delta setpoint and delta power parameters
    device_para_dict = {}
    # beta values
    device_beta_topic_dict = {}
    device_beta_dict = {}
    
    # start and end time for energy reduction
    start_time_topic = house + '/' + 'energy_reduction_startTime'
    end_time_topic = house + '/' + 'energy_reduction_endTime'
   
    for device_name in device_config:
        # setpoints topic
        setpointName = device_config[device_name][0]
        setpoint_topic = house + '/' + device_name + '/' + setpointName
        device_setpoint_topic_dict.update({device_name: setpoint_topic})
        device_setpoint_dict.update({device_name: setpointName})
        device_setpoint_val_dict.update({device_name: 0.0})
        device_setpoint_val_ori_dict.update({device_name: 0.0})
        diff.update({device_name: 0.0})
        reductionE.update({device_name: 0.0})
        disutility.update({device_name: 0.0})
        
        # beta topic
        betaName = device_config[device_name][2]
        beta_topic = house + '/' + device_name + '/' + betaName
        device_beta_topic_dict.update({device_name: beta_topic})

        # Read in pre-generated device parameters for relationship between setpoint and power changes
        if 'parameters' in config['device']:
            if 'setpoint' in device_para[device_name]:
                device_setpoint_val_dict[device_name] = device_para[device_name]['setpoint']
                device_setpoint_val_ori_dict[device_name] = device_para[device_name]['setpoint']
            else:
                warnings.warn('Default setpoint is not given in config file, a base setpoint is needed from user') 
#             if 'setpoint_delta' in device_para[device_name]:
#                 setpoint_list = device_para[device_name]['setpoint_delta']
#             else:
#                 raise ValueError('setpoint list is not given in config file')
#             if 'power_delta' in device_para[device_name]:
#                 power_list = device_para[device_name]['power_delta']
#             else:
#                 raise ValueError('power list is not given in config file')
            if 'beta' in device_para[device_name]:
                beta = device_para[device_name]['beta']
                
            device_beta_dict.update({device_name: beta})
#             setpoint_power_list = []
#             setpoint_power_list.append(setpoint_list)
#             setpoint_power_list.append(power_list)
#             device_para_dict.update({device_name: setpoint_power_list})
        
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
            
            # Initialize subscription function to start time
            _log.info('Subscribing to energy reduction starting time of one day')
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=start_time_topic,
                                      callback=self.on_receive_start_time_message_fncs)
            
            # Initialize subscription function to start time
            _log.info('Subscribing to energy reduction ending time of one day')
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=end_time_topic,
                                      callback=self.on_receive_end_time_message_fncs)
            
            # Initialize subscription function to change beta values
            for device_name in device_beta_topic_dict:
                _log.info('Subscribing to ' + device_beta_topic_dict[device_name])
                beta_topic = device_beta_topic_dict[device_name]
                self.vip.pubsub.subscribe(peer='pubsub',
                                          prefix=beta_topic,
                                          callback=self.on_receive_beta_message_fncs)

            # Set up initial start and end time of eneeeergy reduction
            self.startEnergyReduction = dateutil.parser.parse("2020-01-01 00:00:00")
            self.endEnergyReduction = dateutil.parser.parse("2020-01-01 00:00:00")
            
            # Initialization of flags
            self.energyReduced = False
            self.energyPeriodCalculated = False
            self.energyCalTime = currTime
            
            # Conduct optimization problem with the default beta values, at the begining of the simulations
            self.energy_reduction()
                        
        def on_receive_setpoint_message_fncs(self, peer, sender, bus, topic, headers, message):
            """Subscribe to appliance setpoint and change the data accordingly 
            """    
            # Find the appliance name
            device = topic.split("/")[-2]
            # Update device setpoint
            setpoint = message[0]
            device_setpoint_val_dict.update({device: setpoint})
#             _log.info('Unit {0:s} setpoint changed to {1} at time {2} '.format(device, setpoint, str(datetime.datetime.now())))

            # Once receive real device setpoint before energy reduction starts, 
            # need to run prediction scripts to get the device delta_T and delta_E relation
            if (self.energyReduced == False) :
                E_1_reduction_temp, E_1_reduction_day, E_3_reduction_temp, E_3_reduction_day = Energy_predict(device_setpoint_val_dict.values()[0], device_setpoint_val_dict.values()[1]) # Now used for two-appliance only case
                device_para['AC1']['setpoint_delta'] = E_1_reduction_temp
                device_para['AC1']['power_delta'] = E_1_reduction_day
                device_para['WH1']['setpoint_delta'] = E_3_reduction_temp
                device_para['WH1']['power_delta'] = E_3_reduction_day
                
        def on_receive_start_time_message_fncs(self, peer, sender, bus, topic, headers, message):
            """Subscribe to energy reduction starting time from UI 
            """    
            # Update device setpoint
            self.startEnergyReduction = dateutil.parser.parse(message[:19])
            
            # Print the starting time
            date_format = "%Y-%m-%dT%H:%M:%S.%fZ" 
            _log.info('Energy reduction starting time is set up as {0} '.format(datetime.datetime.strptime(message[:19], "%Y-%m-%dT%H:%M:%S"), date_format))
        
        def on_receive_end_time_message_fncs(self, peer, sender, bus, topic, headers, message):
            """Subscribe to energy reduction ending time from UI 
            """    
            # Update device setpoint
            self.endEnergyReduction = dateutil.parser.parse(message[:19])
            
            # Print the starting time
            date_format = "%Y-%m-%dT%H:%M:%S.%fZ" 
            _log.info('Energy reduction ending time is set up as {0} '.format(datetime.datetime.strptime(message[:19], "%Y-%m-%dT%H:%M:%S"), date_format))

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
        
        @Core.periodic(1)
        def change_back_setpoints(self):
            ''' This method publishes original setpoint when the energy reduction ends
            '''            
            # Check if energy reduction time arrives
            if (self.energyReduced == True and datetime.datetime.now() >= self.endEnergyReduction):
                _log.info('Energy reduction ends at time {} '.format(str(datetime.datetime.now())))
                            
                # At the energy reduction time, publish the changed setpoints based on optimization function
                now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
                headers = {
                    headers_mod.DATE: now
                }
    
                for device_name in device_setpoint_val_ori_dict:
                    # Publish the original setpoints:
                    pub_topic = 'house/' + device_name + '/' + device_setpoint_val_ori_dict[device_name]
                    _log.info('HEMS agent publishes updated setpoints {0} to unit {1:s} with topic: {2}'.format(device_setpoint_val_ori_dict[device_name], device_name, pub_topic))
                    self.vip.pubsub.publish('pubsub', pub_topic, headers, device_setpoint_val_ori_dict[device_name])
                
                # Set flag
                self.energyReduced = False
        
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
            
            # Predefined market clearing price lambda1
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
            topicE = 'record/skycentrics/energyReduction'
            mesgE =  [{'EstimatedEnergyReduction': totalE
                        },
                       {'EstimatedEnergyReduction': {'units': 'kWh', 'tz': 'UTC', 'type': 'float'}
                        }]
            topicComp = 'record/skycentrics/Compensation'
            mesgComp =  [{
                        'Compensation': net_revenue
                        },
                       {
                        'Compensation': {'units': '$', 'tz': 'UTC', 'type': 'float'}
                        }]
            # Publish all messages
            self.vip.pubsub.publish('pubsub', topicE, headers, mesgE)
            self.vip.pubsub.publish('pubsub', topicComp, headers, mesgComp)
            
#             pub_topic = 'record/energy_reduction'
#             self.vip.pubsub.publish('pubsub', pub_topic, headers, totalE)
#             # Publish total revenue estimated
#             pub_topic = 'fncs/input/house/revenue'
#             self.vip.pubsub.publish('pubsub', pub_topic, headers, revenue)
            
        
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
   
            
            