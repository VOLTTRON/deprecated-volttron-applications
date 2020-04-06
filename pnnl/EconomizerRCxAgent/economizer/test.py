"""
File used to unit test EconimizerRC
"""
import unittest
import os
import sys
from datetime import timedelta as td
sys.path.append("..")
from .diagnostics.TemperatureSensor import TemperatureSensor
from datetime import datetime


class TestDiagnosticsTempSensor(unittest.TestCase):
    """
    Contains all the tests for Temperature Diagnostic
    """

    def test_temp_sensor_dx_creation(self):
        """test the  creation of temp sensor diagnostic class"""

        temp_sensor = TemperatureSensor()
        if isinstance(temp_sensor, TemperatureSensor):
            assert True
        else:
            assert False

    def test_temp_sensor_dx_set_values(self):
        """test the  temp sensor set values method"""
        temp_sensor = TemperatureSensor()
        data_window = td(minutes=1)
        temp_sensor.set_class_values(data_window, 1, 4.0, 0, 5.0, 90.0)
        assert temp_sensor.data_window == td(minutes=1)
        assert temp_sensor.no_required_data == 1
        assert temp_sensor.oat_mat_check == 5.0

    def test_temp_sensor_algorithm(self):
        """test the  temp sensor algorithm"""
        temp_sensor = TemperatureSensor()
        data_window = td(minutes=1)
        temp_sensor.set_class_values(data_window, 1, 4.0, 0, 5.0, 90.0)
        oat = 50
        rat = 50
        mat = 50
        oad = 50
        cur_time = datetime.fromtimestamp(1036)
        sensor_problem = temp_sensor.temperature_algorithm(oat, rat, mat, oad, cur_time)
        assert sensor_problem is None
