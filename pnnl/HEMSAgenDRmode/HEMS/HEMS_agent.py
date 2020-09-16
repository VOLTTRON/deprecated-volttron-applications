import datetime
import logging
import sys
import uuid
import math
import json
import random

from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod

from volttron.platform.messaging import topics, headers as headers_mod

from scipy.optimize import fsolve

from os.path import warnings

from get_curve import curve

from AC_market_bid_ideal_accurate import AC_market_bid_ideal_accurate
from AC_Tset_control_ideal import AC_Tset_control_ideal
from WH_market_bid_ideal_accurate import WH_market_bid_ideal_accurate
from WH_Tset_control_ideal import WH_Tset_control_ideal

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
    aggregatorInfo = config['aggregator_information']
    deviceInfos = config['device_information']
    
    device_dict = []
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
        
    agent_id = config.get('agentid', 'HEMS_agent')

    class HEMS_agent_test(Agent):
        '''This agent is used to adjsust setpoint of appliances so that
        minimum disutility price can be achieved. 
        '''
    
        def __init__(self, **kwargs):
            super(HEMS_agent_test, self).__init__(**kwargs)
            
            self.startTime = datetime.datetime.now()
            _log.info('Simulation starts from: {0} in HEMS agent {1}.'.format(str(self.startTime), config['agentid']))
            
            # Initialize controller bids
            self.controller_bid = {}
            self.controller = {} 
            self.subscriptions = {}
                
            # market initialization
            self.aggregator = {'name': 'none', 'market_id': 0, 'average_price': -1, 'std_dev': -1, 'clear_price': -1, 'clear_quantity': 0.0, \
              'initial_price': -1, 'price_cap':9999.0, 'period': -1}
            self.aggregator['market_id'] = aggregatorInfo['market_id']
            self.aggregator['market_unit'] = aggregatorInfo['aggregator_unit']
            self.aggregator['initial_price'] = aggregatorInfo['initial_price']
            self.aggregator['average_price'] = aggregatorInfo['average_price']
            self.aggregator['std_dev'] = aggregatorInfo['std_dev']
            self.aggregator['clear_price'] = aggregatorInfo['clear_price']
            self.aggregator['price_cap'] = aggregatorInfo['price_cap']
            self.aggregator['period'] = aggregatorInfo['period']
            self.P_R = aggregatorInfo['P_R'] # Current utility price, give arbitrary large amount initially - should be obtained from utility
            self.Q_lim = aggregatorInfo['Q_lim'] # Upper limit of total appliance power, give arbitrary large amount initially - should be obtained from OpenADR (unit is kW)
            self.Q_uc = 0.0
            
            # Initialize each device 
            for device_name, deviceInfo in deviceInfos.items():
                
                device_dict.append(device_name)

                agentInitialVal = deviceInfo['initial_value']
                self.agentSubscription = deviceInfo['subscriptions'] 
            
                # controller_bid
                self.controller_bid[device_name] = {'market_id': -1, 'bid_id': 'none', 'bid_price': 0.0, 'bid_quantity': 0, 'bid_accepted': 1, \
                                               'state': 'UNKNOWN', 'rebid': 0, 'Q_min': 0.0, 'Q_max': 0.0}
                
                self.controller[device_name] = {'name': 'none','marketName': 'none', 'device_name': 'none', 'simple_mode': 'none', 'setpoint': 'none', 'lastbid_id': -1, 'lastmkt_id': 0, 'bid_id': 'none', \
                              'slider_setting': -0.001, 'period': -1, 'ramp_low': 0, 'ramp_high': 0, 'range_low': 0, \
                              'range_high': 0, 'dir': 0, 'direction': 0, 'use_predictive_bidding': 0, 'deadband': 0, 'last_p': 0, \
                              'last_q': 0, 'setpoint0': -1, 'minT': 0, 'maxT': 0, 'bid_delay': 60, 'next_run': 0, 't1': 0, 't2': 0, 
                              'use_override': 'OFF', 'control_mode': 'CN_RAMP', 'resolve_mode': 'DEADBAND', 
                              'slider_setting': -0.001, 'slider_setting_heat': -0.001, 'slider_setting_cool': -0.001, 'sliding_time_delay': -1,
                              'heat_range_high': 3, 'heat_range_low': -5, 'heat_ramp_high': 0, 'heating_ramp_low': 0,
                              'cool_range_high': 5, 'cool_range_low': -3, 'cooling_ramp_high': 0, 'cooling_ramp_low': 0,
                              'heating_setpoint0': -1, 'cooling_setpoint0': -1, 'heating_demand': 0, 'cooling_demand': 0,
                              'sliding_time_delay': -1, 
                              'thermostat_mode': 'INVALID',  'last_mode': 'INVALID', 'previous_mode': 'INVALID',
                              'time_off': sys.maxsize,
                              'UA': 0.0, 'mass_heat_coeff': 0.0, 'air_heat_capacity': 0.0, 'mass_heat_capacity': 0.0, 'solar_gain': 0.0, 'heat_cool_gain': 0.0,
                              'outdoor_temperature': 0.0, 'mass_temperature': 0.0, 'design_cooling_capacity':0.0, 'cooling_COP': 0.0,   'Qi': 0.0
                              }
                
                # controller information
                self.controller[device_name]['name'] = device_name #config['agentid']
                self.controller[device_name]['control_mode'] = agentInitialVal['controller_information']['control_mode']
                self.controller[device_name]['aggregatorName'] = agentInitialVal['controller_information']['aggregatorName']
                self.controller[device_name]['houseName'] = agentInitialVal['controller_information']['houseName']
                self.controller[device_name]['bid_id'] = agentInitialVal['controller_information']['bid_id']
                self.controller[device_name]['period'] = agentInitialVal['controller_information']['period']
                self.controller[device_name]['ramp_low'] = agentInitialVal['controller_information']['ramp_low']
                self.controller[device_name]['ramp_high'] = agentInitialVal['controller_information']['ramp_high']
                self.controller[device_name]['range_low'] = agentInitialVal['controller_information']['range_low']
                self.controller[device_name]['range_high'] = agentInitialVal['controller_information']['range_high']
                self.controller[device_name]['setpoint0'] = agentInitialVal['controller_information']['base_setpoint']
                self.controller[device_name]['bid_delay'] = agentInitialVal['controller_information']['bid_delay']
                self.controller[device_name]['use_predictive_bidding'] = agentInitialVal['controller_information']['use_predictive_bidding']
                self.controller[device_name]['use_override'] = agentInitialVal['controller_information']['use_override']
                self.controller[device_name]['last_setpoint'] = self.controller[device_name]['setpoint0']
                self.controller[device_name]['outdoor_temperature'] = agentInitialVal['controller_information']['outdoor_temperature']
                
                # house information  - values will be given after the first time step, thereforely here set as default zero values
                self.controller[device_name]['power_state'] = "ON"
                self.controller[device_name]['deadband'] = 2 
                
                # house information
                self.controller[device_name]['hvac_load'] = agentInitialVal['device_information']['hvac_load']
                self.controller[device_name]['UA'] = agentInitialVal['device_information']['UA']              
                if ('AC' in device_name):
                    self.controller[device_name]['heat_cool_gain'] = agentInitialVal['device_information']['heat_cool_gain']  
                    self.controller[device_name]['air_heat_capacity'] = agentInitialVal['device_information']['air_heat_capacity'] 
                    self.controller[device_name]['MassInternalGainFraction'] = agentInitialVal['device_information']['MassInternalGainFraction'] 
                    self.controller[device_name]['MassSolarGainFraction'] = agentInitialVal['device_information']['MassSolarGainFraction'] 
                    self.controller[device_name]['cooling_COP'] = agentInitialVal['device_information']['cooling_COP'] 
                    self.controller[device_name]['solar_gain'] = agentInitialVal['device_information']['solar_gain'] 
                    self.controller[device_name]['air_temperature'] = self.controller[device_name]['setpoint0'] + self.controller[device_name]['deadband'] * (2 * random.random() - 1)

                elif ('WH' in device_name):
                    self.controller[device_name]['mdot'] = agentInitialVal['device_information']['mdot']  
                    self.controller[device_name]['Cp'] = agentInitialVal['device_information']['Cp'] 
                    self.controller[device_name]['Cw'] = agentInitialVal['device_information']['Cw'] 
                    self.controller[device_name]['Q_elec'] = agentInitialVal['device_information']['Q_elec'] 
                    self.controller[device_name]['T_amb'] = agentInitialVal['device_information']['T_amb'] 
                    self.controller[device_name]['T_inlet'] = agentInitialVal['device_information']['T_inlet'] 
                    self.controller[device_name]['water_flow_temperature'] = self.controller[device_name]['setpoint0'] + self.controller[device_name]['deadband'] * (2 * random.random() - 1)


                # Update controller bidding period:
                if self.controller[device_name]['period'] == 0.0:
                    self.controller[device_name]['period'] = 60
                
                # Check for abnormal input given
                if self.controller[device_name]['use_predictive_bidding'] == 1 and self.controller[device_name]['deadband'] == 0:
                    warnings.warn('Controller deadband property not specified')
                    
                # Calculate dir:
                if self.controller[device_name]['dir'] == 0:
                    high_val = self.controller[device_name]['ramp_high'] * self.controller[device_name]['range_high']
                    low_val = self.controller[device_name]['ramp_low'] * self.controller[device_name]['range_low']
                    if high_val > low_val:
                        self.controller[device_name]['dir'] = 1
                    elif high_val < low_val:
                        self.controller[device_name]['dir'] = -1
                    elif high_val == low_val and (abs(self.controller[device_name]['ramp_high']) > 0.001 or abs(self.controller[device_name]['ramp_low']) > 0.001):
                        self.controller[device_name]['dir'] = 0
                        if abs(self.controller[device_name]['ramp_high']) > 0:
                            self.controller[device_name]['direction'] = 1
                        else:
                            self.controller[device_name]['direction'] = -1
                    if self.controller[device_name]['ramp_low'] * self.controller[device_name]['ramp_high'] < 0:
                        warnings.warn('controller price curve is not injective and may behave strangely')
                
                # Check double_ramp controller mode:
                if self.controller[device_name]['sliding_time_delay'] < 0:
                    self.controller[device_name]['sliding_time_delay'] = 21600 # default sliding_time_delay of 6 hours
                else:
                    self.controller[device_name]['sliding_time_delay'] = int(self.controller[device_name]['sliding_time_delay'])
                
                # use_override
                if self.controller[device_name]['use_override'] == 'ON' and self.controller[device_name]['bid_delay'] <= 0:
                    self.controller[device_name]['bid_delay'] = 1
                  
                # Check slider_setting values
                if self.controller[device_name]['control_mode'] == 'CN_RAMP' or self.controller[device_name]['control_mode'] == 'CN_DOUBLE_PRICE' or self.controller[device_name]['control_mode'] == 'CN_DOUBLE_PRICE_ver2':
                    if self.controller[device_name]['slider_setting'] < -0.001:
                        warnings.warn('slider_setting is negative, reseting to 0.0')
                        self.controller[device_name]['slider_setting'] = 0.0
                    elif self.controller[device_name]['slider_setting'] > 1.0:
                        warnings.warn('slider_setting is greater than 1.0, reseting to 1.0')
                        self.controller[device_name]['slider_setting'] = 1.0
                        
                    # Obtain minnn and max values - presync part in GLD
                    if self.controller[device_name]['slider_setting'] == -0.001:
                        minT = self.controller[device_name]['setpoint0'] + self.controller[device_name]['range_low']
                        maxT = self.controller[device_name]['setpoint0'] + self.controller[device_name]['range_high']
                        
                    elif self.controller[device_name]['slider_setting'] > 0:
                        minT = self.controller[device_name]['setpoint0'] + self.controller[device_name]['range_low'] * self.controller[device_name]['slider_setting']
                        maxT = self.controller[device_name]['setpoint0'] + self.controller[device_name]['range_high'] * self.controller[device_name]['slider_setting']
                        if self.controller[device_name]['range_low'] != 0:
                            self.controller[device_name]['ramp_low'] = 2 + (1 - self.controller[device_name]['slider_setting'])
                        else:
                            self.controller[device_name]['ramp_low'] = 0
                        if self.controller[device_name]['range_high'] != 0:
                            self.controller[device_name]['ramp_high'] = 2 + (1 - self.controller[device_name]['slider_setting'])
                        else:
                            self.controller[device_name]['ramp_high'] = 0
                            
                    else:
                        minT = maxT = self.controller[device_name]['setpoint0']
                    
                    # Update controller parameters
                    self.controller[device_name]['minT'] = minT;
                    self.controller[device_name]['maxT'] = maxT;
                
                # Intialize the controller last time price and quantity 
                self.controller[device_name]['last_p'] = self.aggregator['initial_price']
                self.controller[device_name]['last_q'] = 0
            
                                
            # Intialize controller own parameters (the same for all houses)
            self.controller['lastmkt_id'] = 0
            self.controller['bid_delay'] = agentInitialVal['controller_information']['bid_delay']
            self.controller['period'] = agentInitialVal['controller_information']['period']
            self.controller['next_run'] = self.startTime + datetime.timedelta(0,self.controller['period'])
            self.controller['house_measured_real_power'] = 4.0 # assumed value - should be given by real device measurement
            self.bid = True
            self.cleared = False
    
        @Core.receiver('onsetup')
        def setup(self, sender, **kwargs):
            self._agent_id = config['agentid']
            
        @Core.receiver('onstart')            
        def startup(self, sender, **kwargs):
    
            # Initialize subscription function to change setpoints
            for device_name in device_dict:
                ## Read and define subscription topics from agentSubscription      
                self.subscriptions[device_name] = []
                # Check agentSubscription
                for key, val in self.agentSubscription.items():
                    topic = device_name + '/' + key
                    self.subscriptions[device_name].append(key) # Put house property into subscriptions, rather than topic
                    _log.info('Subscribing to ' + topic)
                    self.vip.pubsub.subscribe(peer='pubsub',
                                              prefix=topic,
                                                  callback=self.on_receive_device_message)
            
            # Initialize subscription function to whole house real power
            topic = 'house/house_measured_real_power'
            _log.info('Subscribing to ' + topic)
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=topic,
                                          callback=self.on_receive_house_measured_real_power)

        # ====================Obtain values from house ===========================
        def on_receive_device_message(self, peer, sender, bus, topic, headers, message):
            """Subscribe to house publications and change the data accordingly 
            """
            # Recieve from real device the property values 
            # Extract the message
            val = float(message)
            # Find the appliance name
            device = topic.split("/")[-2]
            # Find the property
            subscription_property =  topic.split("/")[-1]
            if subscription_property in self.subscriptions[device_name]:
                self.controller[device_name][subscription_property] = val
        
        # ====================Obtain values from meter ===========================
        def on_receive_house_measured_real_power(self, peer, sender, bus, topic, headers, message):
            """Subscribe to house publications and change the data accordingly 
            """
            # Recieve from meter the whole house power data 
            # Extract the message
            val = float(message)
            # Give the value
            self.controller['house_measured_real_power'] = val

        # ====================Obtain values from openADR (not provided by openADR  yet) ===========================
        def on_receive_demand_response_message(self, peer, sender, bus, topic, headers, message):
            """Subscribe to OpenADR demand response information
            """    
            # Update desired cleared quantity from all devices
            self.Q_lim = float(message)
        
        @Core.periodic(1)
        def controller_implementation(self):
            ''' This method comes from the sync and poostsync part of the controller source code in GLD 
            '''    
            self.controller_sync()
            self.clear_market()
            self.controller_postsync()
        
        # ====================Sync content =========================== 
        def controller_sync(self):
            ''' This method comes from the sync and poostsync part of the controller source code in GLD 
            '''        
            # Inputs from market object:
            marketId = self.aggregator['market_id']
            clear_price = self.aggregator['clear_price']
            avgP = self.aggregator['average_price']
            stdP = self.aggregator['std_dev']
            bid_delay = self.controller['bid_delay']
        
            # Update controller t1 information
            self.controller['t1'] = datetime.datetime.now()
            
            # determine what we have to do in this sync step
            update_setpoints = False
            update_bid = False      
            
            if marketId != self.controller['lastmkt_id']:
    #            print ('sync: market changed, need to update the setpoints', t1, next_run, marketId, lastmkt_id)
                update_setpoints = True
                self.controller['lastmkt_id'] = marketId
                
            elif self.controller['t1'] >= self.controller['next_run'] - datetime.timedelta(0,bid_delay) and self.bid == True: # ony allow one bid in one market cycle
    #            print ('sync: t1 within bidding window, need to publish bid and state', t1, next_run - bid_delay)
                update_bid = True
                
            else:
#                 print ('  returning', next_run)
                return 
            
            for device_name in device_dict:
                
                demand = self.controller[device_name]['hvac_load']
                powerstate = self.controller[device_name]['power_state']
                bid_price = -1
                P_min = 0.0
                P_max = 0.0
                Q_max = 0.0
                Q_min = 0.0
                
                if ('AC' in device_name):
                    
                    # Update setpoint after market clears
                    if update_setpoints == True:
                        last_setpoint = AC_Tset_control_ideal(config, self.controller, device_name, self.aggregator, self.controller_bid)
                        self.controller[device_name]['last_setpoint'] = last_setpoint
                        
                                
                        # Publish the changed setpoints:
                        pub_topic = device_name + '/cooling_setpoint'
                    #                         pub_topic = 'fncs/input' + houseGroupId + '/controller_' + houseName + '/cooling_setpoint'
                        _log.info('controller agent {0} publishes updated setpoints {1} to house controlled with topic: {2}'.format(config['agentid'], last_setpoint, pub_topic))
                        #Create timestamp
                        now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
                        headers = {
                            headers_mod.DATE: now
                        }
                        self.vip.pubsub.publish('pubsub', pub_topic, headers, last_setpoint)
                    
                    # Update bid
                    if update_bid == True:
                        bid_price, P_max, P_min, Q_max, Q_min = AC_market_bid_ideal_accurate(self.controller, device_name, self.aggregator)
                
                elif ('WH' in device_name):
                    # Update setpoint after market clears
                    if update_setpoints == True:
                        last_setpoint = WH_Tset_control_ideal(config, self.controller, device_name, self.aggregator, self.controller_bid)
                        self.controller[device_name]['last_setpoint'] = last_setpoint
                        
                        # Publish the changed setpoints:
                        pub_topic = device_name + '/cooling_setpoint'
                    #                         pub_topic = 'fncs/input' + houseGroupId + '/controller_' + houseName + '/cooling_setpoint'
                        _log.info('controller agent {0} publishes updated setpoints {1} to house controlled with topic: {2}'.format(config['agentid'], last_setpoint, pub_topic))
                        #Create timestamp
                        now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
                        headers = {
                            headers_mod.DATE: now
                        }
                        self.vip.pubsub.publish('pubsub', pub_topic, headers, last_setpoint)
                    
                    # Update bid
                    if update_bid == True:
                        bid_price, P_max, P_min, Q_max, Q_min = WH_market_bid_ideal_accurate(self.controller, device_name,  self.aggregator)
                
                else:
                    warnings.warn('Appliace name does not include AC or WH, therefore no setpoint update and no bid update')
                                
                # Update the outputs (no_bid is not used)
                # Update bid price and quantity
                self.controller[device_name]['last_p'] = bid_price
                self.controller[device_name]['last_q'] = demand
                # Check market unit with controller default unit kW
                if (self.aggregator['market_unit']).lower() != "kw":
                    if (self.aggregator['market_unit']).lower() == "w":
                        self.controller[device_name]['last_q'] = self.controller[device_name]['last_q']*1000
                    elif (self.aggregator['market_unit']).lower() == "mw":
                        self.controller[device_name]['last_q'] = self.controller[device_name]['last_q']/1000
                # Update parameters
                self.controller_bid[device_name]['market_id'] = self.controller['lastmkt_id']
                self.controller_bid[device_name]['P_max'] = P_max
                self.controller_bid[device_name]['P_min'] = P_min
                self.controller_bid[device_name]['bid_price'] = self.controller[device_name]['last_p']
                self.controller_bid[device_name]['bid_quantity'] = self.controller[device_name]['last_q']
                self.controller_bid[device_name]['Q_min'] = Q_min
                self.controller_bid[device_name]['Q_max'] = Q_max
               
                # Set controller_bid state
                self.controller_bid[device_name]['state'] = powerstate  
                
                # Issue a bid, if appropriate
                if self.controller_bid[device_name]['bid_quantity'] > 0.0 and self.controller_bid[device_name]['bid_price'] > 0.0:     
                    self.controller_bid[device_name]['rebid'] = 1                   
                  
            # Set the flag as false until the next market cycle    
            self.bid = False 
                
        # ====================clear_market content =========================== 
        def clear_market(self):
            ''' This method clears the market with sorted demand, as well as demand response information 
            '''         
            self.timeSim = datetime.datetime.now() 
                        
            if self.controller['t1'] >= self.controller['next_run'] and self.bid == False:
                
                self.aggregator['market_id'] += 1 # Market id increments by 1
                
                # Obtain uncontrollable load total based on total load consumption, and house consumption
                self.Q_uc = self.controller['house_measured_real_power']
                for device_name in device_dict:
                    if (self.controller[device_name]['hvac_load'] == 'ON'):
                        self.Q_uc -= self.controller[device_name]['hvac_load']
                    
                # Obtain cleared quantity for all appliances, and the cleared price
                Q_clear = 0   
                P_clear = 0
                for device_name in device_dict:
                    Q_clear += self.power_response(self.controller_bid[device_name]['P_min'], self.controller_bid[device_name]['P_max'], self.controller_bid[device_name]['Q_max'], self.controller_bid[device_name]['Q_min'], self.P_R)
                
                if Q_clear <= self.Q_lim - self.Q_uc:
                    P_clear = self.P_R
                else:
                    range_min = 0
                    range_step = 0.001
                    range_max = self.aggregator['price_cap']
                    Q_clear_list = [0.0]*int((range_max - range_min) / range_step)
                    Q_error_list = [0.0]*int((range_max - range_min) / range_step)
                    index = 0
                    Q_clear = 0
                    for P_temp in range(range_max * 1000, range_min - int(range_step * 1000), -int(range_step * 1000)):
                        
                        P_temp = P_temp
                        # Loop through each device with corresponding P_temp
                        for device_name in device_dict:
                            Q_clear += self.power_response(self.controller_bid[device_name]['P_min'], self.controller_bid[device_name]['P_max'], self.controller_bid[device_name]['Q_max'], self.controller_bid[device_name]['Q_min'], P_temp)
                        # Record Q_clear, and Q_error
                        Q_clear_list[index] = Q_clear
                        Q_error_list[index] = Q_clear - (self.Q_lim - self.Q_uc)
                        
                        if Q_error_list[index] >= 0:
                            break
                        
                        index += 1
                        
                    if Q_error_list[index] == 0 or index == 0:
                        P_clear = P_temp
                        Q_clear = Q_clear_list[index]
                    else:
                        P_clear = P_temp + range_step
                        Q_clear = Q_clear_list[index - 1]
                
                    
                # Obtain cleared quantity for each appliance based on cleared price
                Q_clear_dict = {}
                for device_name in device_dict:
                    Q_clear_dict['device_name'] = self.power_response(self.controller_bid[device_name]['P_min'], self.controller_bid[device_name]['P_max'], self.controller_bid[device_name]['Q_max'], self.controller_bid[device_name]['Q_min'], P_clear)
                
                self.aggregator['clear_price'] = P_clear
                self.aggregator['clear_quantity'] = Q_clear
                
                _log.info('At time {2}, HEMS agent {0} with market_id {3} publishes updated cleared price {1} $ to based on cleared quanyity {4} kW'.format(config['agentid'], self.aggregator['clear_price'], self.timeSim.strftime("%Y-%m-%d %H:%M:%S"), self.aggregator['market_id'], self.aggregator['clear_quantity']))
                            
                self.cleared = True
        
        def power_response(self, P_min, P_max, Q_max, Q_min, P):
            
            Qres = 0.0
            
            if Q_max == Q_min:
                Qres = Q_min
            elif P_max == P_min:
                if P > P_max:
                    Qres = Q_min
                else:
                    Qres = Q_max
            else:
                if P >= P_max:
                    Qres = Q_min
                elif P <= P_min:
                    Qres = Q_max
                else:
                    Qres = Q_min + (Q_max - Q_min) * (P - P_max) / (P_min - P_max)
            
            return Qres
            
        def first_index_gt(self, data_list, value):
            '''return the first index greater than value from a given list like object'''
            try:
                index = next(data[0] for data in enumerate(data_list) if data[1] > value)
                return index
            
            except StopIteration: 
                return - 1
           
        # ====================Postsync content =========================== 
        def controller_postsync(self):
            ''' This method comes from the postsync part of the controller source code in GLD 
            '''         
            if self.controller['t1'] >= self.controller['next_run'] and self.cleared == True:
                self.controller['next_run'] += datetime.timedelta(0,self.controller['period'])
                self.bid = True
                self.cleared = False

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
   
            
            