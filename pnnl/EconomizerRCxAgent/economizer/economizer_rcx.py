'''
Copyright (c) 2014, Battelle Memorial Institute
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The views and conclusions contained in the software and documentation are those
of the authors and should not be interpreted as representing official policies,
either expressed or implied, of the FreeBSD Project.

This material was prepared as an account of work sponsored by an
agency of the United States Government.  Neither the United States
Government nor the United States Department of Energy, nor Battelle,
nor any of their employees, nor any jurisdiction or organization
that has cooperated in the development of these materials, makes
any warranty, express or implied, or assumes any legal liability
or responsibility for the accuracy, completeness, or usefulness or
any information, apparatus, product, software, or process disclosed,
or represents that its use would not infringe privately owned rights.

Reference herein to any specific commercial product, process, or
service by trade name, trademark, manufacturer, or otherwise does
not necessarily constitute or imply its endorsement, recommendation,
or favoring by the United States Government or any agency thereof,
or Battelle Memorial Institute. The views and opinions of authors
expressed herein do not necessarily state or reflect those of the
United States Government or any agency thereof.

PACIFIC NORTHWEST NATIONAL LABORATORY
operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
under Contract DE-AC05-76RL01830
'''

import datetime
from datetime import timedelta as td
import logging
import sys
from volttron.platform.agent.math_utils import mean
from volttron.platform.agent.driven import Results, AbstractDrivenAgent
from diagnostics.temperature_sensor_dx import TempSensorDx
from diagnostics.economizer_dx import EconCorrectlyOn, EconCorrectlyOff
from diagnostics.ventilation_dx import ExcessOA, InsufficientOA

__version__ = '3.2'

ECON1 = 'Temperature Sensor Dx'
ECON2 = 'Not Economizing When Unit Should Dx'
ECON3 = 'Economizing When Unit Should Not Dx'
ECON4 = 'Excess Outdoor-air Intake Dx'
ECON5 = 'Insufficient Outdoor-air Intake Dx'
DX = '/diagnostic message'
EI = '/energy impact'
DATA = '/data/'

RAT = 'ReturnAirTemperature'
MAT = 'MixedAirTemperature'
OAT = 'OutsideAirTemperature'
OAD = 'OutsideDamperSignal'
CC = 'CoolCall'
FS = 'SupplyFanSpeed'
EC = 'EconomizerCondition'
ST = 'State'

def create_table_key(table_name, timestamp):
    return '&'.join([table_name, timestamp.strftime('%m-%d-%y %H:%M')])


