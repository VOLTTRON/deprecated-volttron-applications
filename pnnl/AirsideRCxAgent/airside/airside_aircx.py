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

from datetime import timedelta as td
import sys
import logging
from volttron.platform.agent.math_utils import mean
from volttron.platform.agent.utils import setup_logging
from volttron.platform.agent.driven import Results, AbstractDrivenAgent
from diagnostics.sat_aircx import SupplyTempAIRCx
from diagnostics.stcpr_aircx import DuctStaticAIRCx
from diagnostics.schedule_reset_aircx import SchedResetAIRCx
from diagnostics.common import pre_conditions

FAN_OFF = -99.3
DUCT_STC_RCX = "Duct Static Pressure Set Point Control Loop Dx"
DUCT_STC_RCX1 = "Low Duct Static Pressure Dx"
DUCT_STC_RCX2 = "High Duct Static Pressure Dx"
DX = "/diagnostic message"
SA_TEMP_RCX = "Supply-air Temperature Set Point Control Loop Dx"
SA_TEMP_RCX1 = "Low Supply-air Temperature Dx"
SA_TEMP_RCX2 = "High Supply-air Temperature Dx"
dx_list = [DUCT_STC_RCX, DUCT_STC_RCX1, DUCT_STC_RCX2, SA_TEMP_RCX, SA_TEMP_RCX1, SA_TEMP_RCX2]
__version__ = "1.0.7"

setup_logging()
_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.info, format="%(asctime)s   %(levelname)-8s %(message)s")


def data_builder(value_tuple, point_name):
    value_list = []
    for item in value_tuple:
        value_list.append(item[1])
    return value_list


class Application(AbstractDrivenAgent):
    """
    Air-side HVAC Auto-Retuning Diagnostics
    for AHUs.

    Note:
        All configurable thr have default thr that work well with most equipment/configurations.

    Args:
        no_required_data (int): minimum number of measurements required for
            conclusive analysis.
        warm_up_time (int): Number of minutes after equipment startup prior
            to beginning data collection for analysis.
        duct_stcpr_retuning (float): Amount to increment or decrement the duct
            static pressure set point high/low duct static pressure set point
            problem is detected (assumed to be in inches water column (gauge)).
        max_duct_stcpr_stpt (float): Maximum value for the duct static pressure set
            point when applying auto-correction.
        high_sf_thr (float): Auto-correction for low duct static pressure set point
            will not be effective if the supply fan for the AHU is operating at or near 100%
            of full speed. Auto-correction will not be applied if this condition exists.
        zn_high_damper_thr (float):
        zn_low_damper_thr (float):
        min_duct_stcpr_stpt (float): Minimum value for the duct static pressure set
            point when applying auto-correction.
        low_sf_thr (float): Auto-correction for high duct static pressure set point
            will not be effective if the supply fan for the AHU is operating at or near its
            minimum SupplyFanSpeed. Auto-correction will not be applied if this condition exists.
            If the SupplyFanStatus is not available, the supply fan speed can be used
            to determine if the supply fan is operating. The supply fan will be considered
            ON when operating at speeds above the minimum SupplyFanSpeed.
        setpoint_allowable_deviation (float): Maximum acceptable deviation set point for the supply-air
            temperature and the duct static pressure (averaged over an analysis period, typically one hour).
        stcpr_reset_thr (float):
        percent_reheat_thr (float):
        rht_on_thr (float):
        sat_reset_thr (float):
        sat_high_damper_thr (float):
        percent_damper_thr (float):
        min_sat_stpt (float):
        sat_retuning (float):
        reheat_valve_thr (float):
        max_sat_stpt (float):

    """
    def __init__(
            self, no_required_data=10, warm_up_time=15, data_window=None,
            duct_stcpr_retuning=0.15, max_duct_stcpr_stpt=2.5,
            high_sf_thr=95.0, zn_high_damper_thr=90.0,
            zn_low_damper_thr=15.0, min_duct_stcpr_stpt=0.5,
            hdzn_damper_thr=30.0, low_sf_thr=20.0,
            stpt_deviation_thr=10.0, stcpr_reset_thr=0.25,

            percent_reheat_thr=25.0, rht_on_thr=10.0,
            sat_reset_thr=5.0, sat_high_damper_thr=80.0,
            percent_damper_thr=60.0, min_sat_stpt=50.0,
            sat_retuning=1.0, reheat_valve_thr=50.0,
            max_sat_stpt=75.0,

            unocc_time_thr=40.0, unocc_stp_thr=0.2,
            monday_sch=["5:30", "18:30"], tuesday_sch=["5:30", "18:30"],
            wednesday_sch=["5:30", "18:30"], thursday_sch=["5:30", "18:30"],
            friday_sch=["5:30", "18:30"], saturday_sch=["0:00", "0:00"],
            sunday_sch=["0:00", "0:00"], auto_correct_flag=False,
            analysis_name="", sensitivity="all", **kwargs):

        # Point names (Configurable)
        def get_or_none(name):
            value = kwargs["point_mapping"].get(name, None)
            if value:
                value = value.lower()
            return value

        self.warm_up_start = None
        self.warm_up_flag = True
        self.unit_status = None
        self.data_window = td(minutes=data_window) if data_window is not None else None
        self.analysis = analysis_name

        if sensitivity not in ["all", "high", "normal", "low"]:
            sensitivity = None

        analysis = analysis_name
        self.fan_status_name = get_or_none("fan_status")
        self.fan_sp_name = get_or_none("fan_speedcmd")

        if self.fan_sp_name is None and self.fan_status_name is None:
            raise Exception("SupplyFanStatus or SupplyFanSpeed are required to verify AHU status.")
            sys.exit()

        self.duct_stp_stpt_name = get_or_none("duct_stcpr_stpt")
        self.duct_stp_name = get_or_none("duct_stcpr")
        self.sa_temp_name = get_or_none("sa_temp")
        self.sat_stpt_name = get_or_none("sat_stpt")
        sat_stpt_cname = self.sat_stpt_name
        duct_stp_stpt_cname = self.duct_stp_stpt_name

        # Zone Parameters
        self.zn_damper_name = get_or_none("zn_damper")
        self.zn_reheat_name = get_or_none("zn_reheat")

        no_required_data = int(no_required_data)
        _log.debug("required data: {}".format(no_required_data))
        self.low_sf_thr = float(low_sf_thr)
        self.high_sf_thr = float(high_sf_thr)
        self.warm_up_time = td(minutes=warm_up_time)

        if sensitivity is not None and sensitivity != "custom":
            # SAT AIRCx Thresholds
            stpt_deviation_thr = {
                "low": stpt_deviation_thr*1.5,
                "normal": stpt_deviation_thr,
                "high": stpt_deviation_thr*0.5
            }
            percent_reheat_thr = {
                "low":  percent_reheat_thr,
                "normal": percent_reheat_thr,
                "high":  percent_reheat_thr
            }
            percent_damper_thr = {
                "low": percent_damper_thr + 15.0,
                "normal": percent_damper_thr,
                "high": percent_damper_thr - 15.0
            }
            reheat_valve_thr = {
                "low": reheat_valve_thr*1.5,
                "normal": reheat_valve_thr,
                "high": reheat_valve_thr*0.5
            }
            sat_high_damper_thr = {
                "low": sat_high_damper_thr + 15.0,
                "normal": sat_high_damper_thr,
                "high": sat_high_damper_thr - 15.0
            }
            zn_high_damper_thr = {
                "low":  zn_high_damper_thr + 5.0,
                "normal": zn_high_damper_thr,
                "high": zn_high_damper_thr - 5.0
            }
            zn_low_damper_thr = {
                "low": zn_low_damper_thr + 5.0,
                "normal": zn_low_damper_thr,
                "high": zn_low_damper_thr - 5.0
            }
            hdzn_damper_thr = {
                "low": hdzn_damper_thr - 5.0,
                "normal": hdzn_damper_thr,
                "high": hdzn_damper_thr + 5.0
            }
            unocc_stp_thr = {
                "low": unocc_stp_thr*1.5,
                "normal": unocc_stp_thr,
                "high": unocc_stp_thr*0.625
            }
            unocc_time_thr = {
                "low": unocc_time_thr*1.5,
                "normal": unocc_time_thr,
                "high": unocc_time_thr*0.5
            }
            sat_reset_thr = {
                "low": max(sat_reset_thr - 2.0, 0.5),
                "normal": sat_reset_thr,
                "high": sat_reset_thr + 2.0
            }
            stcpr_reset_thr = {
                "low": stcpr_reset_thr*1.5,
                "normal": stcpr_reset_thr,
                "high": stcpr_reset_thr*0.5
            }

            if sensitivity != "all":
                remove_sensitivities = [item for item in ["high", "normal", "low"] if item != sensitivity]
                if remove_sensitivities:
                    for remove in remove_sensitivities:

                        stpt_deviation_thr.pop(remove)
                        percent_reheat_thr.pop(remove)
                        percent_damper_thr.pop(remove)
                        reheat_valve_thr.pop(remove)
                        sat_high_damper_thr.pop(remove)

                        zn_high_damper_thr.pop(remove)
                        zn_low_damper_thr.pop(remove)

                        stcpr_reset_thr.pop(remove)
                        sat_reset_thr.pop(remove)
                        unocc_time_thr.pop(remove)
                        unocc_stp_thr.pop(remove)
        else:
            stpt_deviation_thr = {"normal": stpt_deviation_thr}
            percent_reheat_thr = {"normal": percent_reheat_thr}
            percent_damper_thr = {"normal": percent_damper_thr}
            reheat_valve_thr = {"normal": reheat_valve_thr}
            sat_high_damper_thr = {"normal": sat_high_damper_thr}

            zn_high_damper_thr = {"normal": zn_high_damper_thr}
            zn_low_damper_thr = {"normal": zn_low_damper_thr}

            stcpr_reset_thr = {"normal": stcpr_reset_thr}
            sat_reset_thr = {"normal": sat_reset_thr}
            unocc_time_thr = {"normal": unocc_time_thr}
            unocc_stp_thr = {"normal": unocc_stp_thr}

        self.stcpr_aircx = DuctStaticAIRCx(no_required_data, data_window, auto_correct_flag,
                                           stpt_deviation_thr, max_duct_stcpr_stpt,
                                           duct_stcpr_retuning, zn_high_damper_thr,
                                           zn_low_damper_thr, hdzn_damper_thr,
                                           min_duct_stcpr_stpt, analysis, duct_stp_stpt_cname)

        self.sat_aircx = SupplyTempAIRCx(no_required_data, data_window, auto_correct_flag,
                                         stpt_deviation_thr, rht_on_thr,
                                         sat_high_damper_thr, percent_damper_thr,
                                         percent_reheat_thr, min_sat_stpt, sat_retuning,
                                         reheat_valve_thr, max_sat_stpt, analysis, sat_stpt_cname)

        self.sched_reset_aircx = SchedResetAIRCx(unocc_time_thr, unocc_stp_thr,
                                                 monday_sch, tuesday_sch, wednesday_sch,
                                                 thursday_sch, friday_sch, saturday_sch,
                                                 sunday_sch, no_required_data, stcpr_reset_thr,
                                                 sat_reset_thr, analysis)

    def run(self, cur_time, points):
        device_dict = {}
        dx_result = Results()

        for key, value in points.items():
            point_device = [_name.lower() for _name in key.split("&")]
            if point_device[0] not in device_dict:
                device_dict[point_device[0]] = [(point_device[1], value)]
            else:
                device_dict[point_device[0]].append((point_device[1], value))

        fan_status_data = []
        stcpr_stpt_data = []
        stc_pr_data = []
        sat_stpt_data = []
        sat_data = []
        zn_rht_data = []
        zn_dmpr_data = []
        fan_sp_data = []

        for key, value in device_dict.items():
            data_name = key
            if value is None:
                continue
            if data_name == self.fan_status_name:
                fan_status_data = data_builder(value, data_name)
            elif data_name == self.duct_stp_stpt_name:
                stcpr_stpt_data = data_builder(value, data_name)
            elif data_name == self.duct_stp_name:
                stc_pr_data = data_builder(value, data_name)
            elif data_name == self.sat_stpt_name:
                sat_stpt_data = data_builder(value, data_name)
            elif data_name == self.sa_temp_name:
                sat_data = data_builder(value, data_name)
            elif data_name == self.zn_reheat_name:
                zn_rht_data = data_builder(value, data_name)
            elif data_name == self.zn_damper_name:
                zn_dmpr_data = data_builder(value, data_name)
            elif data_name == self.fan_sp_name:
                fan_sp_data = data_builder(value, data_name)

        missing_data = []
        if not fan_status_data and not fan_sp_data:
            missing_data.append(self.fan_status_name)
        if not sat_data:
            missing_data.append(self.sa_temp_name)
        if not zn_rht_data:
            missing_data.append(self.zn_reheat_name)
        if not sat_stpt_data:
            dx_result.log("SAT set point data is missing.")
        if not stc_pr_data:
            missing_data.append(self.duct_stp_name)
        if not stcpr_stpt_data:
            dx_result.log("Duct static pressure set point data is missing.")
        if not zn_dmpr_data:
            missing_data.append(self.zn_damper_name)

        if missing_data:
            dx_result.log("Missing data from publish: {}".format(missing_data))
            return dx_result

        current_fan_status, fan_sp = self.check_fan_status(fan_status_data, fan_sp_data, cur_time)

        dx_result = self.sched_reset_aircx.schedule_reset_aircx(cur_time, stc_pr_data,
                                                                stcpr_stpt_data, sat_stpt_data,
                                                                current_fan_status, dx_result)

        dx_result = self.check_elapsed_time(dx_result, cur_time, self.unit_status, FAN_OFF)
        if not current_fan_status:
            dx_result.log("Supply fan is off: {}".format(cur_time))
            self.warm_up_flag = True
            return dx_result

        dx_result.log("Supply fan is on: {}".format(cur_time))

        low_sf_cond = True if fan_sp is not None and fan_sp > self.high_sf_thr else False
        high_sf_cond = True if fan_sp is not None and fan_sp < self.low_sf_thr else False

        if self.warm_up_flag:
            self.warm_up_flag = False
            self.warm_up_start = cur_time
            return dx_result

        if self.warm_up_start is not None and (cur_time - self.warm_up_start) < self.warm_up_time:
            dx_result.log("Unit is in warm-up. Data will not be analyzed.")
            return dx_result

        dx_result = self.stcpr_aircx.stcpr_aircx(cur_time, stcpr_stpt_data,
                                                 stc_pr_data, zn_dmpr_data,
                                                 low_sf_cond, high_sf_cond,
                                                 dx_result)
        dx_result = self.sat_aircx.sat_aircx(cur_time, sat_data, sat_stpt_data,
                                             zn_rht_data, zn_dmpr_data, dx_result)
        return dx_result

    def check_fan_status(self, fan_status_data, fan_sp_data, cur_time):
        """
        :param fan_status_data:
        :param fan_sp_data:
        :param cur_time:
        :return:
        """
        supply_fan_status = int(max(fan_status_data)) if fan_status_data else None

        fan_speed = mean(fan_sp_data) if fan_sp_data else None
        if supply_fan_status is None:
            supply_fan_status = 1 if fan_speed > self.low_sf_thr else 0

        if not supply_fan_status:
            if self.unit_status is None:
                self.unit_status = cur_time
        else:
            self.unit_status = None
        return supply_fan_status, fan_speed

    def check_elapsed_time(self, dx_result, cur_time, condition, message):
        """
        Check for persistence of failure to meet pre-conditions for diagnostics.
        :param dx_result:
        :param cur_time:
        :param condition:
        :param message:
        :return:
        """
        elapsed_time = cur_time - condition if condition is not None else td(minutes=0)
        if self.data_window is not None:
            if elapsed_time >= self.data_window:
                dx_result = pre_conditions(message, dx_list, self.analysis, cur_time, dx_result)
                self.clear_all()
        elif condition is not None and condition.hour != cur_time.hour:
            message_time = condition.replace(minute=0)
            dx_result = pre_conditions(message, dx_list, self.analysis, message_time, dx_result)
            self.clear_all()
        return dx_result

    def clear_all(self):
        self.sat_aircx.reinitialize()
        self.stcpr_aircx.reinitialize()
        self.warm_up_start = None
        self.warm_up_flag = True
        self.unit_status = None
