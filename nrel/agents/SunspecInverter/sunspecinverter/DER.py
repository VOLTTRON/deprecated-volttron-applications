import xmltodict
from helper import *
from Device import Inverter
from utilities import *
import logging

from volttron.platform.agent import utils

DEBUG = True
xml_path = get_xml_path()
utils.setup_logging()
_log = logging.getLogger(__name__)

class DERProgramList(object):
    '''
	Extracts and creates the DER Programs 
    '''
    def __init__(self, href, inverter):
        if DEBUG:
	    self.file = os.path.join(xml_path,"DERProgramList.xml")
            self.response = xmltodict.parse(open(self.file).read())
        else:
            self.response = GET(href)
        self.href = href
        Pgms = self.response['DERProgramList']['DERProgram']
        self.pollRate = self.response['DERProgramList']['@pollRate']
        self.Pgms = []
        self.Pgm_mRIDs = []
        for pgm in Pgms:
            self.Pgm_mRIDs = pgm['mRID']
            self.Pgms.append(DERProgram(pgm, inverter))

    def poll(self):
        changed, res = check_content(self, 'DERProgramList', 'DERProgram')
        if changed:
            self.response = res
            newPgm_mRIDS = [x['mRID'] for x in newPgmList]
            temp = set(newPgm_mRIDS).symmetric_difference(set(Pgm_mRIDs))
            if len(temp>0):
                x.add([l for l in z.difference(x)])
                self.Pgm_mRIDs.remove([l for l in temp.difference(set(newPgm_mRIDS))])
                self.Pgms.remove([self.get_pgm_by_mRID(l, self.Pgms) for l in temp.difference(set(newPgm_mRIDS))])

                self.Pgm_mRIDs.append([l for l in temp.difference(set(Pgm_mRIDs))])
                self.Pgms.append([DERProgram(self.get_pgm_by_mRID(l, newPgmList)) for l in temp.difference(set(Pgm_mRIDs))])
                
            for pgm in self.Pgms:
                pgm.set_poll_values(newPgmList)

    def get_pgm_by_mRID(self, id, pgms):
        return [p for p in pgms if p.mRID == id]


class DERProgram(DERProgramList):
    def __init__(self, Program, inverter):
        self.Program = Program
        self.mRID = Program['mRID']
        self.set_poll_values(Program)
        self.inverter = inverter
	self.link = Program['@href']
	self.DefaultDERControl = DefaultDERControl(Program['DefaultDERControlLink']['@href'], self.inverter)
    	self.ActiveeDERControlListLink = Program['ActiveDERControlListLink']['@href']
    	self.DERControlList = DERControlList(Program['DERControlListLink']['@href'], self.inverter)
    	self.DERCurveList = DERCurveList(Program['DERCurveListLink']['@href'], self.inverter)

    def set_poll_values(self, d):
        if d != self.Program:
            self.Program = d
            self.DefaultDERControl.poll(d['DefaultDERControlLink']['@href'], self.inverter)
            self.ActiveeDERControlListLink = d['ActiveDERControlListLink']['@href']
            self.DERControlList.poll(d['DERControlListLink']['@href'], self.inverter)
            self.DERCurveList.poll(d['DERCurveListLink']['@href'], self.inverter)
            self.primacy = d['primacy']
            self.description = d['description']
        else:
            _log.warning("DER Pgm polled values din't change")

class DefaultDERControl(object):
    def __init__(self, href, inverter):
        '''
        For curves set these values to form the default curves
        For controls set these for now and use them whenever there is no scheduled DER control
        '''
        if DEBUG:
            self.file = os.path.join(xml_path, "DefaultDERControl.xml")
            self.response = xmltodict.parse(open(self.file).read())
        else:
            self.response = GET(href)
	self.response = self.response["DefaultDERControl"]
        self.href = href
        self.description = self.response['description'] 
        self.mRID = self.response['mRID']
        self.DefCtlBase = DERControlBase(inverter, self.response['DERControlBase'])

    def poll(self, href):
        res, changed = check_content(self.__dict__, "DefaultDERControl")
        if changed:
            self.response = res
            self.href = href
            self.description = res['description']
            self.DefCtlBase.refresh(res['DERControlBase'])
        else:
            _log.warning("DefDER values din't change")
       
