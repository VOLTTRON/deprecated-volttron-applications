
ECON1 = "Temperature Sensor Dx"
ECON2 = "Not Economizing When Unit Should Dx"
ECON3 = "Economizing When Unit Should Not Dx"
ECON4 = "Excess Outdoor-air Intake Dx"
ECON5 = "Insufficient Outdoor-air Intake Dx"
DX = "/diagnostic message"
EI = "/energy impact"

DX_LIST = [ECON1, ECON2, ECON3, ECON4, ECON5]

FAN_OFF = -99.3
OAF = -89.2
OAT_LIMIT = -79.2
RAT_LIMIT = -69.2
MAT_LIMIT = -59.2
TEMP_SENSOR = -49.2


def table_log_format(name, timestamp, data):
    """ Return a formatted string for use in the log"""
    return str(str(name) + '&' + str(timestamp) + '->[' + str(data) + ']')
