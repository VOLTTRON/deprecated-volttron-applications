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
import abc
import logging

_log = logging.getLogger(__name__)


class DriverInterfaceError(Exception):
    pass


class BaseRegister(object):
    """
        Abstract class for information about a point on a device.
        Extend this class to support a particular device protocol.

        The member variable ``python_type`` should be overridden with the equivalent
        python type object. Defaults to ``int``. This is used to generate meta data.

        The Driver Agent will use :py:meth:`BaseRegister.get_units` to populate metadata for
        publishing. When instantiating register instances be sure to provide a useful
        string for the units argument.

    :param register_type: (str) Type of the register. Either "bit" or "byte". Usually "byte".
    :param read_only: (bool) Specify if the point can be written to.
    :param point_name: (str) Name of the register.
    :param units: (str) Units of the value of the register.
    :param description: (str) Description of the register.
    """

    def __init__(self, register_type, read_only, pointName, units, description=''):
        self.read_only = read_only
        self.register_type = register_type
        self.point_name = pointName
        self.units = units
        self.description = description
        self.python_type = int

    def get_register_python_type(self):
        return self.python_type

    def get_register_type(self):
        return self.register_type, self.read_only

    def get_units(self):
        return self.units

    def get_description(self):
        return self.description


class BaseInterface(object):
    """
        Abstract class for the interface to a device.

        All interfaces *must* subclass this, by convention creating a subclass named "Interface".

    :param vip: A reference to the SimulationDriverAgent's vip subsystem.
    :param core: A reference to the parent DriverAgent's core subsystem.
    """

    __metaclass__ = abc.ABCMeta

    def __init__(self, vip=None, core=None, **kwargs):
        super(BaseInterface, self).__init__(**kwargs)
        self.vip = vip
        self.core = core
        self.point_map = {}
        self.build_register_map()

    def build_register_map(self):
        self.registers = {
            ('byte', True): [],
            ('byte', False): [],
            ('bit', True): [],
            ('bit', False): []}

    @abc.abstractmethod
    def configure(self, config_dict, registry_config_str):
        """
            Configures the :py:class:`Interface` for the specific instance of a device.

            This method must set up register representations of all points on a device
            by creating instances of :py:class:`BaseRegister` (or a subclass) and adding them
            to the Interface with :py:meth:`BaseInterface.insert_register`.

        :param config_dict: (dict) The "driver_config" section of the driver configuration file.
        :param registry_config_str: (str) The contents of the registry configuration file.
        """
        pass

    def get_register_by_name(self, name):
        """
            Get a register by its point name.

        :param name: (str) Point name of register.
        :return: An instance of BaseRegister
        """
        try:
            return self.point_map[name]
        except KeyError:
            raise DriverInterfaceError("Point not configured on device: "+name)

    def get_register_names(self):
        """
            Get a list of register names.

        :return: List of names
        """
        return self.point_map.keys()

    def get_registers_by_type(self, reg_type, read_only):
        """
            Get a list of registers by type. Useful for an :py:class:`Interface` that needs to categorize
            registers by type when doing a scrape.

        :param reg_type: Register type, either "bit" or "byte".
        :param read_only: (bool) Specify whether the desired registers are read only.
        :return: A list of BaseRegister instances.
        """
        return self.registers[reg_type, read_only]

    def insert_register(self, register):
        """
            Insert a register into the :py:class:`Interface`.

        :param register: BaseRegister to add to the interface.
        """
        register_point = register.point_name
        self.point_map[register_point] = register

        register_type = register.get_register_type()
        self.registers[register_type].append(register)

    @abc.abstractmethod
    def get_point(self, point_name, **kwargs):
        """
            Get the current value for the point name given.

        :param point_name: (str) Name of the point to retrieve.
        :param kwargs: Any interface-specific parameters.
        :return: Point value
        """

    @abc.abstractmethod
    def set_point(self, point_name, value, **kwargs):
        """
            Set the current value for the point name given.

            Implementations of this method should make a reasonable effort to return
            the actual value the point was set to.
            Some protocols/devices make this difficult (I'm looking at you, BACnet).
            In these cases it is acceptable to return the value that was requested
            if no error occurs.

        :param point_name: (str) Name of the point to retrieve.
        :param value: Value to set the point to.
        :param kwargs: Any interface-specific parameters.
        :return: Actual point value set.
        """

    @abc.abstractmethod
    def scrape_all(self):
        """
            Called by the DriverAgent to get the device's current state for publication.

        :return: (dict) Point names to values for device.
        """

    @abc.abstractmethod
    def revert_all(self, **kwargs):
        """
            Revert the entire device to its default state.

        :param kwargs: Any interface-specific parameters.
        """

    @abc.abstractmethod
    def revert_point(self, point_name, **kwargs):
        """
            Revert a point to its default state.

        :param point_name: (str) Name of the point to revert.
        :param kwargs: Any interface-specific parameters.
        """

    def get_multiple_points(self, path, point_names, **kwargs):
        """
            Read multiple points from the interface.

        :param path: (str) Device path
        :param point_names: (list of str) Names of points to retrieve
        :param kwargs: Any interface-specific parameters
        :returns: Tuple of dictionaries containing results and errors
        """
        results = {}
        errors = {}
        for point_name in point_names:
            return_key = path + '/' + point_name
            try:
                value = self.get_point(point_name, **kwargs)
                results[return_key] = value
            except Exception as e:
                errors[return_key] = repr(e)
        return results, errors

    def set_multiple_points(self, path, point_names_values, **kwargs):
        """
            Set multiple points on the interface.

        :param path: (str) Device path
        :param point_names_values: Point names and values to be set -- [(str, k)] where k is the new value
        :param kwargs: Any interface-specific parameters
        :returns: Dictionary of points with any exceptions raised
        """
        results = {}
        for point_name, value in point_names_values:
            try:
                self.set_point(point_name, value, **kwargs)
            except Exception as e:
                results[path + '/' + point_name] = repr(e)
        return results


class RevertTracker(object):
    """A helper class for tracking the state of writable points on a device."""

    def __init__(self):
        self.defaults = {}
        self.clean_values = {}
        self.dirty_points = set()

    def update_clean_values(self, points):
        """
            Update the state of all clean point values for a device.

            If a point is marked dirty, it will not be updated.

        :param points: dict of point names to values.
        """
        clean_values = {}
        for k, v in points.iteritems():
            if k not in self.dirty_points and k not in self.defaults:
                clean_values[k] = v
        self.clean_values.update(clean_values)

    def set_default(self, point, value):
        """
            Set the value to revert a point to. Overrides any clean value detected.

        :param point: (str) name of point to set.
        :param value: value to set the point to.
        """
        self.defaults[point] = value

    def get_revert_value(self, point):
        """
            Return the clean value for a point if no default is set, otherwise return the default value.

            If no default value is set and no clean values have been submitted,
            raise, :py:class:`DriverInterfaceError`.

        :param point: (str) Name of point to get.
        :return: Value to revert to.
        """
        if point in self.defaults:
            return self.defaults[point]
        if point not in self.clean_values:
            raise DriverInterfaceError("Nothing to revert to for {}".format(point))
        return self.clean_values[point]

    def clear_dirty_point(self, point):
        """
            Clear the dirty flag on a point.

        :param point: (str) Name of point for which the flag should be cleared.
        """
        self.dirty_points.discard(point)

    def mark_dirty_point(self, point):
        """
            Set the dirty flag on a point. Ignores points that have a default value.

        :param point: (str) Name of point for which the flag should be marked dirty.
        """
        if point not in self.defaults:
            self.dirty_points.add(point)

    def get_all_revert_values(self):
        """
            Returns a dict of points to revert values.

            If no default value is set, use the clean value, otherwise return the default value.

            If no default value is set, and no clean value has been submitted,
            a point value will be an instance of :py:class:`DriverInterfaceError`.

        :return: (dict) Values to revert to.
        """
        results = {}
        for point in self.dirty_points.union(self.defaults):
            try:
                results[point] = self.get_revert_value(point)
            except DriverInterfaceError:
                results[point] = DriverInterfaceError()
        return results