class DERControlBase(object):
    '''
	Implements the DER controls

        Attr:   
                setGradW, opModEnergize, opModFixedPF, opModMaxLimW, opModFixedW 
        '''
    def __init__(self, inverter, base=None):
        for key, value in base.items():
            setattr(DERControlBase, key, value)
	self.base = base
        self.inverter = inverter
        if base == None:
            self.opModMaxLimW = None
            self.opModFixedPF = None
            self.opModFixedW = None
            self.opModEnergize = None
            self.setGradW = None
        else:
            if inverter is not None:
                self.set_controls(base) 

    def set_controls(self, base):
	for k,v in base.items():
	    if k == 'setGradW':
		self.GradW()
	    elif k == 'opModEnergize':
		self.Energize(),
	    elif k == 'opModFixedW':
		self.FixedW()
	    elif k == 'opModFixedPF':
		self.FixedPF()
	    elif k == 'opModMaxLimW':
		self.MaxLimW()
	
   
    def refresh(self, newControls):
        for key, value in newControls.items():
            setattr(DERControlBase, key, value)

    def MaxLimW(self):
        '''
        The opModMaxLimW function specifies a  limit of maximum watt setting.
        '''
        self.opModMaxLimW = self.inverter.write_point('settings', 'WMax', self.base['opModMaxLimW'])
        
    def FixedPF(self):
        '''
        The opModFixedPF function specifies a requested fixed Power Factor (PF) setting.
        '''
        self.opModFixedPF = self.inverter.write_point('controls', 'OutPFSet', self.base['opModFixedPF'])
        
    def FixedW(self):
        '''
        Sets the maximum active power generation level as a percentage of set capacity
        '''  
        self.opModFixedW = self.inverter.write_point('settings', 'VMax' , self.base['opModFixedW'])
        
    def Energize(self):
	connect=self.base['opModEnergize']
        if connect:
            self.opModEnergize = self.inverter.write_point('controls','Conn', 'CONNECT')
        else:
            self.opModEnergize = self.inverter.write_point('controls', 'Conn', 'DISCONNECT')
        
    def GradW(self):
        '''
        Set default rate of change (ramp rate) of active power output
        '''
        self.setGradW = self.inverter.write_point('settings', 'WGra' , self.base['setGradW'])    
        
class DERControlList(object):
    def __init__(self, href, inverter):
        if DEBUG:
	    self.file = os.path.join(xml_path,'DERControlList.xml')
            self.DERControlList = xmltodict.parse(open(self.file).read())
        else:
            self.DERControlList = GET(href)
        self.href = href
        self.DERControlList = self.DERControlList['DERControlList']['DERControl']
        self.DERControls = []
        self.Ctl_mRIDS = []
        self.create_controls(inverter)

    def create_controls(self, inverter):
	self.DERControls.append(DERControl(self.DERControlList, inverter))
	self.Ctl_mRIDS.append(self.DERControlList['mRID'])

    def poll(self):
        changed, res = check_content(self, 'DERControlList', 'DERControl')
        if changed:
            self.response = res
            newCtl_mRIDS = [x['mRID'] for x in newCtlList]
            temp = set(newCur_mRIDS).symmetric_difference(set(Ctl_mRIDS))
            if len(temp>0):
                self.Ctl_mRIDS.remove([l for l in temp.difference(set(newCtl_mRIDS))])
                self.DERCurves.remove([self.get_cur_by_mRID(l, self.DERCurves) for l in temp.difference(set(newCtl_mRIDS))])

                self.Ctl_mRIDS.append([l for l in temp.difference(set(Ctl_mRIDS))])
                self.DERCurves.append([DERProgram(self.get_cur_by_mRID(l, newCtl_mRIDS)) for l in temp.difference(set(Ctl_mRIDS))])
                
            for ctl in self.DERControls:
                cur.set_poll_values(newCtlList)

    def get_cur_by_mRID(self, id, ctls):
        return [p for p in ctls if p.mRID == id] 

