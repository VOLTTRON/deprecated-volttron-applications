import datetime
import logging
import sys
import uuid
import math
import json

from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod

from volttron.platform.messaging import topics, headers as headers_mod

from scipy.interpolate import interp1d
from scipy.optimize import fsolve

from cvxopt import matrix, solvers
from os.path import warnings

from get_curve import curve

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
    fncs_bridgeInfo = config['fncs_bridge']
    
    P_R = 65.00 # Current utility price, give arbitrary large amount initially - should be obtained from utility
    Q_lim = 4 # Upper limit of total appliance power, give arbitrary large amount initially - should be obtained from OpenADR (unit is kW)
    Q_uc = 0
    
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
            
            # Initialize each device 
            for device_name, deviceInfo in deviceInfos.items():
                
                device_dict.append(device_name)

                agentInitialVal = deviceInfo['initial_value']
                agentSubscription = deviceInfo['subscriptions'] 
            
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
                              'UA': 0.0, 'mass_heat_coeff': 0.0, 'air_heat_capacity_cd': 0.0, 'mass_heat_capacity': 0.0, 'solar_gain': 0.0, 'heat_cool_gain': 0.0,
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
                # Read in pre-run and default data
                self.controller[device_name]['hvac_load'] = agentInitialVal['controller_information']['hvac_load']
                self.controller[device_name]['heat_cool_gain'] = agentInitialVal['controller_information']['heat_cool_gain']              
                 
                # house information  - values will be given after the first time step, thereforely here set as default zero values
                self.controller[device_name]['air_temperature'] = 0
                self.controller[device_name]['power_state'] = "ON"
                self.controller[device_name]['target'] = "air_temperature"
                self.controller[device_name]['deadband'] = 2 
                self.controller[device_name]['MassInternalGainFraction'] = 0.5
                self.controller[device_name]['MassSolarGainFraction'] = 0.5
#                 self.controller[device_name]['Qi'] = 6819.0
#                 self.controller[device_name]['cooling_COP'] = 4.07
                
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
                    
                # Intialize controller own parameters (the same for all houses)
                self.controller['lastmkt_id'] = 0
                self.controller['bid_delay'] = agentInitialVal['controller_information']['bid_delay']
                self.controller['period'] = agentInitialVal['controller_information']['period']
                self.controller['next_run'] = self.startTime + datetime.timedelta(0,self.controller['period'])
                self.bid = True
                self.cleared = False
                
                # Intialize the controller last time price and quantity 
                self.controller[device_name]['last_p'] = self.aggregator['initial_price']
                self.controller[device_name]['last_q'] = 0
        
                ## Read and define subscription topics from agentSubscription      
                self.subscriptions[device_name] = []
                # Check agentSubscription
                for key, val in agentSubscription.items():
                    # topic = 'fncs/output/devices/fncs_Test/' + key + '/' + key2
                    self.subscriptions[device_name].append(key) # Put house property into subscriptions, rather than topic
                
            # Subscription to houses in GridLAB-D needs to post-process JSON format messages of all GLD objects together
            subscription_topic = 'fncs/output/devices/fncs_Test/fncs_output'
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=subscription_topic,
                                      callback=self.on_receive_house_message_fncs)
            
            # Initialize subscription function to fncs_bridge:
            topic = 'FNCS_Volttron_Bridge/simulation_end'
            _log.info('Subscribing to ' + topic)
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=topic,
                                          callback=self.on_receive_fncs_bridge_message_fncs)
            
            # Initialize subscription function to OpenADR demand response:
            topic = 'openadr/demand_response'
            _log.info('Subscribing to ' + topic)
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=topic,
                                          callback=self.on_receive_fncs_bridge_message_fncs)

    
        @Core.receiver('onsetup')
        def setup(self, sender, **kwargs):
            self._agent_id = config['agentid']

        # ====================Obtain values from house ===========================
        def on_receive_house_message_fncs(self, peer, sender, bus, topic, headers, message):
            """Subscribe to house publications and change the data accordingly 
            """
            # Recieve from GLD the property values of all configured objects, need to extract the house objects and the corresponding properties
            # Extract the message
            message = json.loads(message[0])
            val =  message['fncs_Test']
            
            for device_name in device_dict:
                # Assign to subscription topics
                for subscription_property in self.subscriptions[device_name]:
                    valTemp = val[device_name][subscription_property]
                    if valTemp != self.controller[device_name][subscription_property]:
                        if subscription_property != 'power_state':
                            valTemp = float(valTemp)
                            # Record hvac load value only when non-zero
                            if (subscription_property == 'hvac_load'):
                                if (valTemp > 0.0):
                                    self.controller[device_name][subscription_property] = valTemp
                            else:
                                self.controller[device_name][subscription_property] = valTemp
                        else:        
                            self.controller[device_name][subscription_property] = valTemp
            
            # Obtain uncontrollable load total based on total load consumption, and house consumption
            Q_uc = val['trip_swing']['measured_real_power']
            for device_name in device_dict:
                Q_uc -= self.controller[device_name]['hvac_load']

        # ====================Obtain values from openADR ===========================
        def on_receive_demand_response_message(self, peer, sender, bus, topic, headers, message):
            """Subscribe to OpenADR demand response information
            """    
            # Update desired cleared quantity from all devices
            self.Q_lim = float(message)

        # ====================Obtain values from fncs_bridge ===========================
        def on_receive_fncs_bridge_message_fncs(self, peer, sender, bus, topic, headers, message):
            """Subscribe to fncs_bridge publications, change appliance setpoints back, and summarize the total energy reduction
            """    
            val =  message[0] # value True
            if (val == 'True'):
                _log.info('----------------- HEMS agent recieves from fncs_bridge the simulation ending signal -----------------------')
                
                # Stop HEMS agent
                self.core.stop() 
        
        def calTmpONOFF(self, Ua, Hm, Ca, Cm, MassInternalGainFraction, MassSolarGainFraction, Qi, Qs, Qh, Tout, monitor, Tmass, deadband, powerstate):
            '''
            This function calculates tmpON tmpOFF from house properties 
            '''
            # ================================================== TEST =========================================================
