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

ECON4 = "Excess Outdoor-air Intake Dx"
ECON5 = "Insufficient Outdoor-air Intake Dx"
DX = "/diagnostic message"
EI = "/energy impact"


def create_table_key(table_name, timestamp):
    return "&".join([table_name, timestamp.isoformat()])


class ExcessOA(object):
    """
    Air-side HVAC ventilation diagnostic.

    ExcessOA uses metered data from a controller or
    BAS to diagnose when an AHU/RTU is providing excess outdoor air.
    """
    def __init__(self, data_window, no_required_data, excess_oaf_threshold,
                 min_damper_sp, excess_damper_threshold, desired_oaf,
                 cfm, eer, analysis):
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.oad_values = []
        self.timestamp = []
        self.fan_spd_values = []
        self.economizing = None

        # Application thresholds (Configurable)
        self.cfm = cfm
        self.eer = eer
        self.max_dx_time = td(minutes=60) if td(minutes=60) > data_window else data_window * 3 / 2
        self.data_window = data_window
        self.no_required_data = no_required_data
        self.excess_oaf_threshold = excess_oaf_threshold
        self.min_damper_sp = min_damper_sp
        self.desired_oaf = desired_oaf
        self.excess_damper_threshold = excess_damper_threshold
        self.economizing_dict = {key: 36.0 for key in self.excess_damper_threshold}
        self.invalid_oaf_dict = {key: 31.2 for key in self.excess_damper_threshold}
        self.inconsistent_date = {key: 35.2 for key in self.excess_damper_threshold}
        self.analysis = analysis

    def econ_alg4(self, dx_result, oat, rat, mat, oad, econ_condition, cur_time, fan_sp):
        """
        Check app. prerequisites and assemble data set for analysis.
        :param dx_result:
        :param oat:
        :param rat:
        :param mat:
        :param oad:
        :param econ_condition:
        :param cur_time:
        :param fan_sp:
        :return:
        """
        dx_result, economizing = self.economizer_conditions(dx_result, econ_condition, cur_time)
        if economizing:
            return dx_result

        self.oad_values.append(oad)
        self.oat_values.append(oat)
        self.rat_values.append(rat)
        self.mat_values.append(mat)
        self.timestamp.append(cur_time)

        fan_sp = fan_sp / 100.0 if fan_sp is not None else 1.0
        self.fan_spd_values.append(fan_sp)
        elapsed_time = self.timestamp[-1] - self.timestamp[0]

        if elapsed_time >= self.data_window and len(self.timestamp) >= self.no_required_data:
            table_key = create_table_key(self.analysis, self.timestamp[-1])
            if elapsed_time > self.max_dx_time:
                dx_result.insert_table_row(table_key, {ECON4 + DX: self.inconsistent_date})
                self.clear_data()
                return dx_result
            dx_result = self.excess_oa(dx_result, table_key)
            return dx_result
        return dx_result

    def excess_oa(self, dx_result, table_key):
        """
        If the detected problems(s) are consistent generate a fault message(s).
        :param dx_result:
        :param table_key:
        :return:
        """
        oaf = [(m - r) / (o - r) for o, r, m in zip(self.oat_values, self.rat_values, self.mat_values)]
        avg_oaf = mean(oaf) * 100.0
        avg_damper = mean(self.oad_values)
        desired_oaf = self.desired_oaf / 100.0
        diagnostic_msg = {}
        energy_impact = {}

        if avg_oaf < 0 or avg_oaf > 125.0:
            msg = ("{}: Inconclusive result, unexpected OAF value: {}".format(ECON4, avg_oaf))
            # color_code = "GREY"
            dx_table = {ECON4 + DX: self.invalid_oaf_dict}
            dx_result.log(msg)
            dx_result.insert_table_row(table_key, dx_table)
            self.clear_data()
            return dx_result

        avg_oaf = max(0.0, min(100.0, avg_oaf))
        thresholds = zip(self.excess_damper_threshold.items(), self.excess_oaf_threshold.items())
        for (key, damper_thr), (key2, oaf_thr) in thresholds:
            energy = None
            if avg_damper > damper_thr:
                msg = "{}: The OAD should be at the minimum but is significantly higher.".format(ECON4)
                # color_code = "RED"
                result = 32.1
                if avg_oaf - self.desired_oaf > oaf_thr:
                    msg = ("{}: The OAD should be at the minimum for ventilation "
                           "but is significantly above that value. Excess outdoor air is "
                           "being provided; This could significantly increase "
                           "heating and cooling costs".format(ECON4))
                    energy = self.energy_impact_calculation(desired_oaf)
                    result = 34.1
            elif avg_oaf - self.desired_oaf > oaf_thr:
                msg = ("{}: Excess outdoor air is being provided, this could "
                       "increase heating and cooling energy consumption.".format(ECON4))
                # color_code = "RED"
                energy = self.energy_impact_calculation(desired_oaf)
                result = 33.1
            else:
                # color_code = "GREEN"
                msg = ("{}: The calculated OAF is within configured limits.".format(ECON4))
                result = 30.0
                energy = 0.0

            dx_result.log(msg)
            if energy is not None:
                energy_impact.update({key: energy})
            diagnostic_msg.update({key: result})

        dx_table = {
            ECON4 + DX: diagnostic_msg,
            ECON4 + EI: energy_impact
        }

        dx_result.insert_table_row(table_key, dx_table)
        self.clear_data()
        return dx_result

    def clear_data(self):
        """
        Reinitialize class insufficient_oa data.
        :return:
        """
        self.oad_values = []
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.fan_spd_values = []
        self.timestamp = []
        self.economizing = None
        return

    def energy_impact_calculation(self, desired_oaf):
        ei = 0.0
        energy_calc = [
            (1.08 * spd * self.cfm * (m - (o * desired_oaf + (r * (1.0 - desired_oaf))))) / (1000.0 * self.eer)
            for m, o, r, spd in zip(self.mat_values, self.oat_values, self.rat_values, self.fan_spd_values)
            if (m - (o * desired_oaf + (r * (1.0 - desired_oaf)))) > 0
        ]
        if energy_calc:
            avg_step = (self.timestamp[-1] - self.timestamp[0]).total_seconds() / 60 if len(self.timestamp) > 1 else 1
            dx_time = (len(energy_calc) - 1) * avg_step if len(energy_calc) > 1 else 1.0
            ei = (sum(energy_calc) * 60.0) / (len(energy_calc) * dx_time)
            ei = round(ei, 2)
        return ei

    def economizer_conditions(self, dx_result, econ_condition, cur_time):
        if econ_condition:
            dx_result.log("{}: economizing at {} .".format(ECON4, cur_time))
            if self.economizing is None:
                self.economizing = cur_time
            if cur_time - self.economizing >= self.data_window:
                dx_result.log("{}: economizing for data set, reinitialize.".format(ECON4))
                dx_table = {ECON4 + DX: self.economizing_dict}
                table_key = create_table_key(self.analysis, cur_time)
                dx_result.insert_table_row(table_key, dx_table)
                self.clear_data()
            return dx_result, True
        else:
            self.economizing = None
        return dx_result, False


class InsufficientOA(object):
    """
    Air-side HVAC ventilation diagnostic.

    insufficient_oa_intake uses metered data from a controller or
    BAS to diagnose when an AHU/RTU is providing inadequate ventilation.
    """

    def __init__(self, data_window, no_required_data, ventilation_oaf_threshold, desired_oaf, analysis):

        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.timestamp = []
        self.max_dx_time = td(minutes=60) if td(minutes=60) > data_window else data_window * 3 / 2

        # Application thresholds (Configurable)
        self.data_window = data_window
        self.no_required_data = no_required_data
        self.ventilation_oaf_threshold = ventilation_oaf_threshold
        self.desired_oaf = desired_oaf
        self.analysis = analysis
        self.invalid_oaf_dict = {key: 41.2 for key in self.ventilation_oaf_threshold}
        self.inconsistent_date = {key: 44.2 for key in self.ventilation_oaf_threshold}

    def econ_alg5(self, dx_result, oatemp, ratemp, matemp, cur_time):
        """
        Check app. pre-quisites and assemble data set for analysis.
        :param dx_result:
        :param oatemp:
        :param ratemp:
        :param matemp:
        :param damper_signal:
        :param econ_condition:
        :param cur_time:
        :param cooling_call:
        :return:
        """
        self.oat_values.append(oatemp)
        self.rat_values.append(ratemp)
        self.mat_values.append(matemp)
        self.timestamp.append(cur_time)

        elapsed_time = self.timestamp[-1] - self.timestamp[0]

        if elapsed_time >= self.data_window and len(self.timestamp) >= self.no_required_data:
            table_key = create_table_key(self.analysis, self.timestamp[-1])
            if elapsed_time > self.max_dx_time:
                dx_result.insert_table_row(table_key, {ECON5 + DX: self.inconsistent_date})
                self.clear_data()
                return dx_result
            dx_result = self.insufficient_oa(dx_result, table_key)
            return dx_result
        return dx_result

    def insufficient_oa(self, dx_result, table_key):
        """
        If the detected problems(s) are
        consistent generate a fault message(s).
        :param dx_result:
        :param cur_time:
        :param table_key:
        :return:
        """
        oaf = [(m - r) / (o - r) for o, r, m in zip(self.oat_values, self.rat_values, self.mat_values)]
        avg_oaf = mean(oaf) * 100.0
        diagnostic_msg = {}

        if avg_oaf < 0 or avg_oaf > 125.0:
            msg = ("{}: Inconclusive result, the OAF calculation led to an "
                   "unexpected value: {}".format(ECON5, avg_oaf))
            # color_code = "GREY"
            dx_table = {ECON5 + DX: self.invalid_oaf_dict}
            dx_result.log(msg)
            dx_result.insert_table_row(table_key, dx_table)
            self.clear_data()
            return dx_result

        avg_oaf = max(0.0, min(100.0, avg_oaf))
        for sensitivity, threshold in self.ventilation_oaf_threshold.items():
            if self.desired_oaf - avg_oaf > threshold:
                msg = "{}: Insufficient OA is being provided for ventilation - sensitivity: {}".format(ECON5, sensitivity)
                result = 43.1
            else:
                msg = "{}: The calculated OAF was within acceptable limits - sensitivity: {}".format(ECON5, sensitivity)
                result = 40.0
            dx_result.log(msg)
            diagnostic_msg.update({sensitivity: result})

        dx_table = {ECON5 + DX: diagnostic_msg}
        dx_result.insert_table_row(table_key, dx_table)
        self.clear_data()
        return dx_result

    def clear_data(self):
        """
        Reinitialize class insufficient_oa data.
        :return:
        """
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.timestamp = []
        return
