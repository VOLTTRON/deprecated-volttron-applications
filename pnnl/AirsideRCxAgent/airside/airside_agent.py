import sys
import logging
from datetime import timedelta as td
from dateutil import parser
from volttron.platform.agent import utils
from volttron.platform.messaging import topics
from volttron.platform.agent.math_utils import mean
from volttron.platform.agent.utils import setup_logging
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.jsonrpc import RemoteError
from .diagnostics import common
from .diagnostics.sat_aircx import SupplyTempAIRCx
from .diagnostics.schedule_reset_aircx import SchedResetAIRCx
from .diagnostics.stcpr_aircx import DuctStaticAIRCx



__version__ = "1.1.0"

setup_logging()
_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.debug, format='%(asctime)s   %(levelname)-8s %(message)s',
                    datefmt='%m-%d-%y %H:%M:%S')


class AirsideAgent(Agent):
    """
     Agent that starts all of the Airside diagnostics
    """

    def __init__(self, config_path, **kwargs):
        super(AirsideAgent, self).__init__(**kwargs)

        # list of class attributes.  Default values will be filled in from reading config file
        # string attributes
        self.analysis_name = ""
        self.sensitivity = ""
        self.fan_status = ""
        self.zone_reheat = ""
        self.zone_damper = ""
        self.duct_stp = ""
        self.duct_stp_stpt = ""
        self.sa_temp = ""
        self.fan_speedcmd = ""
        self.sat_stpt = ""
        self.fan_status_name = ""
        self.fan_sp_name = ""
        self.duct_stp_stpt_name = ""
        self.duct_stp_name = ""
        self.sa_temp_name = ""
        self.sat_stpt_name = ""
        self.zn_damper_name = ""
        self.zn_reheat_name = ""

        #int attributes
        self.no_required_data = 0
        self.warm_up_time = 0
        self.data_window = 0
        self.fan_speed = None

        #float attributes
        self.stcpr_retuning = 0.0
        self.min_stcpr_stpt = 0.0
        self.max_stcpr_stpt = 0.0
        self.sat_retuning = 0.0
        self.min_sat_stpt = 0.0
        self.max_sat_stpt = 0.0
        self.low_sf_thr = 0.0
        self.high_sf_thr = 0.0
        self.stcpr_stpt_deviation_thr = 0.0
        self.zn_high_damper_thr = 0.0
        self.zn_low_damper_thr = 0.0
        self.hdzn_damper_thr = 0.0
        self.stcpr_reset_thr = 0.0
        self.sat_stpt_deviation_thr = 0.0
        self.sat_high_damper_thr = 0.0
        self.rht_on_thr = 0.0
        self.percent_reheat_thr = 0.0
        self.percent_damper_thr = 0.0
        self.reheat_valve_thr = 0.0
        self.sat_reset_thr = 0.0
        self.unocc_time_thr = 0.0
        self.unocc_stp_thr = 0.0
        self.device_lock_duration = 0.0

        #list attributes
        self.device_list = []
        self.units = []
        self.arguments = []
        self.point_mapping = []
        self.monday_sch = []
        self.tuesday_sch = []
        self.wednesday_sch = []
        self.thursday_sch = []
        self.friday_sch = []
        self.saturday_sch = []
        self.sunday_sch = []
        self.fan_status_data = []
        self.stcpr_stpt_data = []
        self.stc_pr_data = []
        self.sat_stpt_data = []
        self.sat_data = []
        self.zn_rht_data = []
        self.zn_dmpr_data = []
        self.fan_sp_data = []
        self.stcpr_stpt_deviation_thr_dict = {}
        self.sat_stpt_deviation_thr_dict = {}
        self.percent_reheat_thr_dict = {}
        self.percent_damper_thr_dict = {}
        self.reheat_valve_thr_dict = {}
        self.sat_high_damper_thr_dict = {}
        self.zn_high_damper_thr_dict = {}
        self.zn_low_damper_thr_dict = {}
        self.hdzn_damper_thr_dict = {}
        self.unocc_stp_thr_dict = {}
        self.unocc_time_thr_dict = {}
        self.sat_reset_threshold_dict = {}
        self.stcpr_reset_threshold_dict = {}
        self.command_tuple = None

        #bool attributes
        self.auto_correct_flag = None
        self.warm_up_start = None
        self.warm_up_flag = True
        self.unit_status = None
        self.low_sf_condition = None
        self.high_sf_condition = None
        self.actuation_mode = None

        #diagnostics
        self.stcpr_aircx = None
        self.sat_aircx = None
        self.sched_reset_aircx = None

        # start reading all the class configs and check them
        self.read_config(config_path)
        self.read_argument_config(config_path)
        self.read_point_mapping()
        self.configuration_value_check()
        self.create_thresholds()
        self.create_diagnostics()


    def read_config(self, config_path):
        """
        Use volttrons config reader to grab and parse out configuration file
        config_path: The path to the agents configuration file
        """
        config = utils.load_config(config_path)
        self.analysis_name = config.get("analysis_name", "analysis_name")
        self.actuation_mode = config.get("actuation_mode", "PASSIVE")
        self.device_lock_duration = config.get("device_lock_duration", 10.0)
        self.device = config.get("device", {})
        if "campus" in self.device:
            self.campus = self.device["campus"]
        if "building" in self.device:
            self.building = self.device["building"]
        if "unit" in self.device:
            # units will be a dictionary with subdevices
            self.units = self.device["unit"]
        for u in self.units:
            # building the connection string for each unit
            self.device_list.append(
                topics.DEVICES_VALUE(campus=self.campus, building=self.building, unit=u, path="", point="all"))
            # loop over subdevices and add them
            if "subdevices" in self.units[u]:
                for sd in self.units[u]["subdevices"]:
                    self.device_list.append(
                        topics.DEVICES_VALUE(campus=self.campus, building=self.building, unit=u, path=sd, point="all"))

    def read_argument_config(self, config_path):
        """read all the config arguments section
        no return
        """
        config = utils.load_config(config_path)
        self.arguments = config.get("arguments", {})

        self.no_required_data = self.read_argument("no_required_data", 10)
        self.warm_up_time = self.read_argument("warm_up_time", 15)
        self.data_window = self.read_argument("data_window", None)
        self.stcpr_retuning = self.read_argument("stcpr_retuning", 0.15)
        self.min_stcpr_stpt = self.read_argument("min_stcpr_stpt", 0.5)
        self.max_stcpr_stpt= self.read_argument("max_stcpr_stpt", 2.5)
        self.sat_retuning = self.read_argument("sat_retuning", 1.0)
        self.min_sat_stpt = self.read_argument("min_sat_stpt", 50.0)
        self.max_sat_stpt = self.read_argument("max_sat_stpt", 70.0)
        self.low_sf_thr = self.read_argument("low_sf_thr", 20.0)
        self.high_sf_thr = self.read_argument("high_sf_thr", 95.0)
        self.auto_correct_flag = self.read_argument("auto_correct_flag", False)
        self.stcpr_stpt_deviation_thr = self.read_argument("stcpr_stpt_deviation_thr", 20.0)
        self.zn_high_damper_thr = self.read_argument("zn_high_damper_thr", 90.0)
        self.zn_low_damper_thr = self.read_argument("zn_low_damper_thr", 25.0)
        self.hdzn_damper_thr = self.read_argument("hdzn_damper_thr", 30.0)
        self.stcpr_reset_thr = self.read_argument("stcpr_reset_thr", 0.25)
        self.sat_stpt_deviation_thr = self.read_argument("sat_stpt_deviation_thr", 5.0)
        self.sat_high_damper_thr = self.read_argument("sat_high_damper_thr", 80.0)
        self.rht_on_thr = self.read_argument("rht_on_thr", 10.0)
        self.percent_reheat_thr = self.read_argument("percent_reheat_thr", 25.0)
        self.percent_damper_thr = self.read_argument("percent_damper_thr", 60.0)
        self.reheat_valve_thr = self.read_argument("reheat_valve_thr", 50.0)
        self.sat_reset_thr = self.read_argument("sat_reset_thr", 2.0)
        self.unocc_time_thr = self.read_argument("unocc_time_thr", 40.0)
        self.unocc_stp_thr = self.read_argument("unocc_stp_thr", 0.2)
        self.monday_sch = self.read_argument("monday_sch", ["5:30", "18:30"])
        self.tuesday_sch = self.read_argument("tuesday_sch", ["5:30", "18:30"])
        self.wednesday_sch = self.read_argument("wednesday_sch", ["5:30", "18:30"])
        self.thursday_sch = self.read_argument("thursday_sch", ["5:30", "18:30"])
        self.friday_sch = self.read_argument("friday_sch", ["5:30", "18:30"])
        self.saturday_sch = self.read_argument("saturday_sch", ["0:00", "0:00"])
        self.sunday_sch = self.read_argument("saturday_sch", ["0:00", "0:00"])
        self.analysis_name = self.read_argument("analysis_name", "")
        self.sensitivity = self.read_argument("sensitivity", "default")
        self.point_mapping = self.read_argument("point_mapping", {})



    def read_argument(self, config_key, default_value):
        """Method that reads an argument from the config file and returns the value or returns the default value if key is not present in config file
        return mixed (string or float or int or dict)
        """
        return_value = default_value
        if config_key in self.arguments:
            return_value = self.arguments[config_key]
        return return_value

    def read_point_mapping(self):
        """Method that reads the point mapping and sets the values
        no return
        """
        self.fan_status = self.get_point_mapping_or_none("fan_status")
        self.zone_reheat = self.get_point_mapping_or_none("zone_reheat")
        self.zone_damper = self.get_point_mapping_or_none("zone_damper")
        self.duct_stp = self.get_point_mapping_or_none("duct_stp")
        self.duct_stp_stpt = self.get_point_mapping_or_none("duct_stp_stpt")
        self.sa_temp = self.get_point_mapping_or_none("sa_temp")
        self.fan_speedcmd = self.get_point_mapping_or_none("fan_speedcmd")
        self.sat_stpt = self.get_point_mapping_or_none("sat_stpt")
        self.fan_status_name = self.get_point_mapping_or_none("fan_status")
        self.fan_sp_name = self.get_point_mapping_or_none("fan_speedcmd")
        self.duct_stp_stpt_name = self.get_point_mapping_or_none("duct_stcpr_stpt")
        self.duct_stp_name = self.get_point_mapping_or_none("duct_stcpr")
        self.sa_temp_name = self.get_point_mapping_or_none("sa_temp")
        self.sat_stpt_name = self.get_point_mapping_or_none("sat_stpt")
        self.zn_damper_name = self.get_point_mapping_or_none("zn_damper")
        self.zn_reheat_name = self.get_point_mapping_or_none("zn_reheat")

    def get_point_mapping_or_none(self, name):
        """ Get the item from the point mapping, or return None
        return mixed (string or float or int or dic
        """
        value = self.point_mapping.get(name, None)
        return value

    def configuration_value_check(self):
        """Method goes through the configuration values and checks them for correctness.  Will error if values are not correct. Some may change based on specific settings
        no return
        """
        if self.sensitivity is not None and self.sensitivity == "custom":
            self.stcpr_stpt_deviation_thr = max(10.0, min(self.stcpr_stpt_deviation_thr, 30.0))
            self.zn_high_damper_thr = max(70.0, min(self.zn_high_damper_thr, 70.0))
            self.zn_low_damper_thr = max(0.0, min(self.zn_low_damper_thr, 35.0))
            self.hdzn_damper_thr = max(20.0, min(self.hdzn_damper_thr, 50.0))
            self.stcpr_reset_thr = max(0.1, min(self.stcpr_reset_thr, 0.5))

            self.sat_stpt_deviation_thr = max(2.0, min(self.sat_stpt_deviation_thr, 10.0))
            self.rht_on_thr = max(5.0, min(self.rht_on_thr, 30.0))
            self.sat_high_damper_thr = max(70.0, min(self.sat_high_damper_thr, 90.0))
            self.percent_reheat_thr = max(10.0, min(self.percent_reheat_thr, 40.0))
            self.percent_damper_thr = max(45.0, min(self.percent_damper_thr, 75.0))
            self.reheat_valve_thr = max(25.0, min(self.reheat_valve_thr, 75.0))
            self.sat_reset_thr = max(1.0, min(self.reheat_valve_thr, 5.0))

            self.unocc_time_thr = max(20.0, min(self.unocc_time_thr, 60.0))
            self.unocc_stp_thr = max(0.125, min(self.unocc_stp_thr, 0.3))

            self.stcpr_retuning = max(0.1, min(self.stcpr_retuning, 0.25))
            self.sat_retuning = max(1.0, min(self.sat_retuning, 3.0))
        else:
            self.stcpr_stpt_deviation_thr = 20.0
            self.zn_high_damper_thr = 90.0
            self.zn_low_damper_thr = 25.0
            self.hdzn_damper_thr = 30.0
            self.stcpr_reset_thr = 0.25

            self.sat_stpt_deviation_thr = 5.0
            self.rht_on_thr = 10.0
            self.sat_high_damper_thr = 80.0
            self.percent_reheat_thr = 25.0
            self.percent_damper_thr = 60.0
            self.reheat_valve_thr = 50.0
            self.sat_reset_thr = 2.0

            self.unocc_time_thr = 40.0
            self.unocc_stp_thr = 0.2

            self.stcpr_retuning = 0.15
            self.sat_retuning = 1

        self.data_window = td(minutes=self.data_window) if self.data_window is not None else None
        self.no_required_data = int(self.no_required_data)
        self.low_sf_thr = float(self.low_sf_thr)
        self.high_sf_thr = float(self.high_sf_thr)
        self.warm_up_time = td(minutes=self.warm_up_time)

        if self.actuation_mode == "ACTIVE":
            self.actuation_mode = True
        else:
            self.actuation_mode = False

        if self.fan_sp_name is None and self.fan_status_name is None:
            _log.error("SupplyFanStatus or SupplyFanSpeed are required to verify AHU status.")
            sys.exit()

    def create_thresholds(self):
        """Create all the threshold dictionaries needed"""
        self.stcpr_stpt_deviation_thr_dict = {
            "low": self.stcpr_stpt_deviation_thr * 1.5,
            "normal": self.stcpr_stpt_deviation_thr,
            "high": self.stcpr_stpt_deviation_thr * 0.5
        }
        self.sat_stpt_deviation_thr_dict = {
            "low": self.sat_stpt_deviation_thr * 1.5,
            "normal": self.sat_stpt_deviation_thr,
            "high": self.sat_stpt_deviation_thr * 0.5
        }
        self.percent_reheat_thr_dict = {
            "low": self.percent_reheat_thr,
            "normal": self.percent_reheat_thr,
            "high": self.percent_reheat_thr
        }
        self.percent_damper_thr_dict = {
            "low": self.percent_damper_thr + 15.0,
            "normal": self.percent_damper_thr,
            "high": self.percent_damper_thr - 15.0
        }
        self.reheat_valve_thr_dict = {
            "low": self.reheat_valve_thr * 1.5,
            "normal": self.reheat_valve_thr,
            "high": self.reheat_valve_thr * 0.5
        }
        self.sat_high_damper_thr_dict = {
            "low": self.sat_high_damper_thr + 15.0,
            "normal": self.sat_high_damper_thr,
            "high": self.sat_high_damper_thr - 15.0
        }
        self.zn_high_damper_thr_dict = {
            "low": self.zn_high_damper_thr + 5.0,
            "normal": self.zn_high_damper_thr,
            "high": self.zn_high_damper_thr - 5.0
        }
        self.zn_low_damper_thr_dict = {
            "low": self.zn_low_damper_thr,
            "normal": self.zn_low_damper_thr,
            "high": self.zn_low_damper_thr
        }
        self.hdzn_damper_thr_dict = {
            "low": self.hdzn_damper_thr - 5.0,
            "normal": self.hdzn_damper_thr,
            "high": self.hdzn_damper_thr + 5.0
        }
        self.unocc_stp_thr_dict = {
            "low": self.unocc_stp_thr * 1.5,
            "normal": self.unocc_stp_thr,
            "high": self.unocc_stp_thr * 0.625
        }
        self.unocc_time_thr_dict = {
            "low": self.unocc_time_thr * 1.5,
            "normal": self.unocc_time_thr,
            "high": self.unocc_time_thr * 0.5
        }
        self.sat_reset_threshold_dict = {
            "low": max(self.sat_reset_thr - 1.0, 0.5),
            "normal": self.sat_reset_thr,
            "high": self.sat_reset_thr + 1.0
        }
        self.stcpr_reset_threshold_dict = {
            "low": self.stcpr_reset_thr * 1.5,
            "normal": self.stcpr_reset_thr,
            "high": self.stcpr_reset_thr * 0.5
        }

    def create_diagnostics(self):
        """creates the diagnostic classes
        No return
        """
        self.stcpr_aircx = DuctStaticAIRCx()
        self.stcpr_aircx.set_class_values(self.command_tuple, self.no_required_data, self.data_window, self.auto_correct_flag,
                                          self.stcpr_stpt_deviation_thr, self.max_stcpr_stpt,self.stcpr_retuning, self.zn_high_damper_thr,
                                          self.zn_low_damper_thr, self.hdzn_damper_thr, self.min_stcpr_stpt, self.analysis, self.duct_stp_stpt_name)

        self.sat_aircx = SupplyTempAIRCx()
        self.sat_aircx.set_class_values(self.command_tuple, self.no_required_data, self.data_window, self.auto_correct_flag,
                                        self.sat_stpt_deviation_thr_dict, self.rht_on_thr,
                                        self.sat_high_damper_thr_dict, self.percent_damper_thr_dict,
                                        self.percent_reheat_thr_dict, self.min_sat_stpt, self.sat_retuning,
                                        self.reheat_valve_thr_dict, self.max_sat_stpt, self.analysis, self.sat_stpt_cname)

        self.sched_reset_aircx = SchedResetAIRCx()
        self.sched_reset_aircx.set_class_values(self.unocc_time_thr, self.unocc_stp_thr, self.monday_sch, self.tuesday_sch, self.wednesday_sch,
                                                self.thursday_sch, self.friday_sch, self.saturday_sch, self.sunday_sch, self.no_required_data,
                                                self.stcpr_reset_threshold, self.sat_reset_threshold, self.analysis)
    def parse_data_message(self, message):
        """Breaks down the passed VOLTTRON message
        message: dictionary
        no return
        """
        data_message = message[0]
        # reset the data arrays on new message
        self.fan_status_data = []
        self.stcpr_stpt_data = []
        self.stc_pr_data = []
        self.sat_stpt_data = []
        self.sat_data = []
        self.zn_rht_data = []
        self.zn_dmpr_data = []
        self.fan_sp_data = []

        for key in data_message:
            value = data_message[key]
            if value is None:
                continue
            if key == self.fan_status_name:
                self.fan_status_data.append(value)
            elif key == self.duct_stp_stpt_name:
                self.stcpr_stpt_data.append(value)
            elif key == self.duct_stp_name:
                self.stc_pr_data.append(value)
            elif key == self.sat_stpt_name:
                self.sat_stpt_data.append(value)
            elif key == self.sa_temp_name:
                self.sat_data.append(value)
            elif key == self.zn_reheat_name:
                self.zn_rht_data.append(value)
            elif key == self.zn_damper_name:
                self.zn_dmpr_data.append(value)
            elif key == self.fan_sp_name:
                self.fan_sp_data.append(value)


    def check_for_missing_data(self):
        """Method that checks the parsed message results for any missing data
        return bool
        """
        missing_data = []
        if not self.fan_status_data and not self.fan_sp_data:
            self.missing_data.append(self.fan_status_name)
        if not self.sat_data:
            self.missing_data.append(self.sa_temp_name)
        if not self.zn_rht_data:
            self.missing_data.append(self.zn_reheat_name)
        if not self.sat_stpt_data:
            _log.info("SAT set point data is missing.")
        if not self.stc_pr_data:
            self.missing_data.append(self.duct_stp_name)
        if not self.stcpr_stpt_data:
            _log.info("Duct static pressure set point data is missing.")
        if not self.zn_dmpr_data:
            self.missing_data.append(self.zn_damper_name)

        if self.missing_data:
            return True
        return False

    def check_fan_status(self, current_time):
        """Check the status and speed of the fan
        current_time: datetime time delta
        return int
        """
        if self.fan_status_data:
            supply_fan_status = int(max(self.fan_status_data))
        else:
            supply_fan_status = None

        if self.fan_sp_data:
            self.fan_speed = mean(self.fan_sp_data)
        else:
            self.fan_speed = None
        if supply_fan_status is None:
            if self.fan_speed > self.low_sf_thr:
                supply_fan_status = 1
            else:
                supply_fan_status = 0

        if not supply_fan_status:
            if self.unit_status is None:
                self.unit_status = current_time
        else:
            self.unit_status = None
        return supply_fan_status

    def check_elapsed_time(self, current_time):
        """Check on time since last message to see if it is in data window
        current_time: datetime time delta
        condition: datetime time delta
        message: string
        """
        condition = self.unit_status
        message = common.FAN_OFF
        if condition is not None:
            elapsed_time = current_time - condition
        else:
            elapsed_time = td(minutes=0)
        if self.data_window is not None:
            if elapsed_time >= self.data_window:
                common.pre_conditions(message, common.dx_list, self.analysis_name, current_time)
                self.clear_all()
        elif condition is not None and condition.hour != current_time.hour:
            message_time = condition.replace(minute=0)
            common.pre_conditions(message, common.dx_list, self.analysis_name, message_time)
            self.clear_all()

    def clear_all(self):
        """Reinitialize all data arrays for diagnostics.
        no return
        """
        self.sat_aircx.reinitialize()
        self.stcpr_aircx.reinitialize()
        self.warm_up_start = None
        self.warm_up_flag = True
        self.unit_status = None


    @Core.receiver("onstart")
    def onstart_subscriptions(self, sender, **kwargs):
        """Method used to setup data subscription on startup of the agent"""
        for device in self.device_list:
            self.vip.pubsub.subscribe(peer="pubsub", prefix=device, callback=self.new_data_message)

    def new_data_message(self, peer, sender, bus, topic, headers, message):
        """
        Call back method for curtailable device data subscription.
        peer: string
        sender: string
        bus: string
        topic: string
        headers: dict
        message: dict
        no return
        """
        self.command_tuple = {}
        current_time = parser.parse(headers["Date"])
        _log.info("Processing Results!")
        self.parse_data_message(message)
        missing_data = self.check_for_missing_data()
        # want to do no further parsing if data is missing
        if missing_data:
            _log.info("Missing data from publish: {}".format(self.missing_data))
            return self.check_result_command()

        current_fan_status = self.check_fan_status(current_time)
        self.sched_reset_aircx.schedule_reset_aircx(current_time, self.stc_pr_data, self.stcpr_stpt_data, self.sat_stpt_data, current_fan_status)
        self.check_elapsed_time(current_time)
        if not current_fan_status:
            _log.info("Supply fan is off: {}".format(current_time))
            self.warm_up_flag = True
            return self.check_result_command()
        _log.info("Supply fan is on: {}".format(current_time))

        if self.fan_speed is not None and self.fan_speed > self.high_sf_thr:
            self.low_sf_condition = True
        else:
            self.low_sf_condition = False

        if self.fan_speed is not None and self.fan_speed < self.low_sf_thr:
            self.high_sf_condition = True
        else:
            self.high_sf_condition = False

        if self.warm_up_flag:
            self.warm_up_flag = False
            self.warm_up_start = current_time
            return self.check_result_command()

        if self.warm_up_start is not None and (current_time - self.warm_up_start) < self.warm_up_time:
            _log.info("Unit is in warm-up. Data will not be analyzed.")
            return self.check_result_command()

        self.stcpr_aircx.stcpr_aircx(current_time, self.stcpr_stpt_data, self.stc_pr_data, self.zn_dmpr_data, self.low_sf_cond, self.high_sf_cond)
        self.sat_aircx.sat_aircx(current_time, self.sat_data, self.sat_stpt_data, self.zn_rht_data, self.zn_dmpr_data)

    def check_result_command(self):
        """Check to see if any commands need to be ran based on diagnostic results"""

        base_actuator_path = topics.RPC_DEVICE_PATH(campus=self.campus, building=self.building, unit=None, path="", point=None)
        for device in self.device_list:
            for point, new_value in self.command_tuple.items():
                point_path = base_actuator_path(unit=device, point=point)
                try:
                    _log.info("Set point {} to {}".format(point_path, new_value))
                    self.actuation_vip.call("platform.actuator", "set_point", "rcx", point_path, new_value).get(timeout=15)
                except RemoteError as ex:
                    _log.warning("Failed to set {} to {}: {}".format(point_path, new_value, str(ex)))
                    continue

def main(argv=sys.argv):
    """Main method called by the app."""
    try:
        utils.vip_main(AirsideAgent)
    except Exception as exception:
        _log.exception("unhandled exception")
        _log.error(repr(exception))


if __name__ == "__main__":
    """Entry point for script"""
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass

