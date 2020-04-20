import sys
import logging
from datetime import timedelta as td
from dateutil import parser
from volttron.platform.agent import utils
from volttron.platform.messaging import topics
from volttron.platform.agent.math_utils import mean
from volttron.platform.agent.utils import setup_logging
from volttron.platform.vip.agent import Agent, Core

from . import constants


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

        #int attributes
        self.no_required_data = 0
        self.warm_up_time = 0
        self.data_window = 0

        #float attributes
        self.stcpr_retuning = 0.0
        self.min_stcpr_stpt = 0.0
        self.max_stcpr_stpt = 0.0
        self.sat_returning = 0.0
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

        #bool attributes
        self.auto_correct_flag = None

        # start reading all the class configs and check them
        self.read_config(config_path)
        self.read_argument_config(config_path)
        self.read_point_mapping()
        self.configuration_value_check()
        self.create_diagnostics()


    def read_config(self, config_path):
        """
        Use volttrons config reader to grab and parse out configuration file
        config_path: The path to the agents configuration file
        """
        config = utils.load_config(config_path)
        self.analysis_name = config.get("analysis_name", "analysis_name")
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
        pass

    def get_point_mapping_or_none(self, name):
        """ Get the item from the point mapping, or return None
        return mixed (string or float or int or dic
        """
        pass

    def configuration_value_check(self):
        """Method goes through the configuration values and checks them for correctness.  Will error if values are not correct. Some may change based on specific settings
        no return
        """
        pass

    def create_diagnostics(self):
        """creates the diagnostic classes
        No return
        """
        pass

    def parse_data_message(self, message):
        """Breaks down the passed VOLTTRON message
        message: dictionary
        no return
        """
        pass

    def check_for_missing_data(self):
        """Method that checks the parsed message results for any missing data
        return bool
        """
        pass

    def check_fan_status(self, current_time):
        """Check the status and speed of the fan
        current_time: datetime time delta
        return int
        """
        pass


    def clear_all(self):
        """Reinitialize all data arrays for diagnostics.
        no return
        """
        pass

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
        pass


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

