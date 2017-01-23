import sys
import logging
from math import ceil
from datetime import timedelta as td, datetime as dt
from copy import deepcopy
import pkgutil
import os
from dateutil.parser import parse

import numpy as np
from scipy.stats import norm
from scipy.signal import butter, filtfilt, argrelextrema

from volttron.platform.messaging import topics
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core

plot_loader = pkgutil.find_loader('matplotlib')
plotter_found = plot_loader is not None
if plotter_found:
    import matplotlib.pyplot as plt

cutoff = 300
fs = 3000

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = "0.2.0"

__author1__ = 'Woohyun Kim <woohyun.kim@pnnl.gov>'
__author2__ = 'Robert Lutes <robert.lutes@pnnl.gov>'
__copyright__ = 'Copyright (c) 2016, Battelle Memorial Institute'
__license__ = 'FreeBSD'
DATE_FORMAT = '%m-%d-%y %H:%M'


def butter_lowpass(cutoff, fs, order=5):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return b, a

def butter_lowpass_filtfilt(data, cutoff, fs, order=5):
    b, a = butter_lowpass(cutoff, fs, order=order)
    y = filtfilt(b, a, data)
    return y

def find_intersections(m1, m2, std1, std2):
    a = 1./(2.*std1**2) - 1./(2.*std2**2)
    b = m2/(std2**2) - m1/(std1**2)
    c = m1**2 /(2*std1**2) - m2**2 / (2*std2**2) - np.log(std2/std1)
    return np.roots([a, b, c])

def locate_min_max(timeseries):
    try:
        filtered_timeseries = butter_lowpass_filtfilt(timeseries, cutoff, fs)
        maximums = detect_peaks(timeseries, mpd=1, valley=False)
        minimums = detect_peaks(timeseries, mpd=1, valley=True)
    except:
        filtered_timeseries = np.empty(0)
        maximums = np.empty(0)
        minimums = np.empty(0)
    return minimums, maximums, filtered_timeseries

def align_pv(zone_temperature_array, peak_ind, val_ind, dtime):
    '''align_pv takes the indices of peaks (peak_ind) and indices of

    valleys (val_ind) and ensures that there is only one valley
    in-between two consecutive peaks and only one peak between two
    consecutive valleys.  If there are two or more peaks between
    valleys the largest value is kept.  If there are two or more
    valleys between two peaks then the smallest value is kept.
    '''
    try:
        reckon = 0
        aligned = False
        find_peak = True if peak_ind[0] < val_ind[0] else False
        begin = 0
        while not aligned:
            if find_peak:
                while peak_ind[reckon+1] < val_ind[reckon+begin]:
                    if zone_temperature_array[peak_ind[reckon]] > zone_temperature_array[peak_ind[reckon+1]]:
                        peak_ind = np.delete(peak_ind, reckon+1)
                    else:
                        peak_ind = np.delete(peak_ind, reckon)
                if (dtime[val_ind[reckon+begin]] - dtime[peak_ind[reckon]]) <= td(minutes=5):
                    val_ind = np.delete(val_ind, reckon+begin)
                    peak_ind = np.delete(peak_ind, reckon+1)
                else:
                    find_peak = False
                    begin += 1
                    if begin > 1:
                        begin = 0
                        reckon += 1
            else:
                while val_ind[reckon + 1] < peak_ind[reckon+begin]:
                    if zone_temperature_array[val_ind[reckon]] > zone_temperature_array[val_ind[reckon+1]]:
                        val_ind = np.delete(val_ind, reckon)
                    else:
                        val_ind = np.delete(val_ind, reckon+1)
                if (dtime[peak_ind[reckon+begin]] - dtime[val_ind[reckon]]) <= td(minutes=5):
                    val_ind = np.delete(val_ind, reckon+1)
                    peak_ind = np.delete(peak_ind, reckon+begin)
                else:
                    find_peak = True
                    begin += 1
                    if begin > 1:
                        begin = 0
                        reckon += 1
            if (reckon+1) == min(val_ind.size, peak_ind.size):
                aligned = True
        if peak_ind.size > val_ind.size:
            peak_ind = np.resize(peak_ind, val_ind.size)
        elif val_ind.size > peak_ind.size:
            val_ind = np.resize(val_ind, peak_ind.size)
        return peak_ind, val_ind
    except:
        return np.empty(0), np.empty(0)



def detect_peaks(data, mph=None, threshold=0, mpd=1, edge='rising',
                 kpsh=False, valley=False, ax=None):
    '''
    Detect peaks in data based on their amplitude and other features.
    Original source for detect_peaks function can be obtained at:
    https://github.com/demotu/BMC/blob/master/functions/detect_peaks.py

    __author__ = "Marcos Duarte, https://github.com/demotu/BMC"
    __version__ = "1.0.4"
    __license__ = "MIT"

    Copyright (c) 2013 Marcos Duarte
    Permission is hereby granted, free of charge, to any person
    obtaining a copy of this software and associated documentation
    files (the "Software"), to deal in the Software without
    restriction, including without limitation the rights to use,
    copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following
    conditions:

    The above copyright notice and this permission notice shall be
    included in all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
    EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
    OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
    NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
    HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
    WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
    OTHER DEALINGS IN THE SOFTWARE.
    '''
    data = np.array(data)
    if data.size < 3:
        return np.array([], dtype=int)
    if valley:
        data = -data

    # find indices of all peaks
    dx = data[1:] - data[:-1]
    # handle NaN's
    indnan = np.where(np.isnan(data))[0]
    if indnan.size:
        data[indnan] = np.inf
        dx[np.where(np.isnan(dx))[0]] = np.inf
    ine, ire, ife = np.array([[], [], []], dtype=int)

    if not edge:
        ine = np.where((np.hstack((dx, 0)) < 0) & (np.hstack((0, dx)) > 0))[0]
    else:
        if edge.lower() in ['rising', 'both']:
            ire = np.where((np.hstack((dx, 0)) <= 0) & (np.hstack((0, dx)) > 0))[0]
        if edge.lower() in ['falling', 'both']:
            ife = np.where((np.hstack((dx, 0)) < 0) & (np.hstack((0, dx)) >= 0))[0]
    ind = np.unique(np.hstack((ine, ire, ife)))

    # handle NaN's
    if ind.size and indnan.size:
        # NaN's and values close to NaN's cannot be peaks
        ind = ind[np.in1d(ind, np.unique(np.hstack((indnan, indnan-1, indnan+1))), invert=True)]
    # first and last values of data cannot be peaks

    if ind.size and ind[0] == 0:
        ind = ind[1:]
    if ind.size and ind[-1] == data.size-1:
        ind = ind[:-1]
    # remove peaks < minimum peak height
    if ind.size and mph is not None:
        ind = ind[data[ind] > mph[ind]]
    # remove peaks - neighbors < threshold
    if ind.size and threshold > 0:
        dx = np.min(np.vstack([data[ind]-data[ind-1], data[ind]-data[ind+1]]), axis=0)
        ind = np.delete(ind, np.where(dx < threshold)[0])
    # detect small peaks closer than minimum peak distance
    if ind.size and mpd > 1:
        ind = ind[np.argsort(data[ind])][::-1]  # sort ind by peak height
        idel = np.zeros(ind.size, dtype=bool)
        for i in range(ind.size):
            if not idel[i]:
                # keep peaks with the same height if kpsh is True
                idel = idel | (ind >= ind[i] - mpd) & (ind <= ind[i] + mpd) & (data[ind[i]] > data[ind] if kpsh else True)
                idel[i] = 0  # Keep current peak
        # remove the small peaks and sort back
        # the indices by their occurrence
        ind = np.sort(ind[~idel])
    return ind


class SetPointDetector(Agent):
    def __init__(self, config_path, **kwargs):
        super(SetPointDetector, self).__init__(**kwargs)
        config = utils.load_config(config_path)

        self.fanstatus_name = config.get('FanStatus', 'FanStatus')
        self.zone_temperature = config.get('ZoneTemperature', 'ZoneTemperature')
        self.device_topic = topics.DEVICES_VALUE(campus=config.get('campus', ''),
                                                 building=config.get('building', ''),
                                                 unit=config.get('unit', ''),
                                                 path='',
                                                 point='all')

        required_data = [self.fanstatus_name, self.zone_temperature]
        self.minimum_data_count = config.get('minimum_data_count', 5)
        self.area_distribution_threshold = config.get('area_distribution_threshold', 0.1)
        self.debug = config.get('debug_flag', False)
        self.debug_directory = config.get('debug_directory')
        self.zone_temperature_array = np.empty(0)
        self.fan_status_arr = np.empty(0)
        self.timestamp_array = np.empty(0)
        self.current_stpt_array = np.empty(0)
        self.current_timestamp_array = np.empty(0)
        self.inconsistent_data_flag = 0
        self.number = 0
        self.startup = True
        self.available = []

    def initialize(self):
        self.zone_temperature_array = np.empty(0)
        self.fan_status_arr = np.empty(0)
        self.timestamp_array = np.empty(0)
        self.inconsistent_data_flag = 0
        self.number = 0
        self.startup = True
        self.available = []

    @Core.receiver('onstart')
    def starting_base(self, sender, **kwargs):
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=self.device_topic,
                                  callback=self.on_new_data)

    def check_data_requirements(self, available):
        """Minimum data requirement is zone temperature and supply fan status.
        """
        avail_required_data = [item for item in required_data if item in available]

        if self.zone_temperature in avail_required_data and self.fanstatus_name in avail_required_data:
            self.available = available
            return True
        return False

    def on_new_data(self, peer, sender, bus, topic, headers, message):
        '''Subscribe to device data on the message bus.'''
        _log.info('RECEIVING NEW DATA')
        data = message[0]
        available = data.keys()
        if not self.check_data_requirements(available):
            _log.info('Required data for diagnostic is not available or '
                      'configured names do not match published names!')
            return
        self.startup = False
        for item in self.available:
            if item not in available:
                self.inconsistent_data_flag += 1
                _log.info('Previously available data is missing '
                          'from device publish')
                if self.inconsistent_data_flag > 5:
                    _log.info('data fields available for device are '
                              'not consistent. Reinitializing diagnostic.')
                    self.initialize()
                return
        self.inconsistent_data_flag = 0
        timestamp = parse(headers['Date'])
        fanstat_value = int(data[self.fanstatus_name])
        if not fanstat_value:
            _log.info('Supply fan is off.  Data for {} '
                      'will not used'.format(str(timestamp)))
            return
        _log.info('Checking timeseries data {}'.format(timestamp))
        zone_temperature_val = float(data.get(self.zone_temperature))
        self.detect_stpt_main(zone_temperature_val, timestamp)
        return

    def check_run_status(self, current_time):
        if self.timestamp_array.size and self.timestamp_array[0].date() != current_time.date():
            return True
        return False

    def detect_stpt_main(self, zone_temp, current_time):
        try:
            if self.check_run_status(current_time):
                valleys, peaks, filtered_timeseries = locate_min_max(self.zone_temperature_array)
                if np.prod(peaks.shape) < self.minimum_data_count or np.prod(valleys.shape) < self.minimum_data_count:
                    _log.debug('Set point detection is inconclusive.  Not enough data.')
                    self.initialize()
                    return
                peak_array, valley_array = align_pv(filtered_timeseries, peaks, valleys, self.timestamp_array)
                if (np.prod(peak_array.shape) < self.minimum_data_count or
                        np.prod(valley_array.shape) < self.minimum_data_count):
                    _log.debug('Set point detection is inconclusive.  Not enough data.')
                    self.initialize()
                    return
                self.current_stpt_array, self.current_timestamp_array = self.create_setpoint_array(deepcopy(peak_array), deepcopy(valley_array))
                # do domething with this
                setpoint_array = self.check_timeseries_grouping()
                self.initialize()
        finally:
            self.timestamp_array = np.append(self.timestamp_array, current_time)
            self.zone_temperature_array = np.append(self.zone_temperature_array, zone_temp)

    def check_timeseries_grouping(self):
        incrementer = 0
        index = 0
        set_points = []
        number_groups = int(ceil(self.current_stpt_array.size)) - self.minimum_data_count  if self.current_stpt_array.size > self.minimum_data_count else 1
        if number_groups == 1:
            current_stpt = [self.timestamp_array[0], self.timestamp_array[-1], np.average(self.current_stpt_array)]
            set_points.append(current_stpt)
        else:
            for grouper in range(number_groups):
                current = self.current_stpt_array[(0+incrementer):(self.minimum_data_count+incrementer+index)]
                next_group = self.current_stpt_array[(1+grouper):(self.minimum_data_count+grouper+1)]
                _log.info('Current {}'.format(current))
                _log.info('Current {}'.format(next_group))
        if np.std(next_group) < 0.4:
            area = self.determine_distribution_area(current, next_group)
            _log.info('distribution area {}'.format(area))
            if area < self.area_distribution_threshold:
                incrementer += 1
                current_stpt = [self.timestamp_array[0+incrementer],
                                self.timestamp_array[self.minimum_data_count+incrementer+index],
                                np.average(current)]
                if np.std(current_stpt) < 0.4:
                    set_points.append(current_stpt)
                if grouper < number_groups - 1:
                    last_stpt = [self.timestamp_array[1+grouper],
                                 self.timestamp_array[self.minimum_data_count+grouper+1],
                                 np.average(next_group)]
            else:
                index += 1
                if grouper == number_groups - 1:
                    current = self.current_stpt_array[(0+incrementer):(self.minimum_data_count+grouper+1)]
                    current_stpt = [self.timestamp_array[0+incrementer],
                                    self.timestamp_array[self.minimum_data_count+grouper+1],
                                    np.average(current)]
            if np.std(current_stpt) < 0.4:
                set_points.append(current_stpt)
        _log.debug('SETPOINT ARRAY: {}'.format(set_points))
        if self.debug and plotter_found:
            plt.close()
        return set_points

    def determine_distribution_area(self, current_ts, next_ts):

        def calculate_area():
            lower = min(norm.cdf(min(intersections), m1, std1), norm.cdf(min(intersections), m2, std2))
            mid_calc1 = 1 - norm.cdf(min(intersections), m1, std1) - (1-norm.cdf(max(intersections), m1, std1))
            mid_calc2 = 1 - norm.cdf(min(intersections), m2, std2) - (1 - norm.cdf(max(intersections), m2, std2))
            mid = min(mid_calc1, mid_calc2)
            end = min(1 - norm.cdf(max(intersections), m1, std1), 1 - norm.cdf(max(intersections), m2, std2))
            return lower + mid + end

        if np.average(current_ts) > np.average(next_ts):
            current_max = True
            m1 = np.average(current_ts)
            m2 = np.average(next_ts)
            std1 = np.std(current_ts)
            std2 = np.std(next_ts)
        else:
            current_max = False
            m2 = np.average(current_ts)
            m1 = np.average(next_ts)
            std2 = np.std(current_ts)
            std1 = np.std(next_ts)
        intersections = find_intersections(m1, m2, std1, std2)
        area = calculate_area()
        if self.debug and plotter_found and self.debug_directory is not None:
            self.plot_dist_area(m1, std1, m2, std2, self.timestamp_array[0].date(), area, current_max)
        return area

    def create_setpoint_array(self, pcopy, vcopy):
        peak_ts = zip(self.timestamp_array[pcopy], self.zone_temperature_array[pcopy])
        valley_ts = zip(self.timestamp_array[vcopy], self.zone_temperature_array[vcopy])
        remove_temp1 = [(x[0], x[1]) for x, y in zip(peak_ts, valley_ts) if x[1] >= y[1] + 0.3]
        remove_temp2 = [(y[0], y[1]) for x, y in zip(peak_ts, valley_ts) if x[1] >= y[1] + 0.3]

        peak_temp = [row[1] for row in remove_temp1]
        valley_temp = [row[1] for row in remove_temp2]

        peak_timestamp = [row[0] for row in remove_temp1]
        valley_timestamp = [row[0] for row in remove_temp2]
        if peak_timestamp[0] < valley_timestamp[0]:
            timestamp_array = np.array(peak_timestamp) + (np.array(valley_timestamp) - np.array(peak_timestamp))/2
        else:
            timestamp_array = np.array(valley_timestamp) + (np.array(peak_timestamp) - np.array(valley_timestamp))/2
        return (np.array(peak_temp) + np.array(valley_temp)) / 2, timestamp_array

    def plot_dist_area(self, m1, std1, m2, std2, _date, area, current_max):
        directory = self.debug_directory + '{}'.format(_date)
        if not os.path.exists(directory):
            os.makedirs(directory)
        self.number += 1
        fig = plt.figure()
        fig.text(0, 0, 'area: {}    std1: {}    std2: {}    current_max: {}'.format(area, std1, std2, current_max))
        x = np.linspace(60.0, 80.-0, 1000)
        plt.plot(x, norm.pdf(x, m1, std1))
        plt.plot(x, norm.pdf(x, m2, std2))
        mover = (m2, m1) if m1 > m2 else (m1, m2)

        axes = plt.gca()
        #axes.set_ylim([0,0.5])
        axes.set_xlim([mover[0]-8, mover[1]+8])

        plt.ylabel('Probability', fontsize=14, fontweight='bold')
        plt.xlabel('Temperature[F]', fontsize=14, fontweight='bold')
        file_name = directory + '/distribution_curve{}'.format(self.number)
        plt.savefig(file_name)
        plt.close()


def main(argv=sys.argv):
    '''Main method called to start the agent.'''
    utils.vip_main(SetPointDetector)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass


