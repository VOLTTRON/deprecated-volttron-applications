'''
Copyright (c) 2016, Battelle Memorial Institute
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
r favoring by the United States Government or any agency thereof,
or Battelle Memorial Institute. The views and opinions of authors
expressed herein do not necessarily state or reflect those of the
United States Government or any agency thereof.

PACIFIC NORTHWEST NATIONAL LABORATORY
operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
under Contract DE-AC05-76RL01830
'''
import logging
from datetime import timedelta as td

ECON2 = 'Not Economizing When Unit Should Dx'
ECON3 = 'Economizing When Unit Should Not Dx'
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
    

class EconCorrectlyOn(object):
    '''Air-side HVAC economizer diagnostic for AHU/RTU systems.

    EconCorrectlyOn uses metered data from a BAS or controller to diagnose
    if an AHU/RTU is economizing when it should.
    '''
    def __init__(self, oaf_economizing_threshold, open_damper_threshold,
                 data_window, no_required_data, cfm, eer, analysis):
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.fan_speed_values = []
        self.oad_values = []
        self.timestamp = []
        self.output_no_run = []
        self.open_damper_threshold = float(open_damper_threshold)
        self.oaf_economizing_threshold = float(oaf_economizing_threshold)
        self.data_window = float(data_window)
        self.no_required_data = no_required_data
        self.cfm = cfm
        self.eer = eer
        self.table_key = None
        self.analysis = analysis
        self.max_dx_time = 60

        '''Application result messages'''
        self.alg_result_messages = [
            'Conditions are favorable for economizing but the '
            'damper is frequently below 100% open.',
            'No problems detected.',
            'Conditions are favorable for economizing and the '
            'damper is 100% open but the OAF indicates the unit '
            'is not brining in near 100% OA.'
        ]

    def econ_alg2(self, dx_result, cooling_call, oatemp, ratemp,
                  matemp, damper_signal, econ_condition, cur_time,
                  fan_sp):
        '''Check app. pre-quisites and assemble data set for analysis.'''
        if not cooling_call:
            dx_result.log('The unit is not cooling, data corresponding to '
                          '{timestamp} will not be used for {name} diagnostic.'
                          .format(timestamp=str(cur_time), name=ECON2),
                          logging.DEBUG)
            self.output_no_run.append(cur_time)

            if (self.output_no_run[-1] - self.output_no_run[0]) >= td(minutes=(self.data_window)):
                dx_result.log('{}: unit is not cooling or economizing, keep collecting data.'.format(ECON2), logging.DEBUG)
                self.output_no_run = []

            dx_status = 3
            return dx_result, dx_status

        if not econ_condition:
            dx_result.log('{}: Conditions are not favorable for economizing, '
                          'data corresponding to {} will not be used.'
                          .format(ECON2,str(cur_time)), logging.DEBUG)
            self.output_no_run.append(cur_time)
            if (self.output_no_run[-1] - self.output_no_run[0]) >= td(minutes=(self.data_window)):
                dx_result.log('{name}: the unit is not cooling or economizing, keep collecting data.'.format(name=ECON2), logging.DEBUG)
                self.output_no_run = []
            dx_status = 3
            return dx_result, dx_status

        self.oat_values.append(oatemp)
        self.mat_values.append(matemp)
        self.rat_values.append(ratemp)
        self.timestamp.append(cur_time)
        self.oad_values.append(damper_signal)

        fan_sp = fan_sp/100.0 if fan_sp is not None else 1.0
        self.fan_speed_values.append(fan_sp)
        self.timestamp.append(cur_time)
        elapsed_time = (self.timestamp[-1] - self.timestamp[0]).total_seconds()/60
        elapsed_time = elapsed_time if elapsed_time > 0 else 1.0

        if (elapsed_time >= self.data_window and len(self.timestamp) >= self.no_required_data):
            self.table_key = create_table_key(self.analysis, self.timestamp[-1])

            if elapsed_time > self.max_dx_time:
                dx_result.insert_table_row(self.table_key, {ECON2 + DX: 13.2})
                dx_result = self.clear_data(dx_result)
                dx_status = 2
                return dx_result, dx_status

            dx_result = self.not_economizing_when_needed(dx_result, cur_time)
            dx_status = 1
            return dx_result, dx_status

        dx_status = 0
        return dx_result, dx_status

    def not_economizing_when_needed(self, dx_result, cur_time):
        '''If the detected problems(s) are consistent then generate a fault
        message(s).
        '''
        def energy_impact_calculation(energy_impact):
            energy_calc = \
                [1.08 * spd * self.cfm * (ma - oa) / (1000.0 * self.eer)
                 for ma, oa, spd in zip(self.mat_values, self.oat_values,
                                        self.fan_speed_values)
                 if (ma - oa) > 0 and color_code == 'RED']
            if energy_calc:
                dx_time = (len(energy_calc) - 1) * avg_step if len(energy_calc) > 1 else 1.0
                energy_impact = (sum(energy_calc) * 60.0) / (len(energy_calc) * dx_time)
                energy_impact = round(energy_impact, 2)
            return energy_impact

        oaf = [(m - r) / (o - r) for o, r, m in zip(self.oat_values, self.rat_values, self.mat_values)]
        avg_step = (self.timestamp[-1] - self.timestamp[0]).total_seconds()/60 if len(self.timestamp) > 1 else 1
        avg_oaf = sum(oaf) / len(oaf) * 100.0
        avg_damper_signal = sum(self.oad_values)/len(self.oad_values)
        energy_impact = 0.0

        if avg_damper_signal < self.open_damper_threshold:
            msg = (self.alg_result_messages[0])
            color_code = 'RED'
            dx_msg = 11.1
            energy_impact = energy_impact_calculation(energy_impact)
        else:
            if (100.0 - avg_oaf) <= self.oaf_economizing_threshold:
                msg = (self.alg_result_messages[1])
                color_code = 'GREEN'
                dx_msg = 10.0
            else:
                msg = (self.alg_result_messages[2])
                color_code = 'RED'
                dx_msg = 12.1
                energy_impact = energy_impact_calculation(energy_impact)

        dx_table = {
            ECON2 + DX: dx_msg,
            ECON2 + EI: energy_impact
        }
        dx_result.insert_table_row(self.table_key, dx_table)
        dx_result.log(msg, logging.INFO)
        dx_result = self.clear_data(dx_result)
        return dx_result

    def clear_data(self, dx_result):
        '''
        reinitialize class insufficient_oa data.
        '''
        self.oad_values = []
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.fan_speed_values = []
        self.timestamp = []
        return dx_result


