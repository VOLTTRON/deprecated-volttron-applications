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

__version__ = '3.1'

ECON1 = 'Temperature Sensor Dx'

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

class TempSensorDx(object):
    '''Air-side HVAC temperature sensor diagnostic for AHU/RTU systems.

    TempSensorDx uses metered data from a BAS or controller to
    diagnose if any of the temperature sensors for an AHU/RTU are accurate and
    reliable.
    '''
    def __init__(self, data_window, no_required_data, temp_diff_thr, open_damper_time,
                 oat_mat_check, temp_damper_threshold, analysis):
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.timestamp = []
        self.open_oat = []
        self.open_mat = []
        self.econ_check = False
        self.steady_state_st = None
        self.open_damper_time = int(open_damper_time)
        self.econ_time_check = td(minutes=self.open_damper_time - 1)
        TempSensorDx.temp_sensor_problem = None
        self.analysis = analysis
        self.max_dx_time = 60

        '''Application thresholds (Configurable)'''
        self.data_window = float(data_window)
        self.no_required_data = no_required_data
        self.temp_diff_thr = float(temp_diff_thr)
        self.oat_mat_check = float(oat_mat_check)
        self.temp_damper_threshold = float(temp_damper_threshold)

    def econ_alg1(self, dx_result, oatemp, ratemp, matemp, damper_signal, cur_time):
        '''Check app. pre-quisites and assemble data set for analysis.'''
        if damper_signal > self.temp_damper_threshold:
            if not self.econ_check:
                self.econ_check = True
                self.steady_state_st = cur_time
            if cur_time - self.steady_state_st >= self.econ_time_check:
                self.open_oat.append(oatemp)
                self.open_mat.append(matemp)
        else:
            self.econ_check = False

        self.oat_values.append(oatemp)
        self.mat_values.append(matemp)
        self.rat_values.append(ratemp)

        if self.timestamp and ((cur_time - self.timestamp[-1]).total_seconds()/60) > 5.0:
            self.econ_check = False
        self.timestamp.append(cur_time)
        elapsed_time = (self.timestamp[-1] - self.timestamp[0]).total_seconds()/60
        elapsed_time = elapsed_time if elapsed_time > 0 else 1.0

        if (elapsed_time >= self.data_window and len(self.timestamp) >= self.no_required_data):
            self.table_key = (self.analysis, self.timestamp[-1])

            if elapsed_time > self.max_dx_time:
                dx_result.insert_table_row(self.table_key, {ECON1 + DX: 3.2})
                dx_result = self.clear_data(dx_result)
                dx_status = 3
                return dx_result, dx_status
            
            dx_result = self.temperature_sensor_dx(dx_result, cur_time)
            dx_status = 1
            return dx_result, dx_status

        dx_status = 0
        return dx_result, dx_status

    def temperature_sensor_dx(self, dx_result, cur_time):
        '''
        If the detected problems(s) are
        consistent then generate a fault message(s).
        '''
        oa_ma = [(x - y) for x, y in zip(self.oat_values, self.mat_values)]
        ra_ma = [(x - y) for x, y in zip(self.rat_values, self.mat_values)]
        ma_oa = [(y - x) for x, y in zip(self.oat_values, self.mat_values)]
        ma_ra = [(y - x)for x, y in zip(self.rat_values, self.mat_values)]
        avg_oa_ma = sum(oa_ma) / len(oa_ma)
        avg_ra_ma = sum(ra_ma) / len(ra_ma)
        avg_ma_oa = sum(ma_oa) / len(ma_oa)
        avg_ma_ra = sum(ma_ra) / len(ma_ra)
        dx_table = {}

        if len(self.open_oat) > self.no_required_data:
            mat_oat_diff_list = [abs(x - y) for x, y in zip(self.open_oat, self.open_mat)]
            open_damper_check = sum(mat_oat_diff_list) / len(mat_oat_diff_list)

            if open_damper_check > self.oat_mat_check:
                TempSensorDx.temp_sensor_problem = True
                msg = ('The OAT and MAT sensor readings are not consistent '
                       'when the outdoor-air damper is fully open.')
                dx_msg = 0.1
                dx_table = {
                    ECON1 + DX: dx_msg,
                    ECON1 + EI: 0.0
                }
                dx_result.log(msg, logging.INFO)
                dx_result.insert_table_row(self.table_key, dx_table)
            self.open_oat = []
            self.open_mat = []

        if avg_oa_ma > self.temp_diff_thr and avg_ra_ma > self.temp_diff_thr:
            msg = ('Temperature sensor problem detected. Mixed-air '
                   'temperature is less than outdoor-air and return-air'
                   'temperatures.')
            dx_msg = 1.1
            dx_table = {
                ECON1 + DX: dx_msg,
                ECON1 + EI: 0.0
            }
            TempSensorDx.temp_sensor_problem = True

        elif avg_ma_oa > self.temp_diff_thr and avg_ma_ra > self.temp_diff_thr:
            msg = ('Temperature sensor problem detected Mixed-air '
                   'temperature is greater than outdoor-air and return-air '
                   'temperatures.')
            dx_msg = 2.1
            dx_table = {
                ECON1 + DX: dx_msg,
                ECON1 + EI: 0.0
            }
            TempSensorDx.temp_sensor_problem = True

        elif TempSensorDx.temp_sensor_problem is None or not TempSensorDx.temp_sensor_problem:
            msg = 'No problems were detected for the temperature sensor diagnostic.'
            dx_msg = 0.0
            dx_table = {
                ECON1 + DX: dx_msg,
                ECON1 + EI: 0.0
            }
            TempSensorDx.temp_sensor_problem = False

        else:
            msg = 'Temperature sensor diagnostic was inconclusive.'
            # color_code = 'GREY'
            dx_msg = 3.2
            dx_table = {
                ECON1 + DX: dx_msg,
                ECON1 + EI: 0.0
            }
            TempSensorDx.temp_sensor_problem = False

        dx_result.insert_table_row(self.table_key, dx_table)
        dx_result.log(msg, logging.INFO)
        dx_result = self.clear_data(dx_result)
        return dx_result

    def clear_data(self, dx_result):
        '''
        reinitialize class insufficient_oa data
        '''
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.timestamp = []
        return dx_result