class EventStatus(object):
    def __init__(self, currentStatus, dateTime, potentiallySuperseded, potentiallySupersededTime = None, reason = None ):
        self.currentStatus = currentStatus
        self.dateTime = dateTime
        self.potentiallySuperseded = potentiallySuperseded
        self.potentiallySupersededTime = potentiallySupersededTime
        self.reason = reason

class DERControl(object):
    def __init__(self, ctl, inverter):    
        self.DERCtl = ctl
        self.mRID = self.DERCtl['mRID']
        self.inverter = inverter
        self.set_controls(self.DERCtl, False)

    def set_poll_values(self, newControls):
        if self.DERCtl != newControls:
            self.set_controls(newControls, True)

    def set_controls(self, ctl, update):
        self.DERCtl = ctl
        self.href = self.DERCtl['@href']
        self.ReplyLink = self.DERCtl['@replyTo']
        self.responseReq = self.DERCtl['@responseRequired'] 
        self.description = self.DERCtl['description']
        self.EventStatus = self.createStatus(self.DERCtl['EventStatus'])
        self.duration = self.DERCtl['interval']['duration']
        self.start = self.DERCtl['interval']['start']
        if update:
            self.CtlBase.refresh(self.DERCtl['DERControlBase'])
        else:
            self.CtlBase = DERControlBase(self.inverter, self.DERCtl['DERControlBase'])

    def createStatus(self, status):
        return EventStatus(status['currentStatus'], status['currentStatus'], status['potentiallySuperseded'])

class DERCurveList(object):
    def __init__(self, href, inverter):
        if DEBUG:
	    self.file = os.path.join(xml_path, 'DERCurveList.xml')
            self.response = xmltodict.parse(open(self.file).read())
        else:
            self.response = GET(href)
        self.href = href
        self.DERCurveList = self.response['DERCurveList']['DERCurve']
        self.DERCurves = []
        self.Cur_mRIDS = []
       # self.create_curves(inverter)

    def create_curves(self, inverter):
        for cur in self.DERCurveList:
            self.DERCurves.append(DERCurve(cur, inverter))
            self.Cur_mRIDS.append(cur['mRID'])

    def poll(self):
        changed, res = check_content(self, 'DERCurveList', 'DERCurve')
        if changed:
            self.response = res
            newCur_mRIDS = [x['mRID'] for x in newCurList]
            temp = set(newCur_mRIDS).symmetric_difference(set(Cur_mRIDs))
            if len(temp>0):
                self.Cur_mRIDs.remove([l for l in temp.difference(set(newCur_mRIDS))])
                self.DERCurves.remove([self.get_cur_by_mRID(l, self.DERCurves) for l in temp.difference(set(newCur_mRIDS))])

                self.Cur_mRIDs.append([l for l in temp.difference(set(Cur_mRIDs))])
                self.DERCurves.append([DERProgram(self.get_cur_by_mRID(l, newCurList)) for l in temp.difference(set(Cur_mRIDs))])
                
            for cur in self.DERCurves:
                cur.set_poll_values(newCurList)

    def get_cur_by_mRID(self, id, curves):
        return [p for p in curves if p.mRID == id]