class EconCorrectlyOff(object):
    '''Air-side HVAC economizer diagnostic for AHU/RTU systems.

    EconCorrectlyOff uses metered data from a BAS or controller to diagnose
    if an AHU/RTU is economizing when it should not.
    '''

    def __init__(self, data_window, no_required_data, min_damper_sp,
                 excess_damper_threshold, cooling_enabled_threshold,
                 desired_oaf, cfm, eer, analysis):
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.oad_values = []
        self.cool_call_values = []
        self.cfm = cfm
        self.eer = eer
        self.fan_speed_values = []
        self.timestamp = []

        # Application result messages
        self.alg_result_messages = \
            ['The outdoor-air damper should be at the minimum position but is '
             'significantly above that value.',
             'No problems detected.',
             'The diagnostic led to inconclusive results, could not '
             'verify the status of the economizer.']
        self.max_dx_time = 60
        self.data_window = float(data_window)
        self.no_required_data = no_required_data
        self.min_damper_sp = float(min_damper_sp)
        self.excess_damper_threshold = float(excess_damper_threshold)
        self.cooling_enabled_threshold = float(cooling_enabled_threshold)
        self.desired_oaf = float(desired_oaf)
        self.analysis = analysis

    def econ_alg3(self, dx_result, oatemp, ratemp, matemp,
                  damper_signal, econ_condition, cur_time,
                  fan_sp, cooling_call):
        '''Check app. pre-quisites and assemble data set for analysis.'''
        if econ_condition:
            dx_result.log(self.alg_result_messages[2]
                          .join(['Data for to {ts} will not be used for this '
                                 'diagnostic.'.format(ts=str(cur_time))]),
                          logging.DEBUG)
            dx_status = 3
            return dx_result, dx_status

        self.oad_values.append(damper_signal)
        self.oat_values.append(oatemp)
        self.mat_values.append(matemp)
        self.rat_values.append(ratemp)
        self.timestamp.append(cur_time)
        fan_sp = fan_sp/100.0 if fan_sp is not None else 1.0
        self.fan_speed_values.append(fan_sp)
        elapsed_time = (self.timestamp[-1] - self.timestamp[0]).total_seconds()/60
        elapsed_time = elapsed_time if elapsed_time > 0 else 1.0

        if elapsed_time >= self.data_window and len(self.timestamp) >= self.no_required_data:
            self.table_key = create_table_key(self.analysis, self.timestamp[-1])

            if elapsed_time > self.max_dx_time:
                dx_result.insert_table_row(self.table_key, {ECON3 + DX: 23.2})
                dx_result = self.clear_data(dx_result)
                dx_status = 2
                return dx_result, dx_status
            
            dx_result = self.economizing_when_not_needed(dx_result, cur_time)
            dx_status = 1
            return dx_result, dx_status

        dx_status = 0
        return dx_result, dx_status

    def economizing_when_not_needed(self, dx_result, cur_time):
        '''If the detected problems(s)
        are consistent then generate a
        fault message(s).
        '''
        def energy_impact_calculation(energy_impact):
            energy_calc = [
                (1.08 * spd * self.cfm * (ma - (oa * desired_oaf +
                                                (ra * (1.0 - desired_oaf))))) /
                (1000.0 * self.eer)
                for ma, oa, ra, spd in zip(self.mat_values,
                                           self.oat_values,
                                           self.rat_values,
                                           self.fan_speed_values)
                if (ma - (oa * desired_oaf + (ra * (1.0 - desired_oaf)))) > 0]
            if energy_calc:
                dx_time = (len(energy_calc) - 1) * avg_step if len(energy_calc) > 1 else 1.0
                energy_impact = (sum(energy_calc) * 60.0) / (len(energy_calc) * dx_time)
                energy_impact = round(energy_impact, 2)
            return energy_impact
            
        avg_step = (self.timestamp[-1] - self.timestamp[0]).total_seconds()/60 if len(self.timestamp) > 1 else 1
        desired_oaf = self.desired_oaf / 100.0
        energy_impact = 0.0
        avg_damper = sum(self.oad_values) / len(self.oad_values)

        if (avg_damper - self.min_damper_sp) > self.excess_damper_threshold:
            msg = self.alg_result_messages[0]
            color_code = 'RED'
            dx_msg = 21.1
            energy_impact = energy_impact_calculation(energy_impact)
        else:
            msg = 'No problems detected for economizing when not needed diagnostic.'
            color_code = 'GREEN'
            dx_msg = 20.0

        dx_table = {
            ECON3 + DX: dx_msg,
            ECON3 + EI: energy_impact
        }
        dx_result.insert_table_row(self.table_key, dx_table)
        dx_result.log(msg, logging.INFO)
        dx_result = self.clear_data(dx_result)
        return dx_result

    def clear_data(self, dx_result):
        '''
        reinitialize class insufficient_oa data
        '''
        self.oad_values = []
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.fan_speed_values = []
        self.timestamp = []
        return dx_result
