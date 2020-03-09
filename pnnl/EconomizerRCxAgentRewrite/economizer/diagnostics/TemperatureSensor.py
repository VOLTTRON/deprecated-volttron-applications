"""
Copyright (c) 2017, Battelle Memorial Institute
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
This material was prepared as an account of work sponsored by an agency of the
United States Government. Neither the United States Government nor the United
States Department of Energy, nor Battelle, nor any of their employees, nor any
jurisdiction or organization that has cooperated in the development of these
materials, makes any warranty, express or implied, or assumes any legal
liability or responsibility for the accuracy, completeness, or usefulness or
any information, apparatus, product, software, or process disclosed, or
represents that its use would not infringe privately owned rights.
Reference herein to any specific commercial product, process, or service by
trade name, trademark, manufacturer, or otherwise does not necessarily
constitute or imply its endorsement, recommendation, or favoring by the
United States Government or any agency thereof, or Battelle Memorial Institute.
The views and opinions of authors expressed herein do not necessarily state or
reflect those of the United States Government or any agency thereof.
PACIFIC NORTHWEST NATIONAL LABORATORY
operated by
BATTELLE
for the
UNITED STATES DEPARTMENT OF ENERGY
under Contract DE-AC05-76RL01830
"""
import logging
from datetime import timedelta as td
from volttron.platform.agent.math_utils import mean
from volttron.platform.agent.utils import setup_logging
from .. import constants

setup_logging()
_log = logging.getLogger(__name__)

class TemperatureSensor(object):
    """
    Air-side HVAC temperature sensor diagnostic for AHU/RTU systems.
    TempSensorDx uses metered data from a BAS or controller to
    diagnose if any of the temperature sensors for an AHU/RTU are accurate and
    reliable.
    """

    def __init__(self):
        # Initialize data arrays
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.timestamp = []

        self.temp_sensor_problem = None
        self.max_dx_time = None

        # Application thresholds (Configurable)
        self.data_window = None
        self.no_required_data = None
        self.oat_mat_check = None
        self.temp_diff_thr = None
        self.inconsistent_date = None
        self.sensor_damper_dx = DamperSensorInconsistency()




    def set_class_values(self, data_window, no_required_data, temp_diff_thr, open_damper_time, oat_mat_check, temp_damper_threshold):
        """Set the values needed for doing the diagnostics"""
        self.max_dx_time = td(minutes=60) if td(minutes=60) > data_window else data_window * 3 / 2
        self.data_window = data_window
        self.no_required_data = no_required_data
        self.oat_mat_check = oat_mat_check
        self.temp_diff_thr = {
            'low': temp_diff_thr + 2.0,
            'normal': temp_diff_thr,
            'high': max(1.0, temp_diff_thr - 2.0)
        }
        self.inconsistent_date = {key: 3.2 for key in self.temp_diff_thr}
        self.sensor_damper_dx.set_class_values(data_window, no_required_data, open_damper_time, oat_mat_check, temp_damper_threshold)


    def temperature_algorithm(self, oat, rat, mat, oad, cur_time):
        """"""
        self.oat_values.append(oat)
        self.mat_values.append(mat)
        self.rat_values.append(rat)
        self.timestamp.append(cur_time)
        elapsed_time = self.timestamp[-1] - self.timestamp[0]

        if elapsed_time and self.data_window:
            _log.log("Elapsed time: {} -- required tme: {}".format(elapsed_time, self.data_window))

        if elapsed_time >= self.data_window and len(self.timestamp) >= self.no_required_data:
            if elapsed_time > self.max_dx_time:
                self.clear_data()
            else:
                self.temperature_sensor_dx()
                return self.temp_sensor_problem

        if self.temp_sensor_problem:
            self.sensor_damper_dx.clear_data()
        else:
            self.sensor_damper_dx.damper_algorithm(oat, mat, oad, cur_time)
        return self.temp_sensor_problem

    def temperature_sensor_dx(self):
        """Temperature sensor diagnostic."""
        avg_oa_ma, avg_ra_ma, avg_ma_oa, avg_ma_ra = self.aggregate_data()
        diagnostic_msg = {}
        for sensitivity, threshold in self.temp_diff_thr.items():
            if avg_oa_ma > threshold and avg_ra_ma > threshold:
                msg = ("{}: MAT is less than OAT and RAT - Sensitivity: {}".format(constants.ECON1, sensitivity))
                result = 1.1
            elif avg_ma_oa > threshold and avg_ma_ra > threshold:
                msg = ("{}: MAT is greater than OAT and RAT - Sensitivity: {}".format(constants.ECON1, sensitivity))
                result = 2.1
            else:
                msg = "{}: No problems were detected - Sensitivity: {}".format(constants.ECON1, sensitivity)
                result = 0.0
                self.temp_sensor_problem = False
            _log.log(msg)
            diagnostic_msg.update({sensitivity: result})

        if diagnostic_msg["normal"] > 0.0:
            self.temp_sensor_problem = True

        self.clear_data()

    def aggregate_data(self):
        oa_ma = [(x - y) for x, y in zip(self.oat_values, self.mat_values)]
        ra_ma = [(x - y) for x, y in zip(self.rat_values, self.mat_values)]
        ma_oa = [(y - x) for x, y in zip(self.oat_values, self.mat_values)]
        ma_ra = [(y - x) for x, y in zip(self.rat_values, self.mat_values)]
        avg_oa_ma = mean(oa_ma)
        avg_ra_ma = mean(ra_ma)
        avg_ma_oa = mean(ma_oa)
        avg_ma_ra = mean(ma_ra)
        return avg_oa_ma, avg_ra_ma, avg_ma_oa, avg_ma_ra

    def clear_data(self):
        """
        Reinitialize data arrays.
        :return:
        """
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.timestamp = []
        if self.temp_sensor_problem:
            self.temp_sensor_problem = None


class DamperSensorInconsistency(object):
    """
    Air-side HVAC temperature sensor diagnostic for AHU/RTU systems.
    TempSensorDx uses metered data from a BAS or controller to
    diagnose if any of the temperature sensors for an AHU/RTU are accurate and
    reliable.
    """

    def __init__(self):
        # Initialize data arrays
        self.oat_values = []
        self.mat_values = []
        self.timestamp = []
        self.steady_state = None
        self.econ_time_check = None
        self.data_window = None
        self.no_required_data = None
        self.oad_temperature_threshold = None
        self.oat_mat_check = None

    def set_class_values(self, data_window, no_required_data, open_damper_time, oat_mat_check, temp_damper_threshold):
        """Set the values needed for doing the diagnostics"""
        self.econ_time_check = open_damper_time
        self.data_window = data_window
        self.no_required_data = no_required_data
        self.oad_temperature_threshold = temp_damper_threshold
        self.oat_mat_check = oat_mat_check

    def damper_algorithm(self, oat, mat, oad, cur_time):
        """ """
        msg = ""
        if oad > self.oad_temperature_threshold:
            if self.steady_state is None:
                self.steady_state = cur_time
            elif cur_time - self.steady_state >= self.econ_time_check:
                self.oat_values.append(oat)
                self.mat_values.append(mat)
                self.timestamp.append(cur_time)
        else:
            self.steady_state = None

        elapsed_time = self.timestamp[-1] - self.timestamp[0] if self.timestamp else td(minutes=0)

        if elapsed_time >= self.data_window:
            if len(self.oat_values) > self.no_required_data:
                mat_oat_diff_list = [abs(x - y) for x, y in zip(self.oat_values, self.mat_values)]
                open_damper_check = mean(mat_oat_diff_list)
                diagnostic_msg = {}
                for sensitivity, threshold in self.oat_mat_check.items():
                    if open_damper_check > threshold:
                        msg = "{} - {}: OAT and MAT are inconsistent when OAD is near 100%".format(constants.ECON1, sensitivity)
                        result = 0.1
                    else:
                        msg = "{} - {}: OAT and MAT are consistent when OAD is near 100%".format(constants.ECON1, sensitivity)
                        result = 0.0
                    diagnostic_msg.update({sensitivity: result})

                _log.log(msg)
            self.clear_data()

    def clear_data(self):
        """
        Reinitialize data arrays.
        :return:
        """
        self.oat_values = []
        self.mat_values = []
        self.steady_state = None
        self.timestamp = []


