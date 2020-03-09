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

class EconCorrectlyOn(object):
    """Air-side HVAC economizer diagnostic for AHU/RTU systems.
    EconCorrectlyOn uses metered data from a BAS or controller to diagnose
    if an AHU/RTU is economizing when it should.
    """

    def __init__(self):
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

        self.open_damper_threshold = None
        self.oaf_economizing_threshold = None
        self.minimum_damper_setpoint = None
        self.data_window = None
        self.no_required_data = None
        self.cfm = None
        self.eer = None

        self.max_dx_time = None
        self.not_economizing_dict = None
        self.not_cooling_dict = None
        self.inconsistent_date = None

        # Application result messages
        self.alg_result_messages = [
            "Conditions are favorable for economizing but the the OAD is frequently below 100%.",
            "No problems detected.",
            "Conditions are favorable for economizing and OAD is 100% but the OAF is too low."
        ]

    def set_class_values(self, open_damper_threshold, minimum_damper_setpoint, data_window, no_required_data,cfm, eer):
        """Set the values needed for doing the diagnostics"""
        self.open_damper_threshold = open_damper_threshold
        self.oaf_economizing_threshold = {
            'low': open_damper_threshold - 30.0,
            'normal': open_damper_threshold - 20.0,
            'high': open_damper_threshold - 10.0
        }
        self.minimum_damper_setpoint = minimum_damper_setpoint
        self.data_window = data_window
        self.no_required_data = no_required_data
        self.cfm = cfm
        self.eer = eer
        self.max_dx_time = td(minutes=60) if td(minutes=60) > data_window else data_window * 3 / 2
        self.not_economizing_dict = {key: 15.0 for key in self.oaf_economizing_threshold}
        self.not_cooling_dict = {key: 14.0 for key in self.oaf_economizing_threshold}
        self.inconsistent_date = {key: 13.2 for key in self.oaf_economizing_threshold}


    def economizer_on_algorithm(self, cooling_call, oat, rat, mat, oad, econ_condition, cur_time, fan_sp):
        """"""

        economizing = self.economizer_conditions(cooling_call, econ_condition, cur_time)
        if not economizing:
            return

        self.oat_values.append(oat)
        self.mat_values.append(mat)
        self.rat_values.append(rat)
        self.oad_values.append(oad)
        self.timestamp.append(cur_time)

        fan_sp = fan_sp / 100.0 if fan_sp is not None else 1.0
        self.fan_spd_values.append(fan_sp)
        elapsed_time = self.timestamp[-1] - self.timestamp[0]

        if elapsed_time >= self.data_window and len(self.timestamp) >= self.no_required_data:
            if elapsed_time > self.max_dx_time:
                self.clear_data()
                return
            self.not_economizing_when_needed()


    def economizer_conditions(self, cooling_call, econ_condition, cur_time):
        """"""
        if not cooling_call:
            _log.log("{}: not cooling at {}".format(constants.ECON2, cur_time))
            if self.not_cooling is None:
                self.not_cooling = cur_time
            if cur_time - self.not_cooling >= self.data_window:
                _log.log("{}: no cooling during data set - reinitialize.".format(constants.ECON2))
                self.clear_data()
            return False
        else:
            self.not_cooling = None

        if not econ_condition:
            _log.log("{}: not economizing at {}.".format(constants.ECON2, cur_time))
            if self.not_economizing is None:
                self.not_economizing = cur_time
            if cur_time - self.not_economizing >= self.data_window:
                _log.log("{}: no economizing during data set - reinitialize.".format(constants.ECON2))
                self.clear_data()
            return False
        else:
            self.not_economizing = None
        return True

    def not_economizing_when_needed(self):
        """If the detected problems(s) are consistent then generate a fault message(s)."""
        oaf = [(m - r) / (o - r) for o, r, m in zip(self.oat_values, self.rat_values, self.mat_values)]
        avg_oaf = max(0.0, min(100.0, mean(oaf) * 100.0))
        avg_damper_signal = mean(self.oad_values)
        diagnostic_msg = {}
        energy_impact = {}
        thresholds = zip(self.open_damper_threshold.items(), self.oaf_economizing_threshold.items())
        for (key, damper_thr), (key2, oaf_thr) in thresholds:
            if avg_damper_signal < damper_thr:
                msg = "{} - {}: {}".format(constants.ECON2, key, self.alg_result_messages[0])
                result = 11.1
                energy = self.energy_impact_calculation()
            else:
                if avg_oaf < oaf_thr:
                    msg = "{} - {}: {} - OAF={}".format(constants.ECON2, key, self.alg_result_messages[2], avg_oaf)
                    result = 12.1
                    energy = self.energy_impact_calculation()
                else:
                    msg = "{} - {}: {}".format(constants.ECON2, key, self.alg_result_messages[1])
                    result = 10.0
                    energy = 0.0
            _log.log(msg)
            diagnostic_msg.update({key: result})
            energy_impact.update({key: energy})

        self.clear_data()

    def energy_impact_calculation(self):
        """"""
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

