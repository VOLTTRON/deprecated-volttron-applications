import os
import sys
import logging
import math
from datetime import timedelta as td, datetime as dt
from dateutil import parser
import gevent
import dateutil.tz
from sympy.parsing.sympy_parser import parse_expr
from sympy import symbols
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

        self.devicelist = []
        self.campus = ""
        self.building = ""
        self.agent_id = ""
        self.units = {}

        self.read_config(config_path)


    def read_config(self, config_path):
        """
        Use volttrons config reader to grab and parse out configuration file
        :param config_path: The path to the agents configuration file
        """
        config = utils.load_config(config_path)
        self.campus = config.get("campus", "")
        self.building = config.get("building", "")
        self.units = config.get("unit", {})
        for u in self.units:
            print(u)



    @Core.receiver("onstart")
    def onstart_subscriptions(self, sender, **kwargs):
        """Method used to setup data subscription on startup of the agent"""
        for device in self.device_list:
            _log.debug("Subscribing to " + device)
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