#             monitor = 65.9015341345
#             Ua = 558.459343583
#             Hm = 3647.56505984
#             Ca = 270.280463141
#             Cm = 2569.73957057
#             MassInternalGainFraction = 0.5
#             MassSolarGainFraction = 0.5
#             Qi = 6819.0
#             Qs = 0.0
#             Tout = 75.0
#             Tmass = 68.9278803355
#             powerstate = 'ON'
#             Qh = -34905.8191257
#             P_cap = 0.999
#             hvac_power = 4.5
#              
#             deadband = 2.0
#             deadband_shift = deadband / 2.0
#               
#             setpoint0 = 72.45
#             avgP = 65
#             stdP = 16
#             maxT = 80.2992330639
#             minT = 67.4306110535
#             ramp_high = 1.7248877792031796
#             range_high = 5.6557938070185285
#             ramp_low = 1.7232495193001907
#             range_low = -5.721968142500344
#              
#             self.controller = {}
#             self.controller['period'] = 300
#             self.controller['bid_delay'] = 10
#                         
#             # ==================================================TEST =========================================================
            Qh_estimate = 0.0
            Qh_average = 0.0
            Qh_count = 0.0
            
            if Qh < 0.0:
                Qh_estimate = Qh
                if Qh_count > 0.0:
                    Qh_average = (Qh_average * Qh_count + Qh) / (Qh_count + 1.0)
                    Qh_count = Qh_count + 1.0
                else:
                    Qh_average = Qh
                    Qh_count = 1.0
            else:
                Qh_estimate = Qh_average
            
            Qa_OFF = ((1 - MassInternalGainFraction)*Qi) + ((1 - MassSolarGainFraction)*Qs)
            Qa_ON = Qh + ((1 - MassInternalGainFraction)*Qi) + ((1 - MassSolarGainFraction)*Qs)
            Qm = (MassInternalGainFraction*Qi) + (MassSolarGainFraction*Qs)
            A_ETP = [[0.0, 0.0],[0.0, 0.0]]
            B_ETP_ON = [0.0, 0.0]
            B_ETP_OFF = [0.0, 0.0]
            x = [monitor, Tmass]
            L = [1.0, 0.0]
            T = (self.controller['bid_delay'] + self.controller['period']) / 3600.0
            AEI = [[0.0, 0.0], [0.0, 0.0]]
            LAEI = [0.0, 0.0]
            AET = [[0.0, 0.0], [0.0, 0.0]]
            eAET = [[0.0, 0.0], [0.0, 0.0]]
            LT = [0.0, 0.0]
            AEx = [0.0, 0.0]
            AxB_ON = [0.0, 0.0]
            AxB_OFF = [0.0, 0.0]
            LAxB = 0.0
            LAIB = 0.0
            Tmax = 0.0
            if Ca != 0.0:
                A_ETP[0][0] = -1.0 * (Ua + Hm) / Ca
                A_ETP[0][1] = Hm / Ca
                B_ETP_ON[0] = (Ua * Tout / Ca) + (Qa_ON / Ca)
                B_ETP_OFF[0] = (Ua * Tout / Ca) + (Qa_OFF / Ca);
            if Cm != 0.0:
                A_ETP[1][0] = Hm / Cm
                A_ETP[1][1] = -1.0 * Hm / Cm
                B_ETP_ON[1] = Qm / Cm
                B_ETP_OFF[1] = Qm / Cm
            
            # Calculate inverse of A_ETP
            detA = 0.0
            if(((A_ETP[0][0]*A_ETP[1][1]) - (A_ETP[0][1]*A_ETP[1][0])) != 0.0):
                detA = ((A_ETP[0][0]*A_ETP[1][1]) - (A_ETP[0][1]*A_ETP[1][0]))
                AEI[0][0] = A_ETP[1][1]/detA
                AEI[0][1] = -1*A_ETP[0][1]/detA
                AEI[1][1] = A_ETP[0][0]/detA
                AEI[1][0] = -1*A_ETP[1][0]/detA
            else:
                if powerstate == 'OFF':
                    return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
#                     return monitor - deadband / 2.0
                else:
                    return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
#                     return monitor + deadband / 2.0
            
            # Calculate exp(A_ETP*T)
            AET[0][0] = A_ETP[0][0]*T
            AET[0][1] = A_ETP[0][1]*T
            AET[1][0] = A_ETP[1][0]*T
            AET[1][1] = A_ETP[1][1]*T
            if (AET[0][1] == 0.0 and AET[1][0] == 0.0): #diagonal matrix
                eAET[0][0] = math.exp(AET[0][0])
                eAET[0][1] = 0.0
                eAET[1][0] = 0.0
                eAET[1][1] = math.exp(AET[1][1])
            elif AET[1][0] == 0.0: # upper triangular matrix
                if(math.fabs(AET[0][0] - AET[1][1]) <= 1e-37): #nilpotent
                    eAET[0][0] = math.exp(AET[0][0])
                    eAET[0][1] = math.exp(AET[0][0]) * AET[0][1]
                    eAET[1][0] = 0.0
                    eAET[1][1] = math.exp(AET[0][0])
                else:
                    eAET[0][0] = math.exp(AET[0][0])
                    eAET[0][1] = (AET[0][1]*(math.exp(AET[0][0]) - math.exp(AET[1][1])))/(AET[0][0] - AET[1][1])
                    eAET[1][0] = 0.0
                    eAET[1][1] = math.exp(AET[1][1])
            else:
                discr = (AET[0][0] - AET[1][1])*(AET[0][0] - AET[1][1]) + (4.0*AET[0][1]*AET[1][0])
                pre = math.exp((AET[0][0] + AET[1][1])/2.0)
                g = 0.0
                if(math.fabs(discr) <= 1e-37):
                    eAET[0][0] = pre*(1.0 + ((AET[0][0] - AET[1][1])/2.0))
                    eAET[0][1] = pre*AET[0][1]
                    eAET[1][0] = pre*AET[1][0]
                    eAET[1][1] = pre*(1.0 - ((AET[0][0] - AET[1][1])/2.0))
                elif (discr > 1e-37):
                    g = 0.5*math.sqrt(discr)
                    eAET[0][0] = pre*(math.cosh(g) + ((AET[0][0] - AET[1][1])*math.sinh(g)/(2.0*g)))
                    eAET[0][1] = pre*AET[0][1]*math.sinh(g)/g
                    eAET[1][0] = pre*AET[1][0]*math.sinh(g)/g
                    eAET[1][1] = pre*(math.cosh(g) - ((AET[0][0] - AET[1][1])*math.sinh(g)/(2.0*g)))
                else:
                    g = 0.5*math.sqrt(math.fabs(discr));
                    eAET[0][0] = pre*(math.cos(g) + ((AET[0][0] - AET[1][1])*math.sin(g)/(2.0*g)))
                    eAET[0][1] = pre*AET[0][1]*math.sin(g)/g
                    eAET[1][0] = pre*AET[1][0]*math.sin(g)/g
                    eAET[1][1] = pre*(math.cos(g) - ((AET[0][0] - AET[1][1])*math.sin(g)/(2.0*g)))

            # Calculate L*inv(A_ETP)
            LAEI[0] = (L[0]*AEI[0][0]) + (L[1]*AEI[1][0])
            LAEI[1] = (L[0]*AEI[0][1]) + (L[1]*AEI[1][1])
            # Calculate L*inv(A_ETP)expm(A_ETP*T)
            LT[0] = (LAEI[0]*eAET[0][0]) + (LAEI[1]*eAET[1][0])
            LT[1] = (LAEI[0]*eAET[0][1]) + (LAEI[1]*eAET[1][1])
            # Calculate A_ETP*x
            AEx[0] = (A_ETP[0][0]*x[0]) + (A_ETP[0][1]*x[1])
            AEx[1] = (A_ETP[1][0]*x[0]) + (A_ETP[1][1]*x[1])
            # Calculate A_ETP*x + B_ETP_ON/OFF
            AxB_OFF[0] = AEx[0] + B_ETP_OFF[0]
            AxB_OFF[1] = AEx[1] + B_ETP_OFF[1]
            AxB_ON[0] = AEx[0] + B_ETP_ON[0]
            AxB_ON[1] = AEx[1] + B_ETP_ON[1]
            # Calculate L*inv(A_ETP)expm(A_ETP*T)(A_ETP*x + B_ETP_ON/OFF)
            LAxB_ON = (LT[0]*AxB_ON[0]) + (LT[1]*AxB_ON[1])
            LAxB_OFF = (LT[0]*AxB_OFF[0]) + (LT[1]*AxB_OFF[1])
            # Calculate L*inv(A_ETP)*B_ETP_ON/OFF
            LAIB_OFF = (LAEI[0]*B_ETP_OFF[0]) + (LAEI[1]*B_ETP_OFF[1])
            LAIB_ON = (LAEI[0]*B_ETP_ON[0]) + (LAEI[1]*B_ETP_ON[1])
            
            # Calculate L*inv(A_ETP)expm(A_ETP*T)(A_ETP*x + B_ETP_ON/OFF) - L*inv(A_ETP)*B_ETP_ON/OFF
            tmpOFF = LAxB_OFF - LAIB_OFF
            tmpON = LAxB_ON - LAIB_ON
    
            return A_ETP, AEI, B_ETP_OFF, B_ETP_ON, x, tmpOFF, tmpON
        
        def compute_time(self, A_ETP, AEI, B_ETP, T0, T1):
            '''
            Compute turnning on/off time taken
            '''
            
            data = (A_ETP, AEI, B_ETP, T0, T1)
            res = fsolve(self.funcComputeTime, 0.0, args=data)
            
            return res
        
        def funcComputeTime(self, x, *data):
            
            # Initialization
            A_ETP, AEI, B_ETP, T0, T1 = data
            
            eAET = [[0.0, 0.0], [0.0, 0.0]]
            eAETx =  [0.0, 0.0]
            AET = [[0.0, 0.0], [0.0, 0.0]]
            AeAEIx = [[0.0, 0.0], [0.0, 0.0]]
            invAeAETxB = [0.0, 0.0]
            LAEI = [0.0, 0.0]
            L = [1.0, 0.0]
            LT = [0.0, 0.0]
            
            # Calculate exp(A_ETP*x)
            AET[0][0] = A_ETP[0][0]*x
            AET[0][1] = A_ETP[0][1]*x
            AET[1][0] = A_ETP[1][0]*x
            AET[1][1] = A_ETP[1][1]*x
            if (AET[0][1] == 0.0 and AET[1][0] == 0.0): #diagonal matrix
                eAET[0][0] = math.exp(AET[0][0])
                eAET[0][1] = 0.0
                eAET[1][0] = 0.0
                eAET[1][1] = math.exp(AET[1][1])
            elif AET[1][0] == 0.0: # upper triangular matrix
                if(math.fabs(AET[0][0] - AET[1][1]) <= 1e-37): #nilpotent
                    eAET[0][0] = math.exp(AET[0][0])
                    eAET[0][1] = math.exp(AET[0][0]) * AET[0][1]
                    eAET[1][0] = 0.0
                    eAET[1][1] = math.exp(AET[0][0])
                else:
                    eAET[0][0] = math.exp(AET[0][0])
                    eAET[0][1] = (AET[0][1]*(math.exp(AET[0][0]) - math.exp(AET[1][1])))/(AET[0][0] - AET[1][1])
                    eAET[1][0] = 0.0
                    eAET[1][1] = math.exp(AET[1][1])
            else:
                discr = (AET[0][0] - AET[1][1])*(AET[0][0] - AET[1][1]) + (4.0*AET[0][1]*AET[1][0])
                pre = math.exp((AET[0][0] + AET[1][1])/2.0)
                g = 0.0
                if(math.fabs(discr) <= 1e-37):
                    eAET[0][0] = pre*(1.0 + ((AET[0][0] - AET[1][1])/2.0))
                    eAET[0][1] = pre*AET[0][1]
                    eAET[1][0] = pre*AET[1][0]
                    eAET[1][1] = pre*(1.0 - ((AET[0][0] - AET[1][1])/2.0))
                elif (discr > 1e-37):
                    g = 0.5*math.sqrt(discr)
                    eAET[0][0] = pre*(math.cosh(g) + ((AET[0][0] - AET[1][1])*math.sinh(g)/(2.0*g)))
                    eAET[0][1] = pre*AET[0][1]*math.sinh(g)/g
                    eAET[1][0] = pre*AET[1][0]*math.sinh(g)/g
                    eAET[1][1] = pre*(math.cosh(g) - ((AET[0][0] - AET[1][1])*math.sinh(g)/(2.0*g)))
                else:
                    g = 0.5*math.sqrt(math.fabs(discr));
                    eAET[0][0] = pre*(math.cos(g) + ((AET[0][0] - AET[1][1])*math.sin(g)/(2.0*g)))
                    eAET[0][1] = pre*AET[0][1]*math.sin(g)/g
                    eAET[1][0] = pre*AET[1][0]*math.sin(g)/g
                    eAET[1][1] = pre*(math.cos(g) - ((AET[0][0] - AET[1][1])*math.sin(g)/(2.0*g)))
            
            # Fomulate the function with x
            # Calculate expm(A_ETP*x)*T0
            eAETx[0] = (eAET[0][0]*T0[0]) + (eAET[0][1]*T0[1])
            eAETx[1] = (eAET[1][0]*T0[0]) + (eAET[1][1]*T0[1])
            # Calculate L*inv(A_ETP)
            LAEI[0] = (L[0]*AEI[0][0]) + (L[1]*AEI[1][0])
            LAEI[1] = (L[0]*AEI[0][1]) + (L[1]*AEI[1][1])
            # Calculate inv(A_ETP)(expm(A_ETP*T)-eye(2))
            AeAEIx[0][0] = (AEI[0][0]*(eAET[0][0] - 1.0)) + (AEI[0][1]*eAET[1][0])
            AeAEIx[0][1] = (AEI[0][0]*eAET[0][1]) + (AEI[0][1]*(eAET[1][1] - 1.0))
            AeAEIx[1][0] = (AEI[1][0]*(eAET[0][0] - 1)) + (AEI[1][1]*eAET[1][0])
            AeAEIx[1][1] = (AEI[1][0]*eAET[0][1]) + (AEI[1][1]*(eAET[1][1] - 1.0))
            # Calculate inv(A_ETP)(expm(A_ETP*x)-eye(2))*B_ETP_ON/OFF
            invAeAETxB[0] = (AeAEIx[0][0]*B_ETP[0]) + (AeAEIx[0][1]*B_ETP[1])
            invAeAETxB[1] = (AeAEIx[1][0]*B_ETP[0]) + (AeAEIx[1][1]*B_ETP[1])
            # Calculate (expm(A_ETP*x)*T0 + inv(A_ETP)(expm(A_ETP*x)-eye(2))*B_ETP_ON/OFF)' * L - T1
            func = eAETx[0] + invAeAETxB[0] - T1
            
            return func
        
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

                # Inputs from controller:
                houseName = self.controller[device_name]['houseName']
                ramp_low = self.controller[device_name]['ramp_low']
                ramp_high = self.controller[device_name]['ramp_high']
                range_low = self.controller[device_name]['range_low']
                range_high = self.controller[device_name]['range_high']
                deadband = self.controller[device_name]['deadband']
                setpoint0 = self.controller[device_name]['setpoint0']
                last_setpoint = self.controller[device_name]['last_setpoint']
                minT = self.controller[device_name]['minT']
                maxT = self.controller[device_name]['maxT']
