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
    

class ExcessOA(object):
    ''' Air-side HVAC ventilation diagnostic.

    ExcessOA uses metered data from a controller or
    BAS to diagnose when an AHU/RTU is providing excess outdoor air.
    '''
    def __init__(self, data_window, no_required_data, excess_oaf_threshold,
                 min_damper_sp, excess_damper_threshold, desired_oaf,
                 cfm, eer, analysis):
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.oad_values = []
        self.cool_call_values = []
        self.timestamp = []
        self.fan_speed_values = []
        # Application thresholds (Configurable)
        self.cfm = cfm
        self.eer = eer
        self.max_dx_time = 60
        self.data_window = float(data_window)
        self.no_required_data = no_required_data
        self.excess_oaf_threshold = float(excess_oaf_threshold)
        self.min_damper_sp = float(min_damper_sp)
        self.desired_oaf = float(desired_oaf)
        self.excess_damper_threshold = float(excess_damper_threshold)
        self.analysis = analysis

    def econ_alg4(self, dx_result, oatemp, ratemp, matemp,
                  damper_signal, econ_condition, cur_time,
                  fan_sp, cooling_call):
        '''Check app. pre-quisites and assemble data set for analysis.'''
        if econ_condition:
            dx_result.log('The unit may be economizing, '
                          'data corresponding to {timestamp} '
                          'will not be used for this diagnostic.'
                          .format(timestamp=str(cur_time)), logging.DEBUG)
            dx_status = 3
            return dx_result, dx_status

        self.oad_values.append(damper_signal)
        self.oat_values.append(oatemp)
        self.rat_values.append(ratemp)
        self.mat_values.append(matemp)
        self.timestamp.append(cur_time)
        fan_sp = fan_sp/100.0 if fan_sp is not None else 1.0
        self.fan_speed_values.append(fan_sp)
        elapsed_time = (self.timestamp[-1] - self.timestamp[0]).total_seconds()/60
        elapsed_time = elapsed_time if elapsed_time > 0 else 1.0

        if elapsed_time >= self.data_window and len(self.timestamp) >= self.no_required_data:
            self.table_key = create_table_key(self.analysis, self.timestamp[-1])
            if elapsed_time > self.max_dx_time:
                dx_result.insert_table_row(self.table_key, {ECON4 + DX: 35.2})
                dx_result = self.clear_data(dx_result)
                dx_status = 2
                return dx_result, dx_status

            dx_result = self.excess_oa(dx_result, cur_time)
            dx_status = 1
            return dx_result, dx_status

        dx_status = 0
        return dx_result, dx_status

    def excess_oa(self, dx_result, cur_time):
        '''If the detected problems(s) are
        consistent generate a fault message(s).
        '''
        def energy_impact_calculation(energy_impact):
            energy_impact = 0.0
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
            return energy_impact
            
        avg_step = (self.timestamp[-1] - self.timestamp[0]).total_seconds()/60 if len(self.timestamp) > 1 else 1
        oaf = [(m - r) / (o - r) for o, r, m in zip(self.oat_values, self.rat_values, self.mat_values)]
        avg_oaf = sum(oaf) / len(oaf) * 100
        avg_damper = sum(self.oad_values) / len(self.oad_values)
        desired_oaf = self.desired_oaf / 100.0
        energy_impact = 0.0
        msg = ''
        dx_msg = 30.0

        if avg_oaf < 0 or avg_oaf > 125.0:
            msg = ('Inconclusive result, the OAF calculation led to an '
                   'unexpected value: {oaf}'.format(oaf=avg_oaf))
            # color_code = 'GREY'
            dx_msg = 31.2
            dx_result.log(msg, logging.INFO)
            dx_table = {
                ECON4 + DX: dx_msg,
                ECON4 + EI: 0.0
            }
            dx_result.insert_table_row(self.table_key, dx_table)
            dx_result = self.clear_data(dx_result)
            return dx_result

        if avg_damper - self.min_damper_sp > self.excess_damper_threshold:
            msg = ('The OAD should be at the minimum position for ventilation '
                   'but is significantly higher than this value.')
            # color_code = 'RED'
            dx_msg = 32.1

        if avg_oaf - self.desired_oaf > self.excess_oaf_threshold:
            if dx_msg > 30.0:
                msg += ('The OAD should be at the minimum for ventilation '
                        'but is significantly above that value. Excess outdoor air is '
                        'being provided; This could significantly increase heating and cooling costs')
                dx_msg = 34.1
            else:
                msg = ('Excess outdoor air is being provided, this could '
                       'increase heating and cooling energy consumption.')
                dx_msg = 33.1
            # color_code = 'RED'
        
        elif dx_msg == 30.0:
            msg = ('The calculated outdoor-air fraction is within '
                   'configured limits.')

        if dx_msg > 30:
            energy_impact = energy_impact_calculation(energy_impact)
            energy_impact = round(energy_impact, 2)

        dx_table = {
            ECON4 + DX: dx_msg,
            ECON4 + EI: energy_impact
        }
        dx_result.insert_table_row(self.table_key, dx_table)
        dx_result.log(msg, logging.INFO)
        dx_result = self.clear_data(dx_result)
        return dx_result

    def clear_data(self, dx_result):
        '''reinitialize class insufficient_oa data.'''
        self.oad_values = []
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.fan_speed_values = []
        self.timestamp = []
        return dx_result


class InsufficientOA(object):
    ''' Air-side HVAC ventilation diagnostic.

    insufficient_oa_intake uses metered data from a controller or
    BAS to diagnose when an AHU/RTU is providing inadequate ventilation.
    '''
    def __init__(self, data_window, no_required_data, ventilation_oaf_threshold,
                 min_damper_sp, insufficient_damper_threshold, desired_oaf, analysis):

        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.oad_values = []
        self.cool_call_values = []
        self.timestamp = []
        self.max_dx_time = 60

        '''Application thresholds (Configurable)'''
        self.data_window = float(data_window)
        self.no_required_data = no_required_data
        self.ventilation_oaf_threshold = float(ventilation_oaf_threshold)
        self.insufficient_damper_threshold = float(insufficient_damper_threshold)
        self.min_damper_sp = float(min_damper_sp)
        self.desired_oaf = float(desired_oaf)
        self.analysis = analysis

    def econ_alg5(self, dx_result, oatemp, ratemp, matemp, damper_signal,
                  econ_condition, cur_time, cooling_call):
        '''Check app. pre-quisites and assemble data set for analysis.'''
        self.oat_values.append(oatemp)
        self.rat_values.append(ratemp)
        self.mat_values.append(matemp)
        self.oad_values.append(damper_signal)

        self.timestamp.append(cur_time)
        elapsed_time = (self.timestamp[-1] - self.timestamp[0]).total_seconds()/60
        elapsed_time = elapsed_time if elapsed_time > 0 else 1.0

        if elapsed_time >= self.data_window and len(self.timestamp) >= self.no_required_data:
            self.table_key = create_table_key(self.analysis, self.timestamp[-1])
            if elapsed_time > self.max_dx_time:
                dx_result.insert_table_row(self.table_row, {ECON5 + DX: 44.2})
                dx_result = self.clear_data(dx_result)
                dx_status = 2
                return dx_result, dx_status

            dx_result = self.insufficient_oa(dx_result, cur_time)
            dx_status = 1
            return dx_result, dx_status

        dx_status = 0
        return dx_result, dx_status

    def insufficient_oa(self, dx_result, cur_time):
        '''If the detected problems(s) are
        consistent generate a fault message(s).
        '''
        oaf = [(m - r) / (o - r) for o, r, m in zip(self.oat_values, self.rat_values, self.mat_values)]
        avg_oaf = sum(oaf) / len(oaf) * 100.0
        avg_damper_signal = sum(self.oad_values) / len(self.oad_values)

        if avg_oaf < 0 or avg_oaf > 125.0:
            msg = ('Inconclusive result, the OAF calculation led to an '
                   'unexpected value: {oaf}'.format(oaf=avg_oaf))
            dx_result.log(msg, logging.INFO)
            dx_msg = 41.2
            dx_table = {
                ECON5 + DX: dx_msg,
                ECON5 + EI: 0.0
            }
            dx_result.insert_table_row(self.table_key, dx_table)
            dx_result = self.clear_data(dx_result)
            return dx_result
        msg = ''
        if self.desired_oaf - avg_oaf > self.ventilation_oaf_threshold:
            msg = 'Insufficient outdoor-air is being provided for ventilation.'
            dx_msg = 43.1
            dx_table = {
                ECON5 + DX: dx_msg,
                ECON5 + EI: 0.0
            }
        else:
            msg = ('The calculated outdoor-air fraction was within acceptable limits.')
            dx_msg = 40.0
            dx_table = {
                ECON5 + DX: dx_msg,
                ECON5 + EI: 0.0
            }
        dx_result.insert_table_row(self.table_key, dx_table)
        dx_result.log(msg, logging.INFO)
        dx_result = self.clear_data(dx_result)
        return dx_result

    def clear_data(self, dx_result):
        '''reinitialize class insufficient_oa data.'''
        self.oad_values = []
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.timestamp = []
        return dx_result