class BasicRevert(object):
    """
        A mixin that implements the :py:meth:`BaseInterface.revert_all`
        and :py:meth:`BaseInterface.revert_point` methods on an
        :py:class:`Interface`.

        It works by tracking changes to all writable points until a `set_point` call
        is made. When this happens, the point is marked dirty and the previous
        value is remembered. When a point is reverted via either a `revert_all`
        or `revert_point` call, the dirty values are set back to clean values
        using the :py:meth:`BasicRevert._set_point` method.

        As it must hook into the setting and scraping of points, it implements the
        :py:meth:`BaseInterface.scrape_all` and :py:meth:`BaseInterface.set_point`
        methods. It then adds :py:meth:`BasicRevert._set_point` and
        :py:meth:`BasicRevert._scrape_all` to the abstract interface. An existing
        interface that wants to use this class can simply mix it in and
        rename its `set_point` and `scrape_all` methods to `_set_point` and
        `_scrape_all` respectively.

        A :py:class:`BaseInterface` may also override the detected clean value with
        its own value to revert to by calling :py:meth:`BasicRevert.set_default`.
        While default values can be set at any time, they
        should be set in the :py:meth:`BaseInterface.configure` call.
    """

    __metaclass__ = abc.ABCMeta

    def __init__(self, **kwargs):
        super(BasicRevert, self).__init__(**kwargs)
        self._tracker = RevertTracker()

    def _update_clean_values(self, points):
        self._tracker.update_clean_values(points)

    def set_default(self, point, value):
        """
            Set the value to revert a point to.

        :param point: (str) name of point to set.
        :param value: value to set the point to.
        """
        self._tracker.set_default(point, value)

    def set_point(self, point_name, value):
        """
            Implementation of :py:meth:`BaseInterface.set_point`

            Passes arguments through to :py:meth:`BasicRevert._set_point`
        """
        result = self._set_point(point_name, value)
        self._tracker.mark_dirty_point(point_name)
        return result

    def scrape_all(self):
        """Implementation of :py:meth:`BaseInterface.scrape_all`"""
        sim_time = self.get_simulated_time()
        result = self._scrape_all(sim_time)
        self._update_clean_values(result)
        return result

    def get_simulated_time(self):
        """Return the current simulated time, as furnished by the SimulatedClockAgent."""
        try:
            sim_time = self.vip.rpc.call('simulationclock', 'get_time').get(timeout=5)
        except Exception, err:
            _log.warning('No simulated time agent or no simulation is in progress')
            sim_time = None
        return sim_time

    @abc.abstractmethod
    def _set_point(self, point_name, value):
        """
            Set the current value for the named point.

            If using this mixin, you must override this method instead of :py:meth:`BaseInterface.set_point`.
            Otherwise the purpose is exactly the same.

            Implementations of this method should make a reasonable effort to return
            the actual value the point was set to.
            Some protocols/devices make this difficult (I'm looking at you, BACnet).
            In these cases it is acceptable to return the value that was requested
            if no error occurs.

        :param point_name: (str) Name of the point to retrieve.
        :param value: Value to set the point to.
        :return: Actual point value set.
        """

    @abc.abstractmethod
    def _scrape_all(self, timestamp):
        """
            Get the current state of a device for publication.

            If using this mixin, you must override this method instead of :py:meth:`BaseInterface.scrape_all`.
            Otherwise the purpose is exactly the same.

        :return: (dict) Point names to values for device.
        """

    def revert_all(self):
        """
            Implementation of :py:meth:`BaseInterface.revert_all`. Revert the device to its default state.

            Calls :py:meth:`BasicRevert._set_point` with `point_name` and the revert value,
            reverting each of the device's writable points.
        """
        points = self._tracker.get_all_revert_values()
        for point_name, value in points.iteritems():
            if not isinstance(value, DriverInterfaceError):
                try:
                    self._set_point(point_name, value)
                    self._tracker.clear_dirty_point(point_name)
                except Exception as e:
                    _log.warning("Error while reverting point {}: {}".format(point_name, str(e)))

    def revert_point(self, point_name):
        """
            Implementation of :py:meth:`BaseInterface.revert_point`. Revert a point to its default state.

            Calls :py:meth:`BasicRevert._set_point` with `point_name` and the revert value.

        :param point_name: (str) Name of the point to revert.
        """
        try:
            value = self._tracker.get_revert_value(point_name)
        except DriverInterfaceError:
            return
        _log.debug("Reverting {} to {}".format(point_name, value))
        self._set_point(point_name, value)
        self._tracker.clear_dirty_point(point_name)