#                 bid_delay = self.controller[device_name]['bid_delay']
                direction = self.controller[device_name]['direction']
                
                # Inputs from house object:
                demand = self.controller[device_name]['hvac_load']
                monitor = self.controller[device_name]['air_temperature']
                powerstate = self.controller[device_name]['power_state']
                
                # variables needed for double_price bid mode
                Ua = self.controller[device_name]['UA']
                Hm = self.controller[device_name]['mass_heat_coeff']
                Ca = self.controller[device_name]['air_heat_capacity_cd']
                Cm = self.controller[device_name]['mass_heat_capacity']
                MassInternalGainFraction = self.controller[device_name]['MassInternalGainFraction']
                MassSolarGainFraction = self.controller[device_name]['MassSolarGainFraction']
                Qi = self.controller[device_name]['Qi']
                Qs = self.controller[device_name]['solar_gain']
                Qh = self.controller[device_name]['heat_cool_gain']
                Tout = self.controller[device_name]['outdoor_temperature']
                Tmass = self.controller[device_name]['mass_temperature']
        
        #        print ("  sync:", demand, power_state, monitor, last_setpoint, deadband, direction, clear_price, avgP, stdP)

                deadband_shift = 0.5 * deadband
                
                #  controller update house setpoint if market clears
                if self.controller[device_name]['control_mode'] == 'CN_RAMP' or self.controller[device_name]['control_mode'] == 'CN_DOUBLE_PRICE' or self.controller[device_name]['control_mode'] == 'CN_DOUBLE_PRICE_ver2':
                     # If market clears, update the setpoints based on cleared market price;
                     # Or, at the beginning of the simlation, update house setpoint based on controller settings (lastmkt_id == -1 at the begining, therefore will go through here)
#                     if marketId != lastmkt_id: 
                    if update_setpoints == True: 
                        
                        # Update controller last market id and bid id
#                         self.controller[device_name]['lastmkt_id'] = marketId
                        self.controller[device_name]['lastbid_id'] = -1
                        self.controller_bid[device_name]['rebid'] = 0 
                        
                        # Calculate shift direction
                        shift_direction = 0
                        if self.controller[device_name]['control_mode'] == 'CN_RAMP' and self.controller[device_name]['use_predictive_bidding'] == 1:
                            if (self.controller[device_name]['dir'] > 0 and clear_price < self.controller[device_name]['last_p']) or (self.controller[device_name]['dir'] < 0 and clear_price > self.controller[device_name]['last_p']):
                                shift_direction = -1
                            elif (self.controller[device_name]['dir'] > 0 and clear_price >= self.controller[device_name]['last_p']) or (self.controller[device_name]['dir'] < 0 and clear_price <= self.controller[device_name]['last_p']):
                                shift_direction = 1
                            else:
                                shift_direction = 0
                                
                        # Calculate updated set_temp
                        if self.controller[device_name]['control_mode'] == 'CN_RAMP':
                            if abs(stdP) < 0.0001:
                                set_temp = setpoint0
                            elif clear_price < avgP and range_low != 0:
                                set_temp = setpoint0 + (clear_price - avgP) * abs(range_low) / (ramp_low * stdP) + deadband_shift*shift_direction
                            elif clear_price > avgP and range_high != 0:
                                set_temp = setpoint0 + (clear_price - avgP) * abs(range_high) / (ramp_high * stdP) + deadband_shift*shift_direction
                            else:
                                set_temp = last_setpoint # setpoint0 + deadband_shift*shift_direction
                        else:
                            if abs(stdP) < 0.0001:
                                set_temp = setpoint0
                            elif clear_price < avgP and range_low != 0:
                                set_temp = setpoint0 + (clear_price - avgP) * abs(range_low) / (ramp_low * stdP)
                            elif clear_price > avgP and range_high != 0:
                                set_temp = setpoint0 + (clear_price - avgP) * abs(range_high) / (ramp_high * stdP)
                            else:
                                set_temp = last_setpoint #setpoint0
                        
                        # Check if set_temp is out of limit
                        if set_temp > maxT:
                            set_temp = maxT
                        elif set_temp < minT:
                            set_temp = minT
                        
                        # Update last_setpoint if changed
                        if last_setpoint != set_temp:
                            self.controller[device_name]['last_setpoint'] = set_temp
                            
                        # Publish the changed setpoints:
                        pub_topic = 'fncs/input/' + houseName + '/cooling_setpoint'
