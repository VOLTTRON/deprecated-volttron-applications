import sys
from api.xsd import oadr_20b
import os
from vtn.models import *
import random
from django.utils import timezone
from datetime import datetime, timedelta

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
XML_DIR = os.path.join(TEST_DIR, 'xml/')
BASE_URL = 'http://127.0.0.1:8000'
POLL_URL = '/OpenADR2/Simple/2.0b/OadrPoll'
EVENT_URL = '/OpenADR2/Simple/2.0b/EiEvent'
REPORT_URL = '/OpenADR2/Simple/2.0b/EiReport'


def python_dt_to_iso(date_time):
    """
    :param date_time: Python date-time object
    :return: an iso 8601 formatted string
    """
    formatter = oadr_20b.GeneratedsSuper()
    to_return = formatter.gds_format_datetime(date_time)
    if to_return[-2] == '0':
        return to_return[0:-2] + to_return[-1]
    else:
        return to_return


def get_file_xml(filename):
    """
    :param filename: the filename, without the .xml suffix, in the tests/xml directory
    :return: returns the specified file's xml
    """

    file = os.path.join(XML_DIR, filename + '.xml')
    with open(file, 'r') as f:
        xml = f.read()
    return xml


class NullWriter(object):
    """
    This class is used in conjunction with suppress_output()
    to temporarily disable printing to the console.
    """
    def write(self, arg):
        pass


def suppress_output():
    null_write = NullWriter()
    old_stdout = sys.stdout
    sys.stdout = null_write
    return old_stdout


def create_dr_event(ven_id, event_status, ven_status):
    programs = DRProgram.objects.all()
    program = programs[random.randint(0, len(programs) - 1)]

    scheduled_notification_time = timezone.now()
    start = scheduled_notification_time + timedelta(seconds=10)
    end = start + timedelta(hours=random.randint(2, 5))
    modification_number = 0
    last_status_time = timezone.now()

    all_events = [int(event.event_id) for event in DREvent.objects.all()]
    all_events.sort()
    event_id = str(all_events[-1] + 1) if len(all_events) > 0 else '0'
    superseded = False
    deleted = False

    DREvent(dr_program=program,
            scheduled_notification_time=scheduled_notification_time,
            start=start,
            end=end,
            modification_number=modification_number,
            last_status_time=last_status_time,
            event_id=event_id,
            superseded=superseded,
            deleted=deleted,
            status=event_status).save()

    dr_event = DREvent.objects.get(event_id=0)

    # Create site event
    site = Site.objects.get(ven_id=ven_id)
    modification_number = 0
    opt_in = 'none'
    deleted = False

    SiteEvent(dr_event=dr_event,
              site=site,
              status=event_status,
              modification_number=modification_number,
              opt_in=opt_in,
              ven_status=ven_status,
              deleted=deleted,
              last_status_time=timezone.now()).save()
