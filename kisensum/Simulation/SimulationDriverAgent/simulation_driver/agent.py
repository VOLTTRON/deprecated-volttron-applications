# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, SLAC National Laboratory / Kisensum Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor SLAC / Kisensum,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# SLAC / Kisensum. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# }}}
import bisect
from datetime import timedelta
import fnmatch
import gevent
import logging
import sys
from zmq.utils import jsonapi

from volttron.platform.vip.agent import Agent, RPC
from volttron.platform.agent import utils

from driver import DriverAgent
from driver_locks import configure_socket_lock, configure_publish_lock
from interfaces import DriverInterfaceError

utils.setup_logging()
_log = logging.getLogger(__name__)

__version__ = '1.0'


class OverrideError(DriverInterfaceError):
    pass


def simulation_driver_agent(config_path, **kwargs):

    def get_config(name, default=None):
        try:
            return kwargs.pop(name)
        except KeyError:
            return config.get(name, default)

    config = utils.load_config(config_path)
    return SimulationDriverAgent(get_config('driver_config_list'),
                                 get_config('driver_scrape_interval', 0.02),
                                 heartbeat_autostart=True,
                                 **kwargs)


class SimulationDriverAgent(Agent):
    """
        Driver Agent for simulation interfaces.

        SimulationDriverAgent is a simplified copy of MasterDriverAgent.
        Its strategy for scheduling device-driver scrapes attempts to match that of the Master Driver.
        Please see services.core.MasterDriverAgent.master_driver.agent.py for additional commentary
        about this agent's implementation.
    """

    def __init__(self, driver_config_list, driver_scrape_interval=0.02, **kwargs):
        super(SimulationDriverAgent, self).__init__(**kwargs)
        self.instances = {}
        try:
            self.driver_scrape_interval = float(driver_scrape_interval)
        except ValueError:
            self.driver_scrape_interval = 0.02
        self.freed_time_slots = []
        self._name_map = {}
        self._override_devices = set()
        self._override_patterns = None
        self._override_interval_events = {}
        self.default_config = {"driver_scrape_interval": driver_scrape_interval}
        self.vip.config.set_default("config", self.default_config)
        self.vip.config.subscribe(self.configure_main, actions=["NEW", "UPDATE"], pattern="config")
        self.vip.config.subscribe(self.update_driver, actions=["NEW", "UPDATE"], pattern="devices/*")
        self.vip.config.subscribe(self.remove_driver, actions="DELETE", pattern="devices/*")

    def configure_main(self, config_name, action, contents):
        config = self.default_config.copy()
        config.update(contents)
        if action == "NEW":
            try:
                configure_socket_lock()
                configure_publish_lock(10000)
            except ValueError as e:
                _log.error("ERROR PROCESSING STARTUP CRITICAL CONFIGURATION SETTINGS: {}".format(e))
                _log.error("SIMULATION DRIVER SHUTTING DOWN")
                sys.exit(1)
        self.update_override_patterns()
        self.update_scrape_schedule(config)

    def update_override_patterns(self):
        if self._override_patterns is None:
            try:
                values = self.vip.config.get("override_patterns")
                values = jsonapi.loads(values)

                if isinstance(values, dict):
                    self._override_patterns = set()
                    for pattern, end_time in values.items():
                        # check the end_time
                        now = utils.get_aware_utc_now()
                        # If end time is indefinite, set override with indefinite duration
                        if end_time == "0.0":
                            self._set_override_on(pattern, 0.0, from_config_store=True)
                        else:
                            end_time = utils.parse_timestamp_string(end_time)
                            # If end time > current time, set override with new duration
                            if end_time > now:
                                delta = end_time - now
                                self._set_override_on(pattern, delta.total_seconds(), from_config_store=True)
                else:
                    self._override_patterns = set()
            except KeyError:
                self._override_patterns = set()
            except ValueError:
                _log.error("Override patterns is not set correctly in config store")
                self._override_patterns = set()

    def update_scrape_schedule(self, config):
        try:
            driver_scrape_interval = float(config["driver_scrape_interval"])
        except ValueError as e:
            _log.error("ERROR PROCESSING CONFIGURATION: {}".format(e))
            _log.error("Master driver scrape interval settings unchanged")
            driver_scrape_interval = None

        if self.driver_scrape_interval != driver_scrape_interval:
            self.driver_scrape_interval = driver_scrape_interval
            _log.info("Setting time delta between driver device scrapes to  " + str(driver_scrape_interval))
            # Reset all scrape schedules
            self.freed_time_slots = []
            time_slot = 0
            for driver in self.instances.itervalues():
                driver.update_scrape_schedule(time_slot, self.driver_scrape_interval)
                time_slot += 1

    def stop_driver(self, device_topic):
        real_name = self._name_map.pop(device_topic.lower(), device_topic)
        driver = self.instances.pop(real_name, None)
        if driver:
            _log.info("Stopping driver: {}".format(real_name))
            try:
                driver.core.stop(timeout=5.0)
            except StandardError as e:
                _log.error("Failure during {} driver shutdown: {}".format(real_name, e))
            bisect.insort(self.freed_time_slots, driver.time_slot)

    def update_driver(self, config_name, action, contents):
        topic = self.derive_device_topic(config_name)
        self.stop_driver(topic)
        slot = self.freed_time_slots.pop(0) if self.freed_time_slots else len(self.instances)
        _log.info("Starting driver: {}".format(topic))
        driver = DriverAgent(self, contents, slot, self.driver_scrape_interval, topic)
        gevent.spawn(driver.core.run)
        self.instances[topic] = driver
        self._name_map[topic.lower()] = topic
        self._update_override_state(topic, 'add')

    def remove_driver(self, config_name, action, contents):
        topic = self.derive_device_topic(config_name)
        self.stop_driver(topic)
        self._update_override_state(topic, 'remove')

    @staticmethod
    def derive_device_topic(config_name):
        _, topic = config_name.split('/', 1)
        return topic

    @RPC.export
    def get_point(self, path, point_name, **kwargs):
        return self.instances[path].get_point(point_name, **kwargs)

    @RPC.export
    def set_point(self, path, point_name, value, **kwargs):
        if path in self._override_devices:
            raise OverrideError(
                "Cannot set point on device {} since global override is set".format(path))
        else:
            return self.instances[path].set_point(point_name, value, **kwargs)

    @RPC.export
    def scrape_all(self, path):
        return self.instances[path].scrape_all()

    @RPC.export
    def get_multiple_points(self, path, point_names, **kwargs):
        return self.instances[path].get_multiple_points(point_names, **kwargs)

    @RPC.export
    def set_multiple_points(self, path, point_names_values, **kwargs):
        if path in self._override_devices:
            raise OverrideError(
                "Cannot set point on device {} since global override is set".format(path))
        else:
            return self.instances[path].set_multiple_points(point_names_values, **kwargs)

    @RPC.export
    def heart_beat(self):
        _log.debug("sending heartbeat")
        for device in self.instances.values():
            device.heart_beat()

    @RPC.export
    def revert_point(self, path, point_name, **kwargs):
        if path in self._override_devices:
            raise OverrideError(
                "Cannot revert point on device {} since global override is set".format(path))
        else:
            self.instances[path].revert_point(point_name, **kwargs)

    @RPC.export
    def revert_device(self, path, **kwargs):
        if path in self._override_devices:
            raise OverrideError(
                "Cannot revert device {} since global override is set".format(path))
        else:
            self.instances[path].revert_all(**kwargs)

    @RPC.export
    def set_override_on(self, pattern, duration=0.0, failsafe_revert=True, staggered_revert=False):
        self._set_override_on(pattern, duration, failsafe_revert, staggered_revert)

    def _set_override_on(self,
                         pattern,
                         duration=0.0,
                         failsafe_revert=True,
                         staggered_revert=False,
                         from_config_store=False):
        stagger_interval = 0.05     # sec
        pattern = pattern.lower()

        # Add to override patterns set
        self._override_patterns.add(pattern)
        device_topic_actual = self.instances.keys()
        i = 0

        for name in device_topic_actual:
            name = name.lower()
            i += 1
            if fnmatch.fnmatch(name, pattern):
                # If revert to default state is needed
                if failsafe_revert:
                    if staggered_revert:
                        self.core.spawn_later(i*stagger_interval, self.instances[name].revert_all())
                    else:
                        self.core.spawn(self.instances[name].revert_all())
                # Set override
                self._override_devices.add(name)
        # Set timer for interval of override condition
        config_update = self._update_override_interval(duration, pattern)
        if config_update and not from_config_store:
            # Update config store
            patterns = dict()
            for pat in self._override_patterns:
                if self._override_interval_events[pat] is None:
                    patterns[pat] = str(0.0)
                else:
                    evt, end_time = self._override_interval_events[pat]
                    patterns[pat] = utils.format_timestamp(end_time)

            self.vip.config.set("override_patterns", jsonapi.dumps(patterns))

    @RPC.export
    def set_override_off(self, pattern):
        return self._set_override_off(pattern)

    @RPC.export
    def get_override_devices(self):
        return list(self._override_devices)

    @RPC.export
    def clear_overrides(self):
        for pattern, evt in self._override_interval_events.items():
            if evt is not None:
                evt[0].cancel()
        self._override_interval_events.clear()
        self._override_devices.clear()
        self._override_patterns.clear()
        self.vip.config.set("override_patterns", {})

    @RPC.export
    def get_override_patterns(self):
        return list(self._override_patterns)

    def _set_override_off(self, pattern):
        pattern = pattern.lower()
        # If pattern exactly matches
        if pattern in self._override_patterns:
            self._override_patterns.discard(pattern)
            # Cancel any pending override events
            self._cancel_override_events(pattern)
            self._override_devices.clear()
            patterns = dict()
            # Build override devices list again
            for pat in self._override_patterns:
                for device in self.instances:
                    device = device.lower()
                    if fnmatch.fnmatch(device, pat):
                        self._override_devices.add(device)

                if self._override_interval_events[pat] is None:
                    patterns[pat] = str(0.0)
                else:
                    evt, end_time = self._override_interval_events[pat]
                    patterns[pat] = utils.format_timestamp(end_time)

            self.vip.config.set("override_patterns", jsonapi.dumps(patterns))
        else:
            _log.error("Override Pattern did not match!")
            raise OverrideError(
                "Pattern {} does not exist in list of override patterns".format(pattern))

    def _update_override_interval(self, interval, pattern):
        if interval <= 0.0:     # indicative of indefinite duration
            if pattern in self._override_interval_events:
                # If override duration is indifinite, do nothing
                if self._override_interval_events[pattern] is None:
                    return False
                else:
                    # Cancel the old event
                    evt = self._override_interval_events.pop(pattern)
                    evt[0].cancel()
            self._override_interval_events[pattern] = None
            return True
        else:
            override_start = utils.get_aware_utc_now()
            override_end = override_start + timedelta(seconds=interval)
            if pattern in self._override_interval_events:
                evt = self._override_interval_events[pattern]
                # If event is indefinite or greater than new end time, do nothing
                if evt is None or override_end < evt[1]:
                    return False
                else:
                    evt = self._override_interval_events.pop(pattern)
                    evt[0].cancel()
            # Schedule new override event
            event = self.core.schedule(override_end, self._cancel_override, pattern)
            self._override_interval_events[pattern] = (event, override_end)
            return True

    def _cancel_override_events(self, pattern):
        if pattern in self._override_interval_events:
            # Cancel the override cancellation timer event
            evt = self._override_interval_events.pop(pattern, None)
            if evt is not None:
                evt[0].cancel()

    def _cancel_override(self, pattern):
        self._set_override_off(pattern)

    def _update_override_state(self, device, state):
        device = device.lower()

        if state == 'add':
            # If device falls under the existing overriden patterns, then add it to list of overriden devices.
            for pattern in self._override_patterns:
                if fnmatch.fnmatch(device, pattern):
                    self._override_devices.add(device)
                    return
        else:
            # If device is in list of overriden devices, remove it.
            if device in self._override_devices:
                self._override_devices.remove(device)


def main(argv=sys.argv):
    """Main method called to start the agent."""
    utils.vip_main(simulation_driver_agent, identity='simulation.driver', version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