class Application(AbstractDrivenAgent):
    '''Application to detect and correct operational problems for AHUs/RTUs.

    This application uses metered data from zones server by an AHU/RTU
    to detect operational problems and where applicable correct these problems
    by modifying set points.  When auto-correction cannot be applied then
    a message detailing the diagnostic results will be made available to
    the building operator.
    '''
    # Diagnostic Point Names (Must match OpenEIS data-type names)

    def __init__(self, economizer_type='DDB', econ_hl_temp=65.0, device_type='AHU',
                 temp_deadband=1.0, data_window=30, no_required_data=20, open_damper_time=5,
                 low_supply_fan_threshold=20.0, mat_low_threshold=50.0, mat_high_threshold=90.0,
                 oat_low_threshold=30.0, oat_high_threshold=100.0, rat_low_threshold=50.0,
                 rat_high_threshold=90.0, temp_difference_threshold=4.0, oat_mat_check=5.0,
                 open_damper_threshold=90.0, oaf_economizing_threshold=25.0, oaf_temperature_threshold=4.0,
                 cooling_enabled_threshold=5.0, minimum_damper_setpoint=15.0, excess_damper_threshold=20.0,
                 excess_oaf_threshold=20.0, desired_oaf=10.0, ventilation_oaf_threshold=5.0,
                 insufficient_damper_threshold=15.0, temp_damper_threshold=90.0, rated_cfm=6000.0, eer=10.0,
                 **kwargs):

        def get_or_none(name):
            value = kwargs.get(name, None)
            if value:
                value = value.lower()
            return value

        # Application thresholds (Configurable)
        analysis = kwargs['analysis_name']
        self.fan_status_name = get_or_none('fan_status')
        self.fansp_name = get_or_none('fan_speedcmd')

        if self.fansp_name  is None and self.fan_status_name is None:
            raise Exception('SupplyFanStatus or SupplyFanSpeed are required to verify AHU status.')

        self.oat_name = get_or_none('oa_temp')
        self.rat_name = get_or_none('ra_temp')
        self.mat_name = get_or_none('ma_temp')
        self.oad_sig_name = get_or_none('damper_signal')
        self.cool_call_name = get_or_none('cool_call')
        self.fan_sp_name = get_or_none('fan_speedcmd')
        data_window = int(data_window)
        open_damper_time = int(open_damper_time)
        self.device_type = device_type.lower()
        self.economizer_type = economizer_type.lower()

        if self.economizer_type == 'hl':
            self.econ_hl_temp = float(econ_hl_temp)

        self.oaf_temperature_threshold = float(oaf_temperature_threshold)
        self.data_window = float(data_window)
        no_required_data = int(no_required_data)
        self.mat_low_threshold = float(mat_low_threshold)
        self.mat_high_threshold = float(mat_high_threshold)
        self.oat_low_threshold = float(oat_low_threshold)
        self.oat_high_threshold = float(oat_high_threshold)
        self.rat_low_threshold = float(rat_low_threshold)
        self.rat_high_threshold = float(rat_high_threshold)
        self.temp_deadband = float(temp_deadband)
        self.low_supply_fan_threshold = float(low_supply_fan_threshold)
        self.cooling_enabled_threshold = float(cooling_enabled_threshold)
        cfm = float(rated_cfm)
        eer = float(eer)

        self.econ1 = TempSensorDx(data_window, no_required_data,
                                  temp_difference_threshold, open_damper_time,
                                  oat_mat_check, temp_damper_threshold, analysis)

        self.econ2 = EconCorrectlyOn(oaf_economizing_threshold, open_damper_threshold,
                                     data_window, no_required_data, cfm, eer, analysis)

        self.econ3 = EconCorrectlyOff(data_window, no_required_data, minimum_damper_setpoint,
                                      excess_damper_threshold, cooling_enabled_threshold,
                                      desired_oaf, cfm, eer, analysis)

        self.econ4 = ExcessOA(data_window, no_required_data, excess_oaf_threshold,
                              minimum_damper_setpoint, excess_damper_threshold, 
                              desired_oaf, cfm, eer, analysis)

        self.econ5 = InsufficientOA(data_window, no_required_data, ventilation_oaf_threshold,
                                    minimum_damper_setpoint, insufficient_damper_threshold,
                                    desired_oaf, analysis)

    def run(self, cur_time, points):
        '''Main run method that is called by the DrivenBaseClass.

        run receives a dictionary of data 'points' and an associated timestamp
        for the data cur_time'.  run then passes the appropriate data to
        each diagnostic when calling
        the diagnostic message.
        '''
        validate_topic = create_table_key('validate', cur_time)
        validate_data = {ECON1: 1, ECON2: 1, ECON3: 1, ECON4: 1, ECON5: 1}
        try:
            device_dict = {}
            dx_result = Results()
            fan_status_data = []
            supply_fan_off = False

            for key, value in points.items():
                point_device = [_name.lower() for _name in key.split('&')]
                if point_device[0] not in device_dict:
                    device_dict[point_device[0]] = [(point_device[1], value)]
                else:
                    device_dict[point_device[0]].append((point_device[1], value))

            if self.fan_status_name in device_dict:
                fan_status = device_dict[self.fan_status_name]
                fan_status = [point[1] for point in fan_status]
                fan_status = [status for status in fan_status if status is not None]
                if fan_status_data:
                    fan_status_data.append(min(fan_status))
                    if not int(fan_status_data[0]):
                        supply_fan_off = True
                        self.warm_up_flag = True

            if self.fansp_name in device_dict:
                fan_speed = device_dict[self.fansp_name]
                fan_speedcmd = mean([point[1] for point in fan_speed])
                if self.fan_status_name is None:
                    if not int(fan_speedcmd):
                        supply_fan_off = True
                        self.warm_up_flag = True
                    fan_status_data.append(bool(int(fan_speedcmd)))
                if fan_speedcmd < self.low_supply_fan_threshold:
                    _log.debug('Fan is operating below minimum configured speed.')
                    return dx_result
                    
            if supply_fan_off:
                dx_result.log('Supply fan is off. Data will not be used for retuning diagnostics.')

            damper_data = []
            oat_data = []
            mat_data = []
            rat_data = []
            cooling_data = []
            fan_sp_data = []

            def data_builder(value_tuple, point_name):
                value_list = []
                for item in value_tuple:
                    value_list.append(item[1])
                return value_list

            for key, value in device_dict.items():
                data_name = key
                if value is None:
                    continue
                if data_name == self.oad_sig_name:
                    damper_data = data_builder(value, data_name)
                elif data_name == self.oat_name:
                    oat_data = data_builder(value, data_name)
                elif data_name == self.mat_name:
                    mat_data = data_builder(value, data_name)
                elif data_name == self.rat_name:
                    rat_data = data_builder(value, data_name)
                elif data_name == self.cool_call_name:
                    cooling_data = data_builder(value, data_name)
                elif data_name == self.fan_sp_name:
                    fan_sp_data = data_builder(value, data_name)

            missing_data = []
            if not oat_data:
                missing_data.append(self.oat_name)
            if not rat_data:
                missing_data.append(self.rat_name)
            if not mat_data:
                missing_data.append(self.mat_name)
            if not damper_data:
                missing_data.append(self.oad_sig_name)
            if not cooling_data:
                missing_data.append(self.cool_call_name)
            if missing_data:
                dx_result.log('Missing required data: {}'.format(missing_data))
                return dx_result
            oatemp = (sum(oat_data) / len(oat_data))
            ratemp = (sum(rat_data) / len(rat_data))
            matemp = (sum(mat_data) / len(mat_data))
            damper_signal = (sum(damper_data) / len(damper_data))
       
            limit_check = False
            if oatemp < self.oat_low_threshold or oatemp > self.oat_high_threshold:
                dx_result.log('Outside-air temperature is outside high/low '
                             'operating limits, check the functionality of '
                             'the temperature sensor.')
                limit_check = True
            if ratemp < self.rat_low_threshold or ratemp > self.rat_high_threshold:
                dx_result.log('Return-air temperature is outside high/low '
                             'operating limits, check the functionality of '
                             'the temperature sensor.')
                limit_check = True
            if matemp < self.mat_low_threshold or matemp > self.mat_high_threshold:
                dx_result.log('Mixed-air temperature is outside high/low '
                              'operating limits, check the functionality '
                              'of the temperature sensor.')
                limit_check = True
            if limit_check:
                return dx_result

            if abs(oatemp - ratemp) < self.oaf_temperature_threshold:
                dx_result.log('OAT and RAT are too close, economizer diagnostic '
                              'will not use data corresponding to: {timestamp} '
                              .format(timestamp=str(cur_time)), logging.DEBUG)
                return dx_result

            device_type_error = False

            if self.device_type == 'ahu':
                cooling_valve = sum(cooling_data) / len(cooling_data)
                if cooling_valve > self.cooling_enabled_threshold:
                    cooling_call = True
                else: 
                    cooling_call = False

            elif self.device_type == 'rtu': 
                cooling_call = int(max(cooling_data))

            else:
                device_type_error = True
                dx_result.log('device_type must be specified as "AHU" or "RTU" '
                              'Check Configuration input.', logging.INFO)

            if device_type_error:
                return dx_result

            if self.economizer_type == 'ddb':
                econ_condition = oatemp < (ratemp - self.temp_deadband)
            else:
                econ_condition = oatemp < (self.econ_hl_temp - self.temp_deadband)

            dx_result, dx_status = self.econ1.econ_alg1(dx_result, oatemp, ratemp, matemp, damper_signal, cur_time)
            validate_data.update({ECON1: dx_status})
     
            if TempSensorDx.temp_sensor_problem is not None and TempSensorDx.temp_sensor_problem is False:
                dx_result, dx_status = self.econ2.econ_alg2(dx_result, cooling_call, oatemp, ratemp, matemp, damper_signal,
                                                 econ_condition, cur_time, fan_speedcmd)
                validate_data.update({ECON2: dx_status})
                
                dx_result, dx_status = self.econ3.econ_alg3(dx_result, oatemp, ratemp, matemp, damper_signal, econ_condition,
                                                 cur_time, fan_speedcmd, cooling_call)
                validate_data.update({ECON3: dx_status})

                dx_result, dx_status = self.econ4.econ_alg4(dx_result, oatemp, ratemp, matemp, damper_signal, econ_condition,
                                                 cur_time, fan_speedcmd, cooling_call)
                validate_data.update({ECON4: dx_status})

                dx_result, dx_status = self.econ5.econ_alg5(dx_result, oatemp, ratemp, matemp, damper_signal, econ_condition,
                                                 cur_time, cooling_call)
                validate_data.update({ECON5: dx_status})
            else:
                dx_result = self.econ2.clear_data(dx_result)
                dx_result = self.econ3.clear_data(dx_result)
                dx_result = self.econ4.clear_data(dx_result)
                dx_result = self.econ5.clear_data(dx_result)
                TempSensorDx.temp_sensor_problem = None
            return dx_result
        finally:
            dx_result.insert_table_row(validate_topic, validate_data)