#                         pub_topic = 'fncs/input' + houseGroupId + '/controller_' + houseName + '/cooling_setpoint'
                        _log.info('controller agent {0} publishes updated setpoints {1} to house controlled with topic: {2}'.format(config['agentid'], set_temp, pub_topic))
                        #Create timestamp
                        now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
                        headers = {
                            headers_mod.DATE: now
                        }
                        self.vip.pubsub.publish('pubsub', pub_topic, headers, set_temp)
                    
                    # Calculate bidding price - only put CN_DOUBLE_PRICE_ver2 here for HEMS agent
                    if self.controller[device_name]['control_mode'] == 'CN_DOUBLE_PRICE_ver2':
                        
                        # Initialization of variables
                        P_min = 0.0
                        P_max = 0.0
#                         P_bid = 0.0
                        Q_max = 0.0
                        Q_min = 0.0
                        
                        T_min = 0.0
                        T_max = 0.0
                        
                        mdt = (self.controller['period']) / 3600.0
                        
                        # Calculate tmpON tmpOFF from house properties             
                        A_ETP, AEI, B_ETP_OFF, B_ETP_ON, T_a, tmpOFF, tmpON = self.calTmpONOFF(Ua, Hm, Ca, Cm, MassInternalGainFraction, MassSolarGainFraction, Qi, Qs, Qh, Tout, monitor, Tmass, deadband, powerstate)
                        
                        if A_ETP != 0.0:
                            # Calculate bidding T_min, T_max, Q_min, Q_max                   
                            if powerstate == 'OFF':
                
                                if (monitor <= minT + deadband_shift) and (tmpOFF <= minT + deadband_shift):
                                    Q_max = 0
                                    T_min = minT
                                    Q_min = 0
                                    T_max = minT
                                if (monitor < minT + deadband_shift) and (tmpOFF > minT + deadband_shift):
                                    tOFF = self.compute_time(A_ETP, AEI, B_ETP_OFF, T_a, minT + deadband_shift)[0]
                                    Q_max = (mdt - tOFF) / mdt * demand
                                    T_min = minT
                                    Q_min = 0
                                    T_max = tmpOFF - deadband_shift
                                if (monitor == minT + deadband_shift) and (tmpOFF > minT + deadband_shift):
                                    if tmpON >= minT - deadband_shift:
                                        Q_max = demand
                                    else:
                                        tON = self.compute_time(A_ETP, AEI, B_ETP_ON, T_a, minT - deadband_shift)[0]
                                        Q_max = tON / mdt * demand
                                    T_min = minT
                                    Q_min = 0
                                    T_max = tmpOFF - deadband_shift
                                if monitor > minT + deadband_shift:
                                    if tmpON >= minT - deadband_shift:
                                        Q_max = demand
                                        T_min = min(T_a[0] - deadband_shift, tmpON + deadband_shift)
                                    else:
                                        tON = self.compute_time(A_ETP, AEI, B_ETP_ON, T_a, minT - deadband_shift)[0]
                                        Q_max = tON / mdt * demand
                                        T_min = T_a[0] - deadband_shift
                                    if tmpOFF <= maxT + deadband_shift:
                                        Q_min = 0
                                        T_max = max(T_a[0] - deadband_shift, tmpOFF - deadband_shift)
                                    else:
                                        tOFF = self.compute_time(A_ETP, AEI, B_ETP_OFF, T_a, maxT + deadband_shift)[0]
                                        Q_min = (mdt - tOFF) / mdt * demand
                                        T_max = maxT
                            
                            if powerstate == 'ON':
                
                                if (monitor >= maxT - deadband_shift) and (tmpON >= maxT - deadband_shift):
                                    Q_max = demand
                                    T_min = maxT
                                    Q_min = demand
                                    T_max = maxT
                                if (monitor > maxT - deadband_shift) and (tmpON < maxT - deadband_shift):
                                    Q_max = demand
                                    T_min = tmpON + deadband_shift
                                    tON = self.compute_time(A_ETP, AEI, B_ETP_ON, T_a, maxT - deadband_shift)[0]
                                    Q_min = tON / mdt * demand
                                    T_max = maxT
                                if (monitor == maxT - deadband_shift) and (tmpON < maxT - deadband_shift):
                                    Q_max = demand
                                    T_min = tmpON + deadband_shift                    
                                    if tmpOFF <= maxT + deadband_shift:
                                        Q_min = 0
                                    else:
                                        tOFF = self.compute_time(A_ETP, AEI, B_ETP_OFF, T_a, maxT + deadband_shift)[0]
                                        Q_min = (mdt - tOFF) / mdt * demand
                                    T_max = maxT
                                if monitor < maxT - deadband_shift:
                                    if tmpOFF <= maxT + deadband_shift:
                                        Q_min = 0
                                        T_max = max(T_a[0] + deadband_shift, tmpOFF - deadband_shift)
                                    else:
                                        tOFF = self.compute_time(A_ETP, AEI, B_ETP_OFF, T_a, maxT + deadband_shift)[0]
                                        Q_min = (mdt - tOFF) / mdt * demand
                                        T_max = T_a[0] + deadband_shift
                                    if tmpON >= minT - deadband_shift:
                                        Q_max = demand
                                        T_max = min(T_a[0] + deadband_shift, tmpON + deadband_shift)
                                    else:
                                        tON = self.compute_time(A_ETP, AEI, B_ETP_ON, T_a, minT - deadband_shift)[0]
                                        Q_max = tON / mdt * demand
                                        T_min = minT
                        
                        if (Q_min == Q_max) and (Q_min == 0):
                            P_min = 0.0
                            P_max = 0.0
                            bid_price = 0.0
                        elif (Q_min == Q_max) and (Q_min > 0):
                            P_min = P_cap
                            P_max = P_cap
                            bid_price = P_cap
                            Q_min = 0.0
                        else:
                            bid_price = -1
                            no_bid = 0

                            # Bidding price when T_avg temperature is within the controller temp limit
                            # Tmin
                            P_min = -1
                            if T_min > setpoint0:
                                k_T = ramp_high
                                T_lim = range_high
                            elif T_min < setpoint0:
                                k_T = ramp_low
                                T_lim = range_low
                            else:
                                k_T = 0
                                T_lim = 0
                            
                            bid_offset = 0.0001
                            if P_min < 0 and T_min != setpoint0:
                                P_min = avgP + (T_min - setpoint0)*(k_T * stdP) / abs(T_lim)   
                            elif T_min == setpoint0:
                                P_min = avgP
                            
                            if P_min < max(avgP - k_T * stdP, 0):
                                P_min = 0
                            if P_min > min(self.aggregator['price_cap'], avgP + k_T * stdP):
                                P_min = self.aggregator['price_cap']
                                
                            # Tmax
                            P_max = -1
                            if T_max > setpoint0:
                                k_T = ramp_high
                                T_lim = range_high
                            elif T_max < setpoint0:
                                k_T = ramp_low
                                T_lim = range_low
                            else:
                                k_T = 0
                                T_lim = 0
                            
                            bid_offset = 0.0001
                            if P_max < 0 and T_max != setpoint0:
                                P_max = avgP + (T_max - setpoint0)*(k_T * stdP) / abs(T_lim)   
                            elif T_max == setpoint0:
                                P_max = avgP
                            
                            if P_max < max(avgP - k_T * stdP, 0):
                                P_max = 0
                            if P_max > min(self.aggregator['price_cap'], avgP + k_T * stdP):
                                P_max = self.aggregator['price_cap']
                            
                            bid_price = (P_max + P_min) / 2.0

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
                
                # Obtain cleared quantity for all appliances, and the cleared price
                Q_clear = 0   
                P_clear = 0
                for device_name in device_dict:
                    Q_clear += self.power_response(self.controller_bid[device_name]['P_min'], self.controller_bid[device_name]['P_max'], self.controller_bid[device_name]['Q_max'], self.controller_bid[device_name]['Q_min'], P_R)
                
                if Q_clear <= Q_lim - Q_uc:
                    P_clear = P_R
                else:
                    range_min = 0
                    range_step = 0.001
                    range_max = self.aggregator['price_cap']
                    Q_clear_list = [0.0]*int((range_max - range_min) / range_step)
                    Q_error_list = [0.0]*int((range_max - range_min) / range_step)
                    index = 0
                    Q_clear = 0
                    for P_temp in range(range_max, -range_step, range_min - range_step):
                        # Loop through each device with corresponding P_temp
                        for device_name in device_dict:
                            Q_clear += self.power_response(self.controller_bid[device_name]['P_min'], self.controller_bid[device_name]['P_max'], self.controller_bid[device_name]['Q_max'], self.controller_bid[device_name]['Q_min'], P_temp)
                        # Record Q_clear, and Q_error
                        Q_clear_list[index] = Q_clear
                        Q_error_list[index] = Q_clear - (Q_lim - Q_uc)
                        
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
   
            
            