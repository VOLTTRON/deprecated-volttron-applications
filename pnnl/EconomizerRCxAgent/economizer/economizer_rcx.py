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
import datetime
from datetime import timedelta as td
import logging
import sys
from volttron.platform.agent.math_utils import mean
from volttron.platform.agent.driven import Results, AbstractDrivenAgent
from volttron.platform.agent.utils import (setup_logging)
from diagnostics.temperature_sensor_dx import TempSensorDx
from diagnostics.economizer_dx import EconCorrectlyOn, EconCorrectlyOff
from diagnostics.ventilation_dx import ExcessOA, InsufficientOA

__version__ = "1.0.8"

ECON1 = "Temperature Sensor Dx"
ECON2 = "Not Economizing When Unit Should Dx"
ECON3 = "Economizing When Unit Should Not Dx"
ECON4 = "Excess Outdoor-air Intake Dx"
ECON5 = "Insufficient Outdoor-air Intake Dx"
DX = "/diagnostic message"
EI = "/energy impact"
dx_list = [ECON1, ECON2, ECON3, ECON4, ECON5]

FAN_OFF = -99.3
OAF = -89.2
OAT_LIMIT = -79.2
RAT_LIMIT = -69.2
MAT_LIMIT = -59.2
TEMP_SENSOR = -49.2

setup_logging()
_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.debug, format='%(asctime)s   %(levelname)-8s %(message)s',
                    datefmt='%m-%d-%y %H:%M:%S')


def create_table_key(table_name, timestamp):
    return "&".join([table_name, timestamp.isoformat()])


def data_builder(value_tuple, point_name):
    value_list = []
    for item in value_tuple:
        if item[1] is not None:
            value_list.append(item[1])
    return value_list


class Application(AbstractDrivenAgent):
    """
    Application to detect and correct operational problems for AHUs/RTUs.

    This application uses metered data from zones server by an AHU/RTU
    to detect operational problems and where applicable correct these problems
    by modifying set points.  When auto-correction cannot be applied then
    a message detailing the diagnostic results will be made available to
    the building operator.
    """

    def __init__(self, economizer_type="DDB", econ_hl_temp=65.0,
                 device_type="AHU", cooling_enabled_threshold=5.0,
                 temp_band=1.0, data_window=30, no_required_data=15,
                 open_damper_time=5, low_supply_fan_threshold=15.0,
                 mat_low_threshold=50.0, mat_high_threshold=90.0,
                 oat_low_threshold=30.0, oat_high_threshold=110.0,
                 rat_low_threshold=50.0, rat_high_threshold=90.0,
                 temp_difference_threshold=4.0, temp_damper_threshold=90.0,
                 open_damper_threshold=80.0, oaf_temperature_threshold=5.0,
                 minimum_damper_setpoint=20.0, desired_oaf=10.0,
                 rated_cfm=6000.0, eer=10.0, constant_volume=False,
                 sensitivity="default", **kwargs):
        def get_or_none(name):
            value = kwargs["point_mapping"].get(name, None)
            if value:
                value = value.lower()
            return value

        if sensitivity is not None and sensitivity == "custom":
            oaf_temperature_threshold = max(5., min(oaf_temperature_threshold, 15.))
            cooling_enabled_threshold = max(5., min(cooling_enabled_threshold, 50.))
            temp_difference_threshold = max(2., min(temp_difference_threshold, 6.))
            mat_low_threshold = max(40., min(mat_low_threshold, 60.))
            mat_high_threshold = max(80., min(mat_high_threshold, 90.))
            rat_low_threshold = max(40., min(rat_low_threshold, 60.))
            rat_high_threshold = max(80., min(rat_high_threshold, 90.))
            oat_low_threshold = max(20., min(oat_low_threshold, 40.))
            oat_high_threshold = max(90., min(oat_high_threshold, 125.))
            open_damper_threshold = max(60., min(open_damper_threshold, 90.))
            minimum_damper_setpoint = max(0., min(minimum_damper_setpoint, 50.))
            desired_oaf = max(5., min(desired_oaf, 30.))
        else:
            oaf_temperature_threshold = 5.
            cooling_enabled_threshold = 5.
            temp_difference_threshold = 4.
            mat_low_threshold = 50.
            mat_high_threshold = 90.
            rat_low_threshold = 50.
            rat_high_threshold = 90.
            oat_low_threshold = 30.
            oat_high_threshold = 110.
            open_damper_threshold = 80.
            minimum_damper_setpoint = 20.
            desired_oaf = 10.

        econ_hl_temp = max(50., min(econ_hl_temp, 75.))
        temp_band = max(0.5, min(temp_band, 10.))

        self.device_type = device_type.lower()
        if self.device_type not in ("ahu", "rtu"):
            _log.error('device_type must be specified as "AHU" or "RTU" in configuration file.')
            sys.exit()

        if economizer_type.lower() not in ("ddb", "hl"):
            _log.error('economizer_type must be specified as "DDB" or "HL" in configuration file.')
            sys.exit()

        Application.analysis = analysis = kwargs["analysis_name"]

        # data point name mapping
        self.fan_status_name = get_or_none("supply_fan_status")
        self.fan_sp_name = get_or_none("supply_fan_speed")

        if self.fan_sp_name is None and self.fan_status_name is None:
            _log.error("SupplyFanStatus or SupplyFanSpeed are required to verify AHU status.")
            sys.exit()

        self.oat_name = get_or_none("outdoor_air_temperature")
        self.rat_name = get_or_none("return_air_temperature")
        self.mat_name = get_or_none("mixed_air_temperature")
        self.oad_sig_name = get_or_none("outdoor_damper_signal")
        self.cool_call_name = get_or_none("cool_call")

        # Precondition flags
        self.oaf_condition = None
        self.unit_status = None
        self.sensor_limit = None
        self.temp_sensor_problem = None

        # Time based configurations
        self.data_window = data_window = td(minutes=data_window)
        open_damper_time = td(minutes=open_damper_time)
        no_required_data = no_required_data

        # diagnostic threshold parameters
        self.economizer_type = economizer_type.lower()
        self.econ_hl_temp = float(econ_hl_temp) if self.economizer_type == "hl" else None
        self.constant_volume = constant_volume

        self.cooling_enabled_threshold = cooling_enabled_threshold
        self.low_supply_fan_threshold = low_supply_fan_threshold
        self.oaf_temperature_threshold = oaf_temperature_threshold
        self.oat_thresholds = [oat_low_threshold, oat_high_threshold]
        self.rat_thresholds = [rat_low_threshold, rat_high_threshold]
        self.mat_thresholds = [mat_low_threshold, mat_high_threshold]
        self.temp_band = temp_band
        cfm = float(rated_cfm)
        eer = float(eer)

        oat_mat_check = {
            'low': max(temp_difference_threshold * 1.5, 6.0),
            'normal': max(temp_difference_threshold*1.25, 5.0),
            'high': max(temp_difference_threshold, 4.0)
        }
        temp_difference_threshold = {
            'low': temp_difference_threshold + 2.0,
            'normal': temp_difference_threshold,
            'high': max(1.0, temp_difference_threshold - 2.0)
        }
        oaf_economizing_threshold = {
            'low': open_damper_threshold - 30.0,
            'normal': open_damper_threshold - 20.0,
            'high': open_damper_threshold - 10.0
        }
        open_damper_threshold = {
            'low': open_damper_threshold - 10.0,
            'normal': open_damper_threshold,
            'high': open_damper_threshold + 10.0
        }
        excess_damper_threshold = {
            'low': minimum_damper_setpoint*2.0,
            'normal': minimum_damper_setpoint,
            'high':  minimum_damper_setpoint*0.5
        }
        excess_oaf_threshold = {
            'low': minimum_damper_setpoint*2.0 + 10.0,
            'normal': minimum_damper_setpoint + 10.0,
            'high': minimum_damper_setpoint*0.5 + 10.0
        }
        ventilation_oaf_threshold = {
            'low': desired_oaf*0.75,
            'normal': desired_oaf*0.5,
            'high': desired_oaf*0.25
        }
        self.sensitivity = ['low', 'normal', 'high']
        self.econ1 = TempSensorDx(data_window, no_required_data,
                                  temp_difference_threshold, open_damper_time,
                                  oat_mat_check, temp_damper_threshold,
                                  analysis)

        self.econ2 = EconCorrectlyOn(oaf_economizing_threshold,
                                     open_damper_threshold,
                                     minimum_damper_setpoint,
                                     data_window, no_required_data,
                                     cfm, eer, analysis)

        self.econ3 = EconCorrectlyOff(data_window, no_required_data,
                                      minimum_damper_setpoint,
                                      excess_damper_threshold,
                                      desired_oaf, cfm, eer, analysis)

        self.econ4 = ExcessOA(data_window, no_required_data,
                              excess_oaf_threshold,
                              minimum_damper_setpoint,
                              excess_damper_threshold,
                              desired_oaf, cfm, eer, analysis)

        self.econ5 = InsufficientOA(data_window, no_required_data,
                                    ventilation_oaf_threshold, desired_oaf,
                                    analysis)

    def run(self, cur_time, points):
        """
        Main run method that is called by the DrivenBaseClass.

        run receives a dictionary of data 'points' and an associated timestamp
        for the data cur_time'.  run then passes the appropriate data to
        each diagnostic when calling
        the diagnostic message.
        :param cur_time:
        :param points:
        :return:
        """
        device_dict = {}
        dx_result = Results()

        for point, value in points.items():
            point_device = [name.lower() for name in point.split("&")]
            if point_device[0] not in device_dict:
                device_dict[point_device[0]] = [(point_device[1], value)]
            else:
                device_dict[point_device[0]].append((point_device[1], value))

        damper_data = []
        oat_data = []
        mat_data = []
        rat_data = []
        cooling_data = []
        fan_sp_data = []
        fan_status_data = []
        missing_data = []

        for key, value in device_dict.items():
            data_name = key
            if value is None:
                continue
            if data_name == self.fan_status_name:
                fan_status_data = data_builder(value, data_name)
            elif data_name == self.oad_sig_name:
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
        if not fan_status_data or not fan_sp_data:
            missing_data.append(self.fan_status_name)
        if missing_data:
            dx_result.log("Missing data from publish: {}".format(missing_data))
            return dx_result

        current_fan_status, fan_sp = self.check_fan_status(fan_status_data, fan_sp_data, cur_time)
        dx_result = self.check_elapsed_time(dx_result, cur_time, self.unit_status, FAN_OFF)
        
        if not current_fan_status:
            dx_result.log("Supply fan is off: {}".format(cur_time))
            return dx_result
        else:
            dx_result.log("Supply fan is on: {}".format(cur_time))

        if fan_sp is None and self.constant_volume:
            fan_sp = 100.0

        oat = mean(oat_data)
        rat = mean(rat_data)
        mat = mean(mat_data)
        oad = mean(damper_data)

        self.check_temperature_condition(oat, rat, cur_time)
        dx_result = self.check_elapsed_time(dx_result, cur_time, self.oaf_condition, OAF)

        if self.oaf_condition:
            dx_result.log("OAT and RAT readings are too close.")
            return dx_result

        limit_condition = self.sensor_limit_check(oat, rat, mat, cur_time)
        dx_result = self.check_elapsed_time(dx_result, cur_time, self.sensor_limit, limit_condition[1])
        if limit_condition[0]:
            dx_result.log("Temperature sensor is outside of bounds: {} -- {}".format(limit_condition, self.sensor_limit))
            return dx_result

        dx_result, self.temp_sensor_problem = self.econ1.econ_alg1(dx_result, oat, rat, mat, oad, cur_time)
        econ_condition, cool_call = self.determine_cooling_condition(cooling_data, oat, rat)
        _log.debug("Cool call: {} - Economizer status: {}".format(cool_call, econ_condition))

        if self.temp_sensor_problem is not None and not self.temp_sensor_problem:
            dx_result = self.econ2.econ_alg2(dx_result, cool_call, oat, rat, mat,
                                             oad, econ_condition, cur_time, fan_sp)

            dx_result = self.econ3.econ_alg3(dx_result, oat, rat, mat, oad,
                                             econ_condition, cur_time, fan_sp)

            dx_result = self.econ4.econ_alg4(dx_result, oat, rat, mat, oad,
                                             econ_condition, cur_time, fan_sp)

            dx_result = self.econ5.econ_alg5(dx_result, oat, rat, mat, cur_time)
        elif self.temp_sensor_problem:
            self.pre_conditions(dx_list[1:], TEMP_SENSOR, cur_time, dx_result)
            self.econ2.clear_data()
            self.econ2.clear_data()
            self.econ3.clear_data()
            self.econ4.clear_data()
            self.econ5.clear_data()
        return dx_result

    def clear_all(self):
        """
        Reinitialize all data arrays for diagnostics.
        :return:
        """
        self.econ1.clear_data()
        self.econ2.clear_data()
        self.econ2.clear_data()
        self.econ3.clear_data()
        self.econ4.clear_data()
        self.econ5.clear_data()
        self.temp_sensor_problem = None
        self.unit_status = None
        self.oaf_condition = None
        self.sensor_limit = None
        return

    def determine_cooling_condition(self, cooling_data, oat, rat):
        """
        Determine if the unit is in a cooling mode and if conditions
        are favorable for economizing.
        :param cooling_data:
        :param oat:
        :param rat:
        :return:
        """
        if self.device_type == "ahu":
            clg_vlv_pos = mean(cooling_data)
            cool_call = True if clg_vlv_pos > self.cooling_enabled_threshold else False
        elif self.device_type == "rtu":
            cool_call = int(max(cooling_data))

        if self.economizer_type == "ddb":
            econ_condition = (rat - oat) > self.temp_band
        else:
            econ_condition = (self.econ_hl_temp - oat) > self.temp_band

        return econ_condition, cool_call

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
            supply_fan_status = 1 if fan_speed > self.low_supply_fan_threshold else 0

        if not supply_fan_status:
            if self.unit_status is None:
                self.unit_status = cur_time
        else:
            self.unit_status = None
        return supply_fan_status, fan_speed

    def check_temperature_condition(self, oat, rat, cur_time):
        """
        Ensure the OAT and RAT have minimum difference to allow
        for a conclusive diagnostic.
        :param oat:
        :param rat:
        :param cur_time:
        :return:
        """
        if abs(oat - rat) < self.oaf_temperature_threshold:
            if self.oaf_condition is None:
                self.oaf_condition = cur_time
        else:
            self.oaf_condition = None
        return

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
        if elapsed_time >= self.data_window:
            dx_result = self.pre_conditions(dx_list, message, cur_time, dx_result)
            self.clear_all()
        return dx_result

    def pre_conditions(self, diagnostics, message, cur_time, dx_result):
        """
        Publish pre-conditions not met message.
        :param diagnostics:
        :param message:
        :param cur_time:
        :param dx_result:
        :return:
        """
        dx_msg = {}
        for sensitivity in self.sensitivity:
            dx_msg[sensitivity] = message

        for diagnostic in diagnostics:
            dx_table = {diagnostic + DX: dx_msg}
            table_key = create_table_key(self.analysis, cur_time)
            dx_result.insert_table_row(table_key, dx_table)
        return dx_result

    def sensor_limit_check(self, oat, rat, mat, cur_time):
        """
        Check temperature limits on sensors.
        :param oat:
        :param rat:
        :param mat:
        :param cur_time:
        :return:
        """
        sensor_limit = (False, None)
        if oat < self.oat_thresholds[0] or oat > self.oat_thresholds[1]:
            sensor_limit = (True, OAT_LIMIT)
        elif mat < self.mat_thresholds[0] or mat > self.mat_thresholds[1]:
            sensor_limit = (True, MAT_LIMIT)
        elif rat < self.rat_thresholds[0] or rat > self.rat_thresholds[1]:
            sensor_limit = (True, RAT_LIMIT)

        if sensor_limit[0]:
            if self.sensor_limit is None:
                self.sensor_limit = cur_time
        else:
            self.sensor_limit = None
        return sensor_limit
