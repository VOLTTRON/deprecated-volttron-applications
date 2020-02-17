import os
import sys
import logging
import math
from datetime import timedelta as td, datetime as dt
from dateutil import parser
import gevent
import dateutil.tz
from volttron.platform.agent import utils
from volttron.platform.messaging import topics
from volttron.platform.agent.math_utils import mean
from volttron.platform.agent.utils import (setup_logging, format_timestamp, get_aware_utc_now)
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.jsonrpc import RemoteError

__version__ = "1.2.0"

setup_logging()
_log = logging.getLogger(__name__)

class EconimizerAgent(Agent):

    def __init__(self, config_path, **kwargs):
        super(EconimizerAgent, self).__init__(**kwargs)

        #list of class attributes.  Default values will be filled in from reading config file
        #string attributes
        self.campus = ""
        self.building = ""
        self.agent_id = ""
        self.device_type = ""
        self.econimizer_type = ""

        #list attributes
        self.device_list = []
        self.units = []

        #int attributes
        self.data_window = 0
        self.no_required_data = 0
        self.open_damper_time = 0

        #float attributes
        self.oaf_temperature_threshold = 0.0
        self.oaf_econimizing_threshold = 0.0
        self.cooling_enabled_threshold = 0.0
        self.temp_difference_threshold = 0.0
        self.mat_low_threshold = 0.0
        self.mat_high_threshold = 0.0
        self.rat_low_threshold = 0.0
        self.rat_high_threshold = 0.0
        self.oat_low_threshold = 0.0
        self.oat_high_threshold = 0.0
        self.oat_mat_check = 0.0
        self.open_damper_threshold = 0.0
        self.minimum_damper_setpoint = 0.0
        self.desired_oaf = 0.0
        self.low_supply_fan_threshold = 0.0
        self.excess_damper_threshold = 0.0
        self.excess_oaf_threshold = 0.0
        self.ventilation_oaf_threshold = 0.0
        self.insufficient_damper_threshold = 0.0
        self.temp_damper_threshold = 0.0
        self.rated_cfm = 0.0
        self.eer = 0.0
        self.temp_deadband = 0.0

        self.read_config(config_path)


    def read_config(self, config_path):
        """
        Use volttrons config reader to grab and parse out configuration file
        :param config_path: The path to the agents configuration file
        """
        config = utils.load_config(config_path)
        #get device, then the units underneath that
        self.device = config.get("device", {})
        if "campus" in self.device:
            self.campus = self.device["campus"]
        if "building" in self.device:
            self.building = self.device["building"]
        if "unit" in self.device:
            #units will be a dictionary with subdevices
            self.units = self.device["unit"]
        for u in self.units:
            #building the connection string for each unit
            _log.info("unit is:" + str(u))
            self.device_list.append(topics.DEVICES_VALUE(campus=self.campus, building=self.building, unit=u, path="", point="all"))
            #loop over subdevices and add them
            if "subdevices" in self.units[u]:
                for sd in self.units[u]["subdevices"]:
                    self.device_list.append(topics.DEVICES_VALUE(campus=self.campus, building=self.building, unit=u, path=sd, point="all"))



    @Core.receiver("onstart")
    def onstart_subscriptions(self, sender, **kwargs):
        """Method used to setup data subscription on startup of the agent"""
        for device in self.device_list:
            _log.info("Subscribing to " + device)
            self.vip.pubsub.subscribe(peer="pubsub", prefix=device, callback=self.new_data_message)


    def new_data_message(self, peer, sender, bus, topic, headers, message):
        """
        Call back method for curtailable device data subscription.
        :param peer:
        :param sender:
        :param bus:
        :param topic:
        :param headers:
        :param message:
        :return:
        """
        _log.info("Data Received for {}".format(topic))










def main(argv=sys.argv):
    """Main method called by the aip."""
    try:
        utils.vip_main(EconimizerAgent)
    except Exception as exception:
        _log.exception("unhandled exception")
        _log.error(repr(exception))


if __name__ == "__main__":
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
