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
    # load consumption related values initialization
    device_load_topic_dict = {}
    device_load_val_dict = {}
    device_energy_dict = {}
    device_energy_dict_Period = {}
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
        
        # Read in pre-generated device parameters for relationship between setpoint and power changes
        if 'parameters' in config['device']:
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
            self.P_total = 7.0
            
            # Initialize subscription function to change setpoints
            for device_name in device_setpoint_topic_dict:
                _log.info('Subscribing to ' + device_setpoint_topic_dict[device_name])
                setpoint_topic = device_setpoint_topic_dict[device_name]
                self.vip.pubsub.subscribe(peer='pubsub',
                                          prefix=setpoint_topic,
                                          callback=self.on_receive_setpoint_message_fncs)
            
            # Initialize subscription function to energy reduction amount
            _log.info('Subscribing to ' + device_beta_topic_dict[device_name])
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
            
                        
            # Set energy consumption time starts at 14 minutes after simulation begins, and lasts for 3 minutes
            _log.info('Simulation starts from: {}.'.format(str(currTime)))
            self.startEnergyReduction = currTime + datetime.timedelta(minutes=14)
            self.endEnergyReduction = currTime + datetime.timedelta(minutes=17)
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
            beta = message[0]
            device_beta_dict.update({device: beta})
            _log.info('Unit {0:s} beta value changed to {1} at time {2} '.format(device, beta, str(datetime.datetime.now())))  
            
            # Re-conduct optimization problem with the updated beta values, only before energy reduction happens
            if (self.energyReduced == false) :
                # re-conduct optimization
                self.energy_reduction()
        
        def on_receive_energy_reduction_message_fncs(self, peer, sender, bus, topic, headers, message):
            """Subscribe to appliance setpoint and change the data accordingly 
            """    
            # Update energy reduction value
            self.P_total = message[0]
            
            # Re-conduct optimization problem with the updated energy reduction values, only before energy reduction happens
            if (self.energyReduced == false) :
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
            
            # Check if energy reduction time ends
            if (datetime.datetime.now() >= self.endEnergyReduction) and (self.energyPeriodCalculated == False):
                self.energyPeriodCalculated = True # Set flag so that total energy consumption is ony displayed once
                now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
                headers = {
                    headers_mod.DATE: now
                }
                index = 0
                for device_name in device_setpoint_dict:
                    # Publish the original setpoints:
                    pub_topic = 'fncs/input/house/' + device_name + '/' + device_setpoint_dict[device_name]
                    self.vip.pubsub.publish('pubsub', pub_topic, headers, device_setpoint_val_ori_dict[device_name])
                    _log.info('HEMS agent publishes updated setpoints {0} to unit {1:s} with topic: {2}'.format(device_setpoint_val_ori_dict[device_name], device_name, pub_topic))
                    index += 1 
                    # Also update final energy consumption values
                    load_curr = device_load_val_dict[device_name]
                    energy_ori = device_energy_dict_Period[device_name]
                    timediff = self.cal_time_diff(self.endEnergyReduction, self.loadChangeTime[device_name])
                    energy_update = energy_ori + load_curr * timediff / 60
                    device_energy_dict_Period.update({device_name: energy_update})
                    _log.info('unit {0:s} total energy consumption during the energy reduction period is {1:f}'.format(device_name, device_energy_dict_Period[device_name]))
        
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
            
            # Check if energy consumption calculation starts
            if (currTime >= self.startEnergyReduction) and (currTime <= self.endEnergyReduction):
                load_curr = device_load_val_dict[device_name]
                energy_ori = device_energy_dict_Period[device_name]
                if (self.loadChangeTime[device_name] < self.startEnergyReduction): 
                    timediff = self.cal_time_diff(currTime, self.startEnergyReduction)
                    energy_update = energy_ori + load_curr * timediff / 60
                else:
                    timediff = self.cal_time_diff(currTime, self.loadChangeTime[device_name])
                    energy_update = energy_ori + load_curr * timediff / 60
                device_energy_dict_Period.update({device_name: energy_update})
                
            # Write to log the energy consumption whenever load changes
            load_curr = device_load_val_dict[device_name]
            energy_ori = device_energy_dict[device_name]
            timediff = self.cal_time_diff(currTime, self.energyCalTime)
            energy_update = energy_ori + load_curr * timediff / 60
            device_energy_dict.update({device_name: energy_update})
            self.energyCalTime = currTime
            _log.info('unit {0:s}: total energy consumption is {1:f}, load changed to {3:f}, at time {2:s}'.format(device_name, device_energy_dict[device_name], str(datetime.datetime.now()), message[0]))
            
            # Publish the energy consumption as well as the load to the message bus, whenever the load changes
            headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
            topicLoad = 'house/{0:s}/load(kW)'.format(device_name)
            mesgLoad = {'load(kW)': load_curr}
            topicEnergy = 'house/{0:s}/Energy(kWH)'.format(device_name)
            mesgEnergy = {'Energy(kWH)': energy_update}
            topicAll = 'house/{0:s}/all'.format(device_name)
            mesgAll =  [{'load(kW)': load_curr,
                        'Energy(kWH)': energy_update},
                       {'load(kW)': {'units': 'kW', 'tz': 'UTC', 'type': 'float'},
                        'Energy(kWH)': {'units': 'kW', 'tz': 'UTC', 'type': 'float'}
                        }]
            self.vip.pubsub.publish('pubsub', topicLoad, headers, mesgLoad)
            self.vip.pubsub.publish('pubsub', topicEnergy, headers, mesgEnergy)
            # Publish all messages
            self.vip.pubsub.publish('pubsub', topicAll, headers, mesgAll)
            
            # Update device load (kW)
            device_load_val_dict.update({device_name: message[0]})
            self.loadChangeTime[device_name] = currTime

        def energy_reduction(self): 
            
            # variable related to discomfort settings
            lambda_E = 0.1

#             beta_1 = 9.0
#             beta_2 = 12.0
#             beta_3 = 6
                       
            # Maximum power reduction for each appliance
            if 'parameters' in config['device']:
                E_rec1_max = -min(device_para_dict['AC1'][1])
                E_rec2_max = -min(device_para_dict['AC2'][1])
                E_rec3_max = -min(device_para_dict['WH1'][1])
            else: # default values for appliances
                E_rec1_max = float(55.181/(3.6*10))
                E_rec2_max = float(42.646/(3.6*10)) 
                E_rec3_max = float(46.376/(3.6*10))
                
                Coefficient = []
                Coefficient_1 = 692074/(3.6*math.pow(10,6))
                Coefficient_2 = 721164/3.6*math.pow(10,6)
                Coefficient_3 = 470545/3.6*math.pow(10,6)
                Coefficient.append([Coefficient_1, Coefficient_2, Coefficient_3])
            
            # Assign beta values
            beta_1 = device_beta_dict['AC1']
            beta_2 = device_beta_dict['AC2']
            beta_3 = device_beta_dict['WH1']
                
            P_rec1_max = float(E_rec1_max/3)
            P_rec2_max = float(E_rec2_max/3)
            P_rec3_max = float(E_rec3_max/3)
                                  
            # solve the optimization problem
            P = matrix([[float(6*beta_1), 0.0, 0.0], [0.0, float(6*beta_2), 0.0], [0.0, 0.0, float(6*beta_3)]])
            q = matrix([-3 * lambda_E, -3 * lambda_E, -3 *lambda_E])
            G = matrix([[-1.0, 1.0, 0.0, 0.0, 0.0, 0.0], [0.0, 0.0, -1.0, 1.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0, -1.0, 1.0]])
            h = matrix([0, P_rec1_max, 0, P_rec2_max, 0, P_rec3_max])
            A = matrix([3.0, 3.0, 3.0], (1, 3))
#             b = matrix(self.P_total)
            while True:
                try:
                    b = matrix(self.P_total)
                    sol = solvers.qp(P,q,G,h,A,b)
                    if sol['dual infeasibility'] != float("inf") and (sol['x'][0] <= P_rec1_max and sol['x'][1] <= P_rec2_max and sol['x'][2] <= P_rec3_max):
                        break
                    else:
                        self.P_total = self.P_total - 1
                except ValueError:
                       _log.info('The energy reduction requirement {0:f} kWh cannot be met, changed to {1:f}  kWh by default'.format(self.P_total, self.P_total - 1))
                       self.P_total = self.P_total - 1

#             print(sol['x'])
            
            now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
            headers = {
                headers_mod.DATE: now
            }
            
            # Publish the calculated minimum compensation for the occupant
            _log.info('Total minimum compensation for the occupant with chosen preferences [{1:f}, {2:f}, {3:f}] is {0:f} $'.format(sol['primal objective'], beta_1, beta_2, beta_3))
            pub_topic = 'fncs/input/house/minimum_disutility'
            self.vip.pubsub.publish('pubsub', pub_topic, headers, sol['primal objective'])
            
            # Publish the total energy reduction expected
            _log.info('Total energy reduction is {0:f} kWh'.format(self.P_total))
            pub_topic = 'fncs/input/house/energy_reduction'
            self.vip.pubsub.publish('pubsub', pub_topic, headers, self.P_total)
            
            listApp = ['AC1', 'AC2', 'WH1']
            for device_name in device_setpoint_dict:
                index = listApp.index(device_name) # FInd the index of the appliance in the solution list
#                 setpoint = device_setpoint_val_dict[device_name]
                if 'parameters' in config['device']: 
                    setpoint_list = device_para[device_name]['setpoint_delta']
                    power_list = device_para[device_name]['power_delta']
                    interp_func = interp1d(power_list, setpoint_list)
                    diff[device_name] = interp_func(-sol['x'][index]*3)
                else:
                    diff[device_name] = sol['x'][index]*3/Coefficient[index]
#                 diff[device_name] = 0
#                 device_setpoint_val_ori_dict.update({device_name: setpoint})
#                 device_setpoint_val_dict.update({device_name: setpoint + diff[device_name]})
#                 # Publish the changed setpoints:
#                 pub_topic = 'fncs/input/house/' + device_name + '/' + device_setpoint_dict[device_name]
#                 _log.info('HEMS agent publishes updated setpoints {0} to unit {1:s} with topic: {2}'.format(setpoint + diff, device_name, pub_topic))
#                 self.vip.pubsub.publish('pubsub', pub_topic, headers, setpoint + diff)
                
        
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
   
            
            