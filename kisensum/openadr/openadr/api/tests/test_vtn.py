from vtn.models import *
from django.test import TestCase, Client
import pytest
from .setup_test_data import create_customers, create_dr_programs, create_sites, create_dr_events
import os
from django.utils import timezone
import time
from django.db.models import Q
from api.xsd import oadr_20b
import isodate
import pytz
import sys
from .helper_functions import *

import django
django.setup()

pytestmark = pytest.mark.django_db

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
XML_DIR = os.path.join(TEST_DIR, 'xml/')
BASE_URL = 'http://127.0.0.1:8000'
POLL_URL = '/OpenADR2/Simple/2.0b/OadrPoll'
EVENT_URL = '/OpenADR2/Simple/2.0b/EiEvent'
REPORT_URL = '/OpenADR2/Simple/2.0b/EiReport'


@pytest.fixture(scope="module")
def database_ready():
    create_customers(5)
    create_dr_programs(2)
    create_sites(2)

    yield "database ready"


@pytest.mark.usefixtures("database_ready")
class TestDialogue(TestCase):
    """
    This class tests the various features of the VTN.
    """

    # Test reporting #

    def test_register_report(self):
        """
        This checks to make sure a report is correctly recorded in the database
        after a RegisterReport is sent to the VTN.

        """
        Report.objects.all().delete()  # Get a clean slate
        register_report_xml = get_file_xml('ven_register_report')
        client = Client()
        response = client.post(REPORT_URL, register_report_xml, content_type="application/xml")
        old_stdout = suppress_output()
        parsed = oadr_20b.parseString(response.content)
        sys.stdout = old_stdout
        report = Report.objects.get(ven_id='0')
        self.assertEqual(report.report_request_id, '0')
        self.assertEqual(report.report_status, 'active')
        self.assertIsNotNone(parsed.oadrSignedObject.oadrRegisteredReport)

    def test_add_register_report(self):
        """
        This checks to make sure the report request ID is correctly incremented
        in the database when an active report for a given VEN already exists.
        """
        Report.objects.all().delete()
        Report(ven_id='0', report_request_id='0', report_status='active').save()
        register_report_xml = get_file_xml('ven_register_report')
        client = Client()
        response = client.post(REPORT_URL, register_report_xml, content_type="application/xml")
        old_stdout = suppress_output()
        parsed = oadr_20b.parseString(response.content)
        sys.stdout = old_stdout
        reports = Report.objects.filter(Q(report_request_id='0') | Q(report_request_id='1'))
        self.assertEqual(reports.count(), 2)

    def test_created_and_canceled_report(self):
        """
        This checks to make sure the VTN is correctly processing CreatedReport
        and CanceledReport.
        """
        Report.objects.all().delete()  # Clean the slate
        Report(ven_id='0', report_request_id='0', report_status='active').save()
        created_report_xml = get_file_xml('ven_created_report')
        vtn_response = get_file_xml('vtn_200_response')
        request_id = 'c206f5a8-e1c3-11e7-91ae-6c96cfdb28b5'  # Can change this as long as corresponding xml file is changed as well
        client = Client()
        created_report_response = client.post(REPORT_URL, created_report_xml, content_type="application/xml")
        vtn_response = vtn_response.format(request_id=request_id)
        canceled_report_xml = get_file_xml('ven_canceled_report')
        canceled_report_response = client.post(REPORT_URL, canceled_report_xml, content_type="application/xml")
        report = Report.objects.get(report_request_id='0')
        self.assertEqual(report.report_status, 'cancelled')
        self.assertXMLEqual(vtn_response, created_report_response.content.decode('utf-8'))

    def test_update_report(self):
        """
        This checks if the correct telemetry in UpdateReport has been recorded in the database.
        """
        Telemetry.objects.all().delete()  # Delete any existing Telemetry objects
        update_report_xml = get_file_xml('ven_update_report')
        old_stdout = suppress_output()
        parsed_update_report = oadr_20b.parseString(bytes(update_report_xml, 'utf-8'))
        sys.stdout = old_stdout
        oadr_reports = parsed_update_report.oadrSignedObject.oadrUpdateReport.oadrReport
        client = Client()
        response = client.post(REPORT_URL, update_report_xml, content_type="application/xml")
        t_data = Telemetry.objects.all()
        t_data = t_data[0]
        baseline_power = 0
        actual_power = 0
        for oadr_report in oadr_reports:
            intervals = oadr_report.intervals.interval
            for interval in intervals:
                start = interval.dtstart.get_date_time()
                start.replace(tzinfo=pytz.utc)
                if start is not None:
                    report_payloads = interval.streamPayloadBase
                    for report_payload in report_payloads:
                        rID = report_payload.rID
                        if rID == 'baseline_power':
                            baseline_power = report_payload.payloadBase.value
                        elif rID == 'actual_power':
                            actual_power = report_payload.payloadBase.value
        self.assertEqual(baseline_power, t_data.baseline_power_kw)
        self.assertEqual(actual_power, t_data.measured_power_kw)
        self.assertEqual('0', t_data.site.ven_id)

    # Test Events #

    def test_no_events(self):
        """
        This checks that when a VEN poll is sent to the VTN, the VTN responds
        with an empty response when there are no applicable DR Events.
        """
        DREvent.objects.all().delete()  # Clean the slate
        vtn_response_xml = get_file_xml('vtn_response_no_events')
        poll_xml = get_file_xml('ven_poll')
        client = Client()
        response = client.post(POLL_URL, poll_xml, content_type="application/xml")
        self.assertXMLEqual(vtn_response_xml, response.content.decode('utf-8'))

        create_dr_event('0', 'active', 'not_told')
        poll_xml = poll_xml.replace("<ei:venID>0</ei:venID>", "<ei:venID>1</ei:venID>")
        response = client.post(POLL_URL, poll_xml, content_type="application/xml")
        vtn_response_xml = vtn_response_xml.replace("<oadr:venID>0</oadr:venID>", "<oadr:venID>1</oadr:venID>")
        self.assertXMLEqual(vtn_response_xml, response.content.decode('utf-8'))

    def test_one_event(self):
        """
        This checks that a distribute event is correctly returned by the VTN when there is an
        un-acknowledged site-event for the site with ven_id '0'.
        """

        DREvent.objects.all().delete()  # clean the slate
        # Create a DR Event for Site with ven_id '0'
        create_dr_event('0', 'active', 'not_told')

        poll_xml = get_file_xml('ven_poll')
        client = Client()
        response = client.post(POLL_URL, poll_xml, content_type="application/xml")
        old_stdout = suppress_output()
        parsed = oadr_20b.parseString(response.content)
        sys.stdout = old_stdout

        site_event = SiteEvent.objects.get(site__ven_id='0')

        self.assertEqual(site_event.ven_status, 'told')
        self.assertIsNotNone(parsed.oadrSignedObject.oadrDistributeEvent)

    def test_two_events(self):
        """
        This checks that a distribute event is correctly returned by the VTN when there
        is more than one un-acknowledged site-event for the site with ven_id '0'.
        """
        DREvent.objects.all().delete()  # clean the slate
        create_dr_event('0', 'active', 'not_told')
        create_dr_event('0', 'active', 'told')

        poll_xml = get_file_xml('ven_poll')
        client = Client()
        response = client.post(POLL_URL, poll_xml, content_type="application/xml")
        old_stdout = suppress_output()
        parsed = oadr_20b.parseString(response.content)
        sys.stdout = old_stdout

        oadr_events = parsed.oadrSignedObject.oadrDistributeEvent.oadrEvent

        self.assertEqual(len(oadr_events), 2)

    def test_ack_events(self):
        """
        This checks that events that the VEN has already acknowledged aren't re-sent
        by the VTN.
        """

        DREvent.objects.all().delete()
        create_dr_event('0', 'active', 'acknowledged')
        create_dr_event('0', 'active', 'acknowledged')

        poll_xml = get_file_xml('ven_poll')
        client = Client()
        response = client.post(POLL_URL, poll_xml, content_type="application/xml")
        vtn_response_xml = get_file_xml('vtn_response_no_events')
        self.assertXMLEqual(vtn_response_xml, response.content.decode('utf-8'))

    def test_inconsistent_ack_events(self):
        """
        This checks that the VTN sends all applicable events to the VEN, even if some
        events have been acknowledged by the VEN and some have not.
        """

        DREvent.objects.all().delete()
        create_dr_event('0', 'active', 'acknowledged')
        create_dr_event('0', 'active', 'not_told')

        poll_xml = get_file_xml('ven_poll')
        client = Client()
        response = client.post(POLL_URL, poll_xml, content_type="application/xml")
        old_stdout = suppress_output()
        parsed = oadr_20b.parseString(response.content)
        sys.stdout = old_stdout

        oadr_events = parsed.oadrSignedObject.oadrDistributeEvent.oadrEvent

        site_events = SiteEvent.objects.all()
        for site_event in site_events:
            self.assertEqual(site_event.ven_status, 'told')

        self.assertEqual(len(oadr_events), 2)

    def test_canceled_event(self):
        """
        This checks that a canceled event with the 'cancelled' status is sent to VEN upon
        a poll.
        """

        DREvent.objects.all().delete()  # Clear the slate
        create_dr_event('0', 'cancelled', 'not_told')

        poll_xml = get_file_xml('ven_poll')
        client = Client()
        response = client.post(POLL_URL, poll_xml, content_type="application/xml")
        old_stdout = suppress_output()
        parsed = oadr_20b.parseString(response.content)
        sys.stdout = old_stdout
        event_status = ''

        oadr_events = parsed.oadrSignedObject.oadrDistributeEvent.oadrEvent
        for oadr_event in oadr_events:  # There is guaranteed to be only one oadr_event
            event_status = oadr_event.eiEvent.eventDescriptor.eventStatus
        self.assertEqual(event_status, 'cancelled')

    def test_created_event(self):
        """
        Tests that the VTN updates a site event's status upon receipt of
        a CreatedEvent.
        """

        DREvent.objects.all().delete()  # clean the slate
        create_dr_event('0', 'active', 'not_told')
        created_event_xml = get_file_xml('ven_created_event')
        client = Client()
        response = client.post(EVENT_URL, created_event_xml, content_type="application/xml")
        old_stdout = suppress_output()
        parsed = oadr_20b.parseString(response.content)
        sys.stdout = old_stdout

        site_event = SiteEvent.objects.get(site__ven_id='0')

        self.assertEqual(site_event.opt_in, 'optIn')
        self.assertEqual(site_event.ven_status, 'acknowledged')

    def test_invalid_ven_id(self):
        """
        Tests that the VTN returns proper response when the VEN's ven_id doesn't
        exist in the VTN's database.
        """
        DREvent.objects.all().delete()  # clean the slate
        poll_xml = get_file_xml('ven_poll_ven_id_too_high')
        vtn_response_xml = get_file_xml('vtn_no_site_found')
        client = Client()
        response = client.post(POLL_URL, poll_xml, content_type="application/xml")
        self.assertEqual(response.status_code, 400)
        self.assertXMLEqual(vtn_response_xml, response.content.decode('utf-8'))











