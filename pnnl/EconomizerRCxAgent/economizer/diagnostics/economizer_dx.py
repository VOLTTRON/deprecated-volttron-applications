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

ECON2 = "Not Economizing When Unit Should Dx"
ECON3 = "Economizing When Unit Should Not Dx"
DX = "/diagnostic message"
EI = "/energy impact"


def create_table_key(table_name, timestamp):
    return "&".join([table_name, timestamp.isoformat()])


class EconCorrectlyOn(object):
    """Air-side HVAC economizer diagnostic for AHU/RTU systems.

    EconCorrectlyOn uses metered data from a BAS or controller to diagnose
    if an AHU/RTU is economizing when it should.
    """

    def __init__(self, oaf_economizing_threshold, open_damper_threshold,
                 minimum_damper_setpoint, data_window, no_required_data,
                 cfm, eer, analysis):
        # Initialize data arrays
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.fan_spd_values = []
        self.oad_values = []
        self.timestamp = []

        # Initialize not_cooling and not_economizing flags
        self.not_cooling = None
        self.not_economizing = None


        self.open_damper_threshold = open_damper_threshold
        self.oaf_economizing_threshold = oaf_economizing_threshold
        self.minimum_damper_setpoint = minimum_damper_setpoint
        self.data_window = data_window
        self.no_required_data = no_required_data
        self.cfm = cfm
        self.eer = eer

        self.analysis = analysis
        self.max_dx_time = td(minutes=60) if td(minutes=60) > data_window else data_window * 3 / 2
        self.not_economizing_dict = {key: 15.0 for key in self.oaf_economizing_threshold}
        self.not_cooling_dict = {key: 14.0 for key in self.oaf_economizing_threshold}
        self.inconsistent_date = {key: 13.2 for key in self.oaf_economizing_threshold}

        # Application result messages
        self.alg_result_messages = [
            "Conditions are favorable for economizing but the the OAD is frequently below 100%.",
            "No problems detected.",
            "Conditions are favorable for economizing and OAD is 100% but the OAF is too low."
        ]

    def econ_alg2(self, dx_result, cooling_call, oat, rat, mat, oad, econ_condition, cur_time, fan_sp):
        """
        Check app. pre-quisites and assemble data set for analysis.
        :param dx_result:
        :param cooling_call:
        :param oat:
        :param rat:
        :param mat:
        :param oad:
        :param econ_condition:
        :param cur_time:
        :param fan_sp:
        :return:
        """
        dx_result, economizing = self.economizer_conditions(dx_result, cooling_call, econ_condition, cur_time)
        if not economizing:
            return dx_result

        self.oat_values.append(oat)
        self.mat_values.append(mat)
        self.rat_values.append(rat)
        self.oad_values.append(oad)
        self.timestamp.append(cur_time)

        fan_sp = fan_sp / 100.0 if fan_sp is not None else 1.0
        self.fan_spd_values.append(fan_sp)

        elapsed_time = self.timestamp[-1] - self.timestamp[0]

        if elapsed_time >= self.data_window and len(self.timestamp) >= self.no_required_data:
            table_key = create_table_key(self.analysis, self.timestamp[-1])

            if elapsed_time > self.max_dx_time:
                dx_result.insert_table_row(table_key, {ECON2 + DX: self.inconsistent_date})
                self.clear_data()
                return dx_result
            dx_result = self.not_economizing_when_needed(dx_result, table_key)
            return dx_result

        return dx_result

    def not_economizing_when_needed(self, dx_result, table_key):
        """
        If the detected problems(s) are consistent then generate a fault
        message(s).
        :param dx_result:
        :param table_key:
        :return:
        """
        oaf = [(m - r) / (o - r) for o, r, m in zip(self.oat_values, self.rat_values, self.mat_values)]
        avg_oaf = max(0.0, min(100.0, mean(oaf)*100.0))
        avg_damper_signal = mean(self.oad_values)
        diagnostic_msg = {}
        energy_impact = {}
        thresholds = zip(self.open_damper_threshold.items(), self.oaf_economizing_threshold.items())
        for (key, damper_thr), (key2, oaf_thr) in thresholds:
            if avg_damper_signal < damper_thr:
                msg = "{} - {}: {}".format(ECON2, key, self.alg_result_messages[0])
                # color_code = "RED"
                result = 11.1
                energy = self.energy_impact_calculation()
            else:
                if avg_oaf < oaf_thr:
                    msg = "{} - {}: {} - OAF={}".format(ECON2, key, self.alg_result_messages[2], avg_oaf)
                    # color_code = "RED"
                    result = 12.1
                    energy = self.energy_impact_calculation()
                else:
                    msg = "{} - {}: {}".format(ECON2, key, self.alg_result_messages[1])
                    # color_code = "GREEN"
                    result = 10.0
                    energy = 0.0
            dx_result.log(msg)
            diagnostic_msg.update({key: result})
            energy_impact.update({key: energy})

        dx_table = {
            ECON2 + DX: diagnostic_msg,
            ECON2 + EI: energy_impact
        }
        dx_result.insert_table_row(table_key, dx_table)
        self.clear_data()
        return dx_result

    def economizer_conditions(self, dx_result, cooling_call, econ_condition, cur_time):
        """
        Check if unit is in a cooling mode.
        :param dx_result:
        :param cooling_call:
        :param econ_condition:
        :param cur_time:
        :return:
        """
        if not cooling_call:
            dx_result.log("{}: not cooling at {}".format(ECON2, cur_time))
            if self.not_cooling is None:
                self.not_cooling = cur_time
            if cur_time - self.not_cooling >= self.data_window:
                dx_result.log("{}: no cooling during data set - reinitialize.".format(ECON2))
                dx_table = {ECON2 + DX: self.not_cooling_dict}
                table_key = create_table_key(self.analysis, cur_time)
                dx_result.insert_table_row(table_key, dx_table)
                self.clear_data()
            return dx_result, False
        else:
            self.not_cooling = None

        if not econ_condition:
            dx_result.log("{}: not economizing at {}.".format(ECON2, cur_time))
            if self.not_economizing is None:
                self.not_economizing = cur_time
            if cur_time - self.not_economizing >= self.data_window:
                dx_result.log("{}: no economizing during data set - reinitialize.".format(ECON2))
                dx_table = {ECON2 + DX: self.not_economizing_dict}
                table_key = create_table_key(self.analysis, cur_time)
                dx_result.insert_table_row(table_key, dx_table)
                self.clear_data()
            return dx_result, False
        else:
            self.not_economizing = None
        return dx_result, True

    def energy_impact_calculation(self):
        ei = 0.0
        energy_calc = [1.08 * s * self.cfm * (m - o) / (1000.0 * self.eer)
                       for m, o, s in zip(self.mat_values, self.oat_values, self.fan_spd_values)
                       if (m - o) > 0]
        if energy_calc:
            avg_step = (self.timestamp[-1] - self.timestamp[0]).total_seconds() / 60 if len(self.timestamp) > 1 else 1
            dx_time = (len(energy_calc) - 1) * avg_step if len(energy_calc) > 1 else 1.0
            ei = (sum(energy_calc) * 60.0) / (len(energy_calc) * dx_time)
            ei = round(ei, 2)
        return ei

    def clear_data(self):
        """
        Reinitialize data arrays.
        :return:
        """
        self.oad_values = []
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.fan_spd_values = []
        self.timestamp = []
        self.not_economizing = None
        self.not_cooling = None


class EconCorrectlyOff(object):
    """
    Air-side HVAC economizer diagnostic for AHU/RTU systems.

    EconCorrectlyOff uses metered data from a BAS or controller to diagnose
    if an AHU/RTU is economizing when it should not.
    """
    def __init__(self, data_window, no_required_data, min_damper_sp,
                 excess_damper_threshold, desired_oaf, cfm, eer, analysis):
        # Initialize data arrays.
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.oad_values = []
        self.fan_spd_values = []
        self.timestamp = []

        self.economizing = None

        # Application result messages
        self.alg_result_messages = \
            ["The OAD should be at the minimum position but is significantly above this value.",
             "No problems detected.",
             "Inconclusive results, could not verify the status of the economizer."]
        # Map configurable parameters
        self.max_dx_time = td(minutes=60) if td(minutes=60) > data_window else data_window * 3/2
        self.data_window = data_window
        self.no_required_data = no_required_data
        self.min_damper_sp = min_damper_sp
        self.excess_damper_threshold = excess_damper_threshold
        self.economizing_dict = {key: 25.0 for key in self.excess_damper_threshold}
        self.inconsistent_date = {key: 23.2 for key in self.excess_damper_threshold}
        self.desired_oaf = desired_oaf
        self.analysis = analysis
        self.cfm = cfm
        self.eer = eer

    def econ_alg3(self, dx_result, oat, rat, mat, oad, econ_condition, cur_time, fan_sp):
        """
        Check app. pre-quisites and assemble data set for analysis.
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
        self.mat_values.append(mat)
        self.rat_values.append(rat)
        self.timestamp.append(cur_time)

        fan_sp = fan_sp / 100.0 if fan_sp is not None else 1.0
        self.fan_spd_values.append(fan_sp)

        elapsed_time = self.timestamp[-1] - self.timestamp[0]

        if elapsed_time >= self.data_window and len(self.timestamp) >= self.no_required_data:
            table_key = create_table_key(self.analysis, self.timestamp[-1])

            if elapsed_time > self.max_dx_time:
                dx_result.insert_table_row(table_key, {ECON3 + DX: self.inconsistent_date})
                self.clear_data()
                return dx_result

            dx_result = self.economizing_when_not_needed(dx_result, table_key)
            return dx_result
        return dx_result

    def economizing_when_not_needed(self, dx_result, table_key):
        """
        If the detected problems(s) are consistent then generate a
        fault message(s).
        :param dx_result:
        :param table_key:
        :return:
        """
        desired_oaf = self.desired_oaf / 100.0
        avg_damper = mean(self.oad_values)
        diagnostic_msg = {}
        energy_impact = {}
        for sensitivity, threshold in self.excess_damper_threshold.items():
            if avg_damper > threshold:
                msg = "{} - {}: {}".format(ECON3, sensitivity, self.alg_result_messages[0])
                # color_code = "RED"
                result = 21.1
                energy = self.energy_impact_calculation(desired_oaf)
            else:
                msg = "{} - {}: {}".format(ECON3, sensitivity, self.alg_result_messages[1])
                # color_code = "GREEN"
                result = 20.0
                energy = 0.0
            dx_result.log(msg)
            diagnostic_msg.update({sensitivity: result})
            energy_impact.update({sensitivity: energy})

        dx_table = {
            ECON3 + DX: diagnostic_msg,
            ECON3 + EI: energy_impact
        }
        dx_result.insert_table_row(table_key, dx_table)
        self.clear_data()
        return dx_result

    def clear_data(self):
        """
        Reinitialize data arrays.
        :return:
        """
        self.oad_values = []
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.fan_spd_values = []
        self.timestamp = []
        self.economizing = None

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
            dx_result.log("{}: economizing, for data {} --{}.".format(ECON3, econ_condition, cur_time))
            if self.economizing is None:
                self.economizing = cur_time
            if cur_time - self.economizing >= self.data_window:
                dx_result.log("{}: economizing - reinitialize!".format(ECON3))
                dx_table = {ECON3 + DX: self.economizing_dict}
                table_key = create_table_key(self.analysis, cur_time)
                dx_result.insert_table_row(table_key, dx_table)
                self.clear_data()
            return dx_result, True
        else:
            self.economizing = None
        return dx_result, False
