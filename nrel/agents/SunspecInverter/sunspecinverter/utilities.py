import datetime
import requests
import os
import xmltodict
from volttron.platform import get_volttron_root

DEBUG = True

def get_current_time():
    sec = id_to_model(122).points[41]
    return str(datetime.timedelta(seconds=sec))

def POST(url, xml, contentLength =1, hostname='SEP'):
    POST_header = {'Host': hostname, 'Content-Type': 'application/sep+xml',
                        'Content-Length': contentLength}
    url = "http://"+url
    if not DEBUG:
        r = requests.post(url, headers=POST_header, data=xml, verify=False) 
        if r.status_code == requests.codes.ok:
            return res.json()
        else:
            _log.warning("%s threw an error"%url)

def GET(url, hostname='SEP'):
    GET_header = {'Host': hostname, 'Accept': 'application/sep+xml'} 
    url = "http://"+url
    if not DEBUG:
        r = requests.get(url, headers=GET_header, verify=False) 
        if r.status_code == requests.codes.ok:
            return xmltodict.parse(r.json())
        else:
            _log.warning("%s threw an error"%url)

def check_content(obj, l, t=None):
        if DEBUG:
            newResponse = xmltodict.parse(open(obj.file).read()) 
        else:
            newResponse = GET(obj.href)
	newResponse = newResponse[l][t]
        return (obj.response == newResponse, newResponse)

def get_xml_path():
    root = get_volttron_root()
    services_core = os.path.join(root, "services/core")
    return os.path.join(services_core, "SunspecInverter/XML_files")

def get_xml(type, content):
        xml_content = {}
        xml_content[type] = {}
        xml_content[type]["@xmlns"] = "urn:ieee:std:2030.5:ns"
        for k,v in content.items():
            xml_content[type][k] = v
        return xmltodict.unparse(xml_content,full_document=False)
