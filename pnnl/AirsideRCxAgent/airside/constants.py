FAN_OFF = -99.3
DUCT_STC_RCX = "Duct Static Pressure Set Point Control Loop Dx"
DUCT_STC_RCX1 = "Low Duct Static Pressure Dx"
DUCT_STC_RCX2 = "High Duct Static Pressure Dx"
DX = "/diagnostic message"
SA_TEMP_RCX = "Supply-air Temperature Set Point Control Loop Dx"
SA_TEMP_RCX1 = "Low Supply-air Temperature Dx"
SA_TEMP_RCX2 = "High Supply-air Temperature Dx"
DX_LIST = [DUCT_STC_RCX, DUCT_STC_RCX1, DUCT_STC_RCX2, SA_TEMP_RCX, SA_TEMP_RCX1, SA_TEMP_RCX2]

def table_log_format(name, timestamp, data):
    """ Return a formatted string for use in the log"""
    return str(str(name) + '&' + str(timestamp) + '->[' + str(data) + ']')