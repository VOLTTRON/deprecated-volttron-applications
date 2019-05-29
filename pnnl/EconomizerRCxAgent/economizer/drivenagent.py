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
import csv
import logging
import sys
import gevent
from collections import defaultdict
from datetime import timedelta as td
from dateutil.parser import parse

from volttron.platform.agent import utils
from volttron.platform.agent.utils import (setup_logging, get_aware_utc_now, format_timestamp)
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.jsonrpc import RemoteError
from volttron.platform.agent.driven import ConversionMapper
from volttron.platform.messaging import (headers as headers_mod, topics)
import dateutil.tz

__version__ = "1.0.8"

__author1__ = "Craig Allwardt <craig.allwardt@pnnl.gov>"
__author2__ = "Robert Lutes <robert.lutes@pnnl.gov>"
__author3__ = "Poorva Sharma <poorva.sharma@pnnl.gov>"
__copyright__ = "Copyright (c) 2017, Battelle Memorial Institute"
__license__ = "FreeBSD"
DATE_FORMAT = "%m-%d-%y %H:%M"

setup_logging()
_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.info, format="%(asctime)s   %(levelname)-8s %(message)s", datefmt=DATE_FORMAT)


def driven_agent(config_path, **kwargs):
    """
    Reads agent configuration and converts it to run driven agent.
    :param config_path:
    :param kwargs:
    :return:
    """
    config = utils.load_config(config_path)
    arguments = config.get("arguments")

    application = config.get("application")
    analysis_name = config.get("analysis_name", "analysis_name")
    # application_name = config.get("pretty_name", analysis_name)
    arguments.update({"analysis_name": analysis_name})

    actuation_mode = True if config.get("actuation_mode", "PASSIVE") == "ACTIVE" else False
    actuator_lock_required = config.get("require_actuator_lock", False)
    interval = config.get("interval", 60)
    vip_destination = config.get("vip_destination", None)
    timezone = config.get("local_timezone", "US/Pacific")
    device_lock_duration = config.get("device_lock_duration", 10.0)
    conversion_map = config.get("conversion_map")
    missing_data_threshold = config.get("missing_data_threshold", 90.0)

    device = config["device"]
    validation_error = ""
    if not application:
        validation_error = "Invalid application specified in config\n"
    if validation_error:
        _log.error(validation_error)
        raise ValueError(validation_error)

    converter = ConversionMapper()
    # output_file_prefix = config.get("output_file")

    klass = _get_class(application)
    # This instances is used to call the applications run method when
    # data comes in on the message bus.  It is constructed here
    # so that_process_results each time run is called the application
    # can keep it state.
    # points = arguments.pop("point_mapping")
    app_instance = klass(**arguments)

    class DrivenAgent(Agent):
        """Agent listens to message bus device and runs when data is published.
        """

        def __init__(self,
                     device,
                     actuation_mode=False,
                     actuator_lock_required=False,
                     interval=60,
                     vip_destination=None,
                     timezone="US/Pacific",
                     device_lock_duration=10.0,
                     conversion_map=None,
                     missing_data_threshold=90.0,
                     **kwargs):
            """
            Initializes agent
            :param kwargs: Any driver specific parameters"""

            super(DrivenAgent, self).__init__(**kwargs)

            self.sites_config_list = []
            self.device_topic_dict = {}
            self.site_topic_dict = {}

            self.default_config = {
                "device": device,
                "actuation_mode": actuation_mode,
                "actuator_lock_required": actuator_lock_required,
                "interval": interval,
                "vip_destination": vip_destination,
                "timezone": timezone,
                "device_lock_duration": device_lock_duration,
                "conversion_map": conversion_map,
                "missing_data_threshold": missing_data_threshold
            }
            self.vip.config.set_default("config", self.default_config)
            self.vip.config.subscribe(self.configure_main, actions=["NEW", "UPDATE"], pattern="config")
            self.vip.config.subscribe(self.update_driver, actions=["NEW", "UPDATE"], pattern="devices/*")
            self.vip.config.subscribe(self.remove_driver, actions="DELETE", pattern="devices/*")

            # master is where we copy from to get a poppable list of
            # subdevices that should be present before we run the analysis.
            self.received_input_datetime = None

            self._header_written = False
            self.file_creation_set = set()
            self.initialize_time = None

        def configure_main(self, config_name, action, contents):
            config = self.default_config.copy()
            config.update(contents)
            _log.info("configure_main with {}".format(config))

            self.unsubscribe_from_all_devices()

            self.actuation_mode = True if config.get("actuation_mode", "PASSIVE") == "ACTIVE" else False
            self.actuator_lock_required = config.get("require_actuator_lock", False)
            self.interval = config.get("interval", 60)
            self.vip_destination = config.get("vip_destination", None)
            self.timezone = config.get("local_timezone", "US/Pacific")
            self.device_lock_duration = config.get("device_lock_duration", 10.0)
            self.conversion_map = config.get("conversion_map")
            self.missing_data_threshold = config.get("missing_data_threshold", 50.0)/100.0

            self.actuation_vip = self.vip.rpc
            if self.vip_destination:
                self.agent = setup_remote_actuation(self.vip_destination)
                self.actuation_vip = self.agent.vip.rpc

            self.map_names = {}
            if self.conversion_map:
                for key, value in self.conversion_map.items():
                    self.map_names[key.lower() if isinstance(key, str) else key] = value

            _log.info("--- actuation_mode {}".format(self.actuation_mode))
            _log.info("--- require_actuator_lock {}".format(self.actuator_lock_required))
            _log.info("--- interval {}".format(self.interval))
            _log.info("--- vip_destination {}".format(self.vip_destination))
            _log.info("--- local_timezone {}".format(self.timezone))
            _log.info("--- device_lock_duration {}".format(self.device_lock_duration))
            _log.info("--- missing_data_threshold {}".format(self.missing_data_threshold))
            _log.info("--- conversion_map {}".format(self.conversion_map))
            _log.info("--- map_names {}".format(self.map_names))

            self.sites = config["device"]
            if not isinstance(self.sites, list):
                self.sites = [self.sites]

            self.sites_config_list = []
            self.site_topic_dict = {}
            self.device_topic_dict = {}

            for site in self.sites:
                campus = site.get("campus", "")
                building = site.get("building", "")
                site_name = "/".join([campus, building])
                publish_base = "/".join([analysis_name, campus, building])

                device_config = site["unit"]
                multiple_devices = isinstance(device_config, dict)
                command_devices = device_config.keys()
                site_device_topic_dict = {}
                device_topic_list = []
                subdevices_list = []

                base_actuator_path = topics.RPC_DEVICE_PATH(campus=campus, building=building, unit=None,
                                                            path="", point=None)

                site_dict = {
                    'site_name': site_name,
                    'publish_base': publish_base,
                    'multiple_devices': multiple_devices,
                    'device_topic_dict': site_device_topic_dict,
                    'device_topic_list': device_topic_list,
                    'subdevices_list': subdevices_list,
                    'command_devices': command_devices,
                    'base_actuator_path': base_actuator_path
                }
                if 'point_mapping' in site:
                    site_dict['point_mapping'] = site['point_mapping']
                self.sites_config_list.append(site_dict)

                for device_name in device_config:
                    device_topic = topics.DEVICES_VALUE(campus=campus, building=building, unit=device_name,
                                                        path="", point="all")

                    self.site_topic_dict.update({device_topic: site_dict})
                    self.device_topic_dict.update({device_topic: device_name})
                    site_device_topic_dict.update({device_topic: device_name})
                    device_topic_list.append(device_name)
                    _log.info("device_topic_list topic {} -> device {}".format(device_topic, device_name))
                    if multiple_devices:
                        for subdevice in device_config[device_name]["subdevices"]:
                            if subdevice not in subdevices_list:
                                subdevices_list.append(subdevice)
                            subdevice_topic = topics.DEVICES_VALUE(campus=campus, building=building, unit=device_name,
                                                                   path=subdevice, point="all")

                            subdevice_name = device_name + "/" + subdevice
                            self.site_topic_dict.update({subdevice_topic: site_dict})
                            self.device_topic_dict.update({subdevice_topic: subdevice_name})
                            site_device_topic_dict.update({subdevice_topic: subdevice_name})
                            device_topic_list.append(subdevice_name)
                            _log.info("device_topic_list topic {} -> subdev {}".format(subdevice_topic, subdevice_name))
                _log.info("-- Site config {}".format(site_dict))

            self.initialize_devices()
            self.subscribe_to_all_devices()

        def derive_device_topic(self, config_name):
            _, topic = config_name.split('/', 1)
            # remove any #prefix from the config name which is only used to differentiate config keys
            return topic.split('#', 1)[0]

        def derive_device_unit(self, config_name, contents):
            if 'unit' in contents:
                return contents['unit']
            _, topic = config_name.split('/', 1)
            if '#' in topic:
                return topic.split('#', 1)[1]
            return None

        def update_driver(self, config_name, action, contents):
            topic = self.derive_device_topic(config_name)
            topic_split = topic.split('/', 2)
            if len(topic_split) > 1:
                campus = topic_split[0]
                building = topic_split[1]
            if len(topic_split) > 2:
                unit = topic_split[2]
            else:
                unit = ""
            site_name = "/".join([campus, building])
            publish_base = "/".join([analysis_name, campus, building])
            command_devices = []
            site_device_topic_dict = {}
            device_topic_list = []
            subdevices_list = []

            base_actuator_path = topics.RPC_DEVICE_PATH(campus=campus, building=building, unit=None,
                                                        path="", point=None)

            site_dict = {
                'site_name': site_name,
                'publish_base': publish_base,
                'multiple_devices': False,
                'device_topic_dict': site_device_topic_dict,
                'device_topic_list': device_topic_list,
                'subdevices_list': subdevices_list,
                'command_devices': command_devices,
                'base_actuator_path': base_actuator_path
            }
            if 'point_mapping' in contents:
                site_dict['point_mapping'] = contents['point_mapping']
            if not unit:
                # lookup the subdevices from point_mapping
                for point in contents['point_mapping'].keys():
                    # remove the point name to get the subdevice
                    subdevice_name = point.rsplit('/', 1)[0]
                    sd_split = subdevice_name.rsplit('/', 1)
                    device_name = sd_split[0]
                    subdevice = ''
                    if len(sd_split) > 1:
                        subdevice = sd_split[1]
                    if subdevice not in subdevices_list:
                        subdevices_list.append(subdevice)
                        command_devices.append(subdevice)
                    subdevice_topic = topics.DEVICES_VALUE(campus=campus, building=building, unit=device_name,
                                                           path=subdevice, point="all")
                    self.site_topic_dict.update({subdevice_topic: site_dict})
                    self.device_topic_dict.update({subdevice_topic: subdevice_name})
                    site_device_topic_dict.update({subdevice_topic: subdevice_name})
                    device_topic_list.append(subdevice_name)
                    _log.info("device_topic_list topic {} -> subdev {}".format(subdevice_topic, subdevice_name))

            self.sites_config_list.append(site_dict)
            device_topic = topics.DEVICES_VALUE(campus=campus, building=building, unit=unit,
                                                path="", point="all")

            if device_topic in self.device_topic_dict:
                self.unsubscribe_from_device(device_topic)

            self.site_topic_dict.update({device_topic: site_dict})
            if unit:
                self.device_topic_dict.update({device_topic: unit})
                site_device_topic_dict.update({device_topic: unit})
                device_topic_list.append(unit)
                command_devices.append(unit)

            # overrides the publishing unit topic, which is needed for split topics
            override_unit = self.derive_device_unit(config_name, contents)
            if override_unit:
                del command_devices[:]
                command_devices.append(override_unit)

            _log.info("device_topic_list topic {} -> device {}".format(device_topic, unit))
            self.initialize_device(site_dict)
            _log.info("-- Site config {}".format(site_dict))
            for dt in site_device_topic_dict.keys():
                self.subscribe_to_device(dt)

        def remove_driver(self, config_name, action, contents):
            topic = self.derive_device_topic(config_name)
            topic_split = topic.split('/', 2)
            if len(topic_split) > 1:
                campus = topic_split[0]
                building = topic_split[1]
            if len(topic_split) > 2:
                unit = topic_split[2]
            else:
                unit = ""
            device_topic = topics.DEVICES_VALUE(campus=campus, building=building, unit=unit,
                                                path="", point="all")

            self.site_topic_dict.pop(device_topic, None)
            self.device_topic_dict.pop(device_topic, None)
            self.unsubscribe_from_device(device_topic)

        def initialize_devices(self):
            for site in self.sites_config_list:
                self.initialize_device(site)

        def initialize_device(self, site):
            _log.info("initialize_device {}".format(site))
            site['needed_devices'] = site['device_topic_list'][:]
            if 'device_values' in site:
                site['device_values'].clear()
            else:
                site['device_values'] = {}

        @Core.receiver("onstart")
        def startup(self, sender, **kwargs):
            """
            Starts up the agent and subscribes to device topics
            based on agent configuration.
            :param sender:
            :param kwargs: Any driver specific parameters
            :type sender: str
            """
            pass

        def unsubscribe_from_device(self, device):
            _log.info("Unsubscribing to " + device)
            self.vip.pubsub.unsubscribe(peer="pubsub", prefix=device, callback=self.on_analysis_message)

        def unsubscribe_from_all_devices(self):
            for device in self.device_topic_dict:
                self.unsubscribe_from_device(device)

        def subscribe_to_device(self, device):
            _log.info("Subscribing to " + device)
            self.vip.pubsub.subscribe(peer="pubsub", prefix=device, callback=self.on_analysis_message)

        def subscribe_to_all_devices(self):
            for device in self.device_topic_dict:
                self.subscribe_to_device(device)

        def _should_run_now(self, topic):
            """
            Checks if messages from all the devices are received
                before running application
            :returns: True or False based on received messages.
            :rtype: boolean
            """
            # Assumes the unit/all values will have values.
            _log.info("_should_run_now topic {} ".format(topic))
            site = self.site_topic_dict[topic]
            device_values = site['device_values']
            _log.info("_should_run_now check device_values {} ".format(device_values))
            if not device_values.keys():
                _log.info("_should_run_now FALSE")
                return False
            needed_devices = site['needed_devices']
            _log.info("_should_run_now check needed_devices {} ".format(needed_devices))
            return not needed_devices

        def aggregate_subdevice(self, device_data, topic):
            """
            Aggregates device and subdevice data for application
            :returns: True or False based on if device data is needed.
            :rtype: boolean"""
            result = True
            tagged_device_data = {}
            device_tag = self.device_topic_dict[topic]
            site = self.site_topic_dict[topic]
            needed_devices = site['needed_devices']
            device_values = site['device_values']
            _log.info("Current device to aggregate: topic {} device: {}".format(topic, device_tag))
            if device_tag not in needed_devices:
                result = False
            # optional eg: 'SomeFanSpeed' -> 'supply_fan_speed'
            mappings = site.get('point_mapping', {})
            _log.info("--- device_data -> {}".format(device_data))
            _log.info("--- mappings -> {}".format(mappings))
            for key, value in device_data.items():
                # weird ... bug
                if key.endswith(device_tag):
                    _log.warning("--- weird entry in device_data ? {} -> {}".format(key, value))
                    _log.warning("--- device_tag ? {}".format(device_tag))
                    key = key[:-len(device_tag)-1]

                # here do the mapping between the actual device topic
                # and the APP expected topic names
                k = key
                if key in mappings:
                    k = mappings[key]
                else:
                    long_key = '/'.join([device_tag, key])
                    if long_key in mappings:
                        k = mappings[long_key]

                device_data_tag = "&".join([k, device_tag])
                tagged_device_data[device_data_tag] = value
            _log.info("--- tagged_device_data -> {}".format(tagged_device_data))
            device_values.update(tagged_device_data)
            _log.info("--- device_values -> {}".format(device_values))
            if device_tag in needed_devices:
                needed_devices.remove(device_tag)
                _log.info("--- needed_devices removed [{}] -> {}".format(device_tag, needed_devices))
            return result

        def on_analysis_message(self, peer, sender, bus, topic, headers, message):
            """
            Subscribe to device data and assemble data set to pass
                to applications.
            :param peer:
            :param sender: device name
            :param bus:
            :param topic: device path topic
            :param headers: message headers
            :param message: message containing points and values dict
                    from device with point type
            :type peer: str
            :type sender: str
            :type bus: str
            :type topic: str
            :type headers: dict
            :type message: dict
            """
            _log.info("on_analysis_message: from device {} topic -> {}".format(sender, topic))
            _log.info("on_analysis_message: {} -> {}".format(headers, message))
            site = self.site_topic_dict.get(topic)
            if not site:
                _log.error("No Site configured for topic: {}".format(topic))
                return

            needed_devices = site['needed_devices']
            device_values = site['device_values']
            master_devices = site['device_topic_list']

            timestamp = parse(headers.get("Date"))
            missing_but_running = False
            if self.initialize_time is None and len(master_devices) > 1:
                self.initialize_time = self.find_reinitialize_time(timestamp)

            if self.initialize_time is not None and timestamp < self.initialize_time:
                if len(master_devices) > 1:
                    _log.info("on_analysis_message: waiting until initialize_time: {}".format(self.initialize_time))
                    return

            to_zone = dateutil.tz.gettz(self.timezone)
            timestamp = timestamp.astimezone(to_zone)
            self.received_input_datetime = timestamp
            _log.info("on_analysis_message: Current time of publish: {}".format(timestamp))

            device_data = message[0]
            if isinstance(device_data, list):
                device_data = device_data[0]

            device_needed = self.aggregate_subdevice(device_data, topic)
            if not device_needed:
                fraction_missing = float(len(needed_devices)) / len(master_devices)
                _log.warning("on_analysis_message: No device_needed: {} fraction_missing = {}".format(topic, fraction_missing))
                if fraction_missing > self.missing_data_threshold:
                    _log.error("on_analysis_message: Device values already present, reinitializing at publish: {}".format(timestamp))
                    self.initialize_device(site)
                    device_needed = self.aggregate_subdevice(device_data, topic)
                    return
                missing_but_running = True
                _log.warning("on_analysis_message: Device already present. Using available data for diagnostic.: {}".format(timestamp))
                _log.warning("on_analysis_message: Device already present - topic: {}".format(topic))
                _log.warning("on_analysis_message: All devices: {}".format(master_devices))
                _log.warning("on_analysis_message: Needed devices: {}".format(needed_devices))

            srn = self._should_run_now(topic)
            _log.info("on_analysis_message: _should_run_now {} or {}".format(srn, missing_but_running))
            if srn or missing_but_running:
                field_names = {}
                _log.info("on_analysis_message: Running for topic {}".format(topic))
                for point, data in device_values.items():
                    _log.info("on_analysis_message: --- point, data: {} -> {}".format(point, data))
                    field_names[point] = data
                if not converter.initialized and conversion_map is not None:
                    converter.setup_conversion_map(self.map_names, field_names)

                results = app_instance.run(timestamp, converter.process_row(field_names))
                self.process_results(site, results)
                self.initialize_device(site)
                if missing_but_running:
                    device_needed = self.aggregate_subdevice(device_data, topic)
            else:
                _log.info("on_analysis_message: Still need {} before running.".format(needed_devices))

        def process_results(self, site, results):
            """
            Runs driven application with converted data. Calls appropriate
                methods to process commands, log and table_data in results.
            :param results: Results object containing commands for devices,
                    log messages and table data.
            :type results: Results object \\volttron.platform.agent.driven
            :returns: Same as results param.
            :rtype: Results object \\volttron.platform.agent.driven
            """
            _log.info("Processing Results!")
            actuator_error = False
            if self.actuation_mode:
                if results.devices and self.actuator_lock_required:
                    actuator_error = self.actuator_request(site, results.devices)
                elif results.commands and self.actuator_lock_required:
                    actuator_error = self.actuator_request(site, site['command_devices'])
                if not actuator_error:
                    results = self.actuator_set(site, results)
            for log in results.log_messages:
                _log.info("LOG: {}".format(log))
            for key, value in results.table_output.items():
                _log.info("TABLE: {}->{}".format(key, value))
            # if output_file_prefix is not None:
            #   results = self.create_file_output(results)
            if len(results.table_output.keys()):
                results = self.publish_analysis_results(site, results)
            return results

        def publish_analysis_results(self, site, results):
            """
            Publish table_data in analysis results to the message bus for
                capture by the data historian.

            :param results: Results object containing commands for devices,
                    log messages and table data.
            :type results: Results object \\volttron.platform.agent.driven
            :returns: Same as results param.
            :rtype: Results object \\volttron.platform.agent.driven
            """
            to_publish = defaultdict(dict)
            for app, analysis_table in results.table_output.items():
                try:
                    name_timestamp = app.split("&")
                    timestamp = name_timestamp[1]
                except:
                    timestamp = self.received_input_datetime
                    timestamp = format_timestamp(timestamp)

                headers = {headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON, headers_mod.DATE: timestamp, }
                for entry in analysis_table:
                    for point, result in entry.items():
                        for device in site['command_devices']:
                            publish_topic = "/".join([site['publish_base'], device, point])
                            analysis_topic = topics.RECORD(subtopic=publish_topic)
                            # datatype = str(type(value))
                            to_publish[analysis_topic] = result

                for result_topic, result in to_publish.items():
                    self.vip.pubsub.publish("pubsub", result_topic, headers, result)
                to_publish.clear()
            return results

        def create_file_output(self, results):
            """
            Create results/data files for testing and algorithm validation
            if table data is present in the results.

            :param results: Results object containing commands for devices,
                    log messages and table data.
            :type results: Results object \\volttron.platform.agent.driven
            :returns: Same as results param.
            :rtype: Results object \\volttron.platform.agent.driven"""
            tag = 0
            for key, value in results.table_output.items():
                for row in value:
                    name_timestamp = key.split("&")
                    _name = name_timestamp[0]
                    timestamp = name_timestamp[1]
                    file_name = _name + str(tag) + ".csv"
                    tag += 1
                    if file_name not in self.file_creation_set:
                        self._header_written = False
                    self.file_creation_set.update([file_name])
                    with open(file_name, "a+") as file_to_write:
                        row.update({"Timestamp": timestamp})
                        _keys = row.keys()
                        file_output = csv.DictWriter(file_to_write, _keys)
                        if not self._header_written:
                            file_output.writeheader()
                            self._header_written = True
                        file_output.writerow(row)
                    file_to_write.close()
            return results

        def actuator_request(self, site, command_equip):
            """
            Calls the actuator"s request_new_schedule method to get
                    device schedule
            :param command_equip: contains the names of the devices
                that will be scheduled with the ActuatorAgent.
            :type: dict or list
            :returns: Return result from request_new_schedule method
                and True or False for error in scheduling device.
            :rtype: boolean
            :Return Values:

                request_error = True/False

            warning:: Calling without previously scheduling a device and not within
                         the time allotted will raise a LockError"""

            _now = get_aware_utc_now()
            str_now = format_timestamp(_now)
            _end = _now + td(minutes=self.device_lock_duration)
            str_end = format_timestamp(_end)
            for device in command_equip:
                actuation_device = site['base_actuator_path'](unit=device, point="")
                schedule_request = [[actuation_device, str_now, str_end]]
                try:
                    _log.info("Make Request {} for start {} and end {}".format(actuation_device, str_now, str_end))
                    result = self.actuation_vip.call("platform.actuator", "request_new_schedule", "rcx",
                                                     actuation_device, "HIGH", schedule_request).get(timeout=15)
                except RemoteError as ex:
                    _log.warning("Failed to schedule device {} (RemoteError): {}".format(device, str(ex)))
                    request_error = True
                if result["result"] == "FAILURE":
                    if result["info"] == "TASK_ID_ALREADY_EXISTS":
                        _log.info("Task to schedule device already exists " + device)
                        request_error = False
                    else:
                        _log.warning("Failed to schedule device (unavailable) " + device)
                        request_error = True
                else:
                    request_error = False

            return request_error

        def actuator_set(self, site, results):
            """
            Calls the actuator"s set_point method to set point on device

            :param results: Results object containing commands for devices,
                    log messages and table data.
            :type results: Results object \\volttron.platform.agent.driven"""

            def make_actuator_set(device, point_value_dict):
                for point, new_value in point_value_dict.items():
                    point_path = site['base_actuator_path'](unit=device, point=point)
                    try:
                        _log.info("Set point {} to {}".format(point_path, new_value))
                        self.actuation_vip.call("platform.actuator", "set_point", "rcx", point_path,
                                                new_value).get(timeout=15)
                    except RemoteError as ex:
                        _log.warning("Failed to set {} to {}: {}".format(point_path, new_value, str(ex)))
                        continue

            for device, point_value_dict in results.devices.items():
                make_actuator_set(device, point_value_dict)

            for device in site['command_devices']:
                make_actuator_set(device, results.commands)
            return results

        def find_reinitialize_time(self, current_time):
            midnight = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            seconds_from_midnight = (current_time - midnight).total_seconds()
            offset = seconds_from_midnight % self.interval
            previous_in_seconds = seconds_from_midnight - offset
            next_in_seconds = previous_in_seconds + self.interval
            from_midnight = td(seconds=next_in_seconds)
            _log.debug("Start of next scrape interval: {}".format(midnight + from_midnight))
            return midnight + from_midnight

    def setup_remote_actuation(vip_destination):
        event = gevent.event.Event()
        agent = Agent(address=vip_destination)
        gevent.spawn(agent.core.run, event)
        event.wait(timeout=15)
        return agent

    DrivenAgent.__name__ = "DrivenLoggerAgent"
    return DrivenAgent(
        device,
        actuation_mode,
        actuator_lock_required,
        interval,
        vip_destination,
        timezone,
        device_lock_duration,
        conversion_map,
        missing_data_threshold,
        **kwargs
        )


def _get_class(kls):
    """Get driven application information."""
    parts = kls.split(".")
    module = ".".join(parts[:-1])
    main_mod = __import__(module)
    for comp in parts[1:]:
        main_mod = getattr(main_mod, comp)
    return main_mod


def main(argv=sys.argv):
    """ Main method."""
    utils.vip_main(driven_agent)


if __name__ == "__main__":
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