class DERCurve(object):
    def __init__(self, curve, inverter):
        '''
	Attr:
        opModLVRTMUSTTrip, opModHVRTMUSTTrip, 
        opModLFRTMUSTTrip, opModHFRTMUSTTrip, 
        opModVoltVar,  opModVoltWatt, opModFreqWatt
        '''
        self.DERCur = curve
        self.mRID = self.DERCur['mRID']
        self.inverter = inverter
        self.extract(curve)

    def set_poll_values(self, response):
        if self.DERCur != response_obj:
            self.extract(present_curve)
            self.DERCur = response

    def extract(self, curve):
        self.href = curve['@href'] 
        self.curveType = curve['curveType']  
        self.description = curve['description']      
        self.creationTime = curve['creationTime'] 

        type_fn = {
            0 : self.set_volt_var(curve['yRefType']),
            1 : self.set_freq_watt(),
            3 : self.set_volt_watt(curve['yRefType']),
            4 : self.VRT('opModLVRTMUSTTrip'),
            5 : self.VRT('opModHVTMUSTTrip'),
            6 : self.FRT('opModLFRTMUSTTrip'),
            7 : self.FRT('opModHFRTMUSTTrip')
        }
        if self.inverter is not None:
            type_fn[self.curveType]()
        

    def set_curves(self, response):
        self.DERCurData = []
        for cur in self.DERCur['CurveData']:
            self.DERCurData.append(Curve_Data(cur, response['model'], response['register'], self.inverter))

    def set_volt_watt(self, yRef):
        '''
        The Volt-Watt reduces active power output as a function of
        measured voltage. 
        '''
        Vref = self.inverter.read_point('settings', 'VRef')
        model = 'volt_watt'
        #Writing the yRefType
        self.inverter.write_point(model, 'DeptRef', yRef)
        for data in self.DERCur['CurveData']:
		data["xvalue"] = int(data["xvalue"])*100/Vref 

        self.set_curves({
            'model': model,
            'register': 14
        })

    def set_freq_watt(self):
        '''
        The Frequency-Watt function limits active power
        generation or consumption when the line frequency deviates from nominal by a specified amount.
        '''
        self.set_curves({
            'model': 'freq_watt_param',
            'register': 13
        })

    def VRT(self, type):
        '''
        Ref page 124 of that IEEE sheet
        Types:
            opModHVRTMUSTTrip
            opModLVRTMUSTTrip
        '''
        Vref = self.inverter.read_point('settings', 'VRef')

        if type == 'opModLVRTMUSTTrip':
            model = 'lvrt'
        else:
            model = 'hvrt'
	for data in self.DERCur['CurveData']:
		data["xvalue"] = int(data["xvalue"])*100/Vref

        self.set_curves({
            'model': model,
            'register': 13
        })

    def set_volt_var(self, yRef):
        '''
        The static Volt-VAr function provides over- or underexcited
        VAr compensation as a function of measured voltage. 
        '''
        Vref = self.inverter.read_point('settings', 'VRef')
        yRefType = self.inverter.write_point('volt_var', 'DeptRef', yRef)

        for data in self.DERCur['CurveData']:
		data["xvalue"] = int(data["xvalue"])*100/Vref
        self.set_curves({
            'model': 'volt_var',
            'register': 14
        })

    def FRT(self, type, response_points):
        '''
        opModHFRTMustTrip: High frequency must trip disturbance response curve
        opModLFMRTMustTrip: Low frequency must trip disturbance response curve
        '''
        if opModLFMRTMustTrip:
            model = 'lfrt'
        else:
            model = 'hfrt'
        self.set_curves({
            'model': model,
            'register': 13
        })

class Curve_Data(object):
    '''
    Attr: excitation, xvalue, yvalue
    '''
    def __init__(self, model_name, data, register, inverter):
        self.data = data
        self.inverter = inverter
	self.model_name = model_name
        id_modelmap = self.inverter.device.models
        modelname_id= {
            'volt_var': id_modelmap[126],
            'freq_watt_param': id_modelmap[127],
            'volt_watt': id_modelmap[132],
            'lvrt': id_modelmap[129],
            'hvrt': id_modelmap[130],
            'lfrt': id_modelmap[135],
            'hfrt': id_modelmap[136],
        }
        self.model = modelname_id[model_name]
	self.set_curves(register)

    def set_active_curve(self, curve_index):
        if self.inverter is not None:
            self.inverter.write_point(self.model, 'ActCrv', curve_index) 
            self.inverter.write_point(self.model, 'ModEna', 0) 

    def get_active_curve(self):
        if self.inverter is not None:
            self.inverter.read_point(self.model, 'ActCrv')

    def set_curves(self, register): 
        '''
        Attributes:
        model (object): Pass the model object related to the curve
        response_points (dict: Response from the DERCurveLink query
        register (int): Starting register number for points
        curve_index: Index of the curve to be activated (1-4)
        enable_mode: Enable the curve control (0- Enable)
        '''

        active_points = self.inverter.read_point(self.model,  self.model.points[12]) 
        if active_points != 0:
            register += active_points
        for k,v in self.data.items():
            self.inverter.write_point(self.model, self.model.points[register+1], int(k)) 
            self.inverter.write_point(self.model,self.model.points[register], int(v))
            register += 2
        
        self.inverter.write_point(self.model, self.model.points[12],len(self.data.keys()))

