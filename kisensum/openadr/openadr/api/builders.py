# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, Battelle Memorial Institute
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
# Government nor the United States Department of Energy, nor Battelle,
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
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import csv
from datetime import datetime, timedelta
from django.db.models import Q
import lxml.etree as etree_
import random
from django.views.decorators.csrf import csrf_exempt
from io import StringIO
import isodate
from isodate import isoduration
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_xml.parsers import XMLParser
from api.xsd import oadr_20b
from vtn.models import *
from django.core.handlers.wsgi import WSGIRequest
from rest_framework import status
from django.db.models import ObjectDoesNotExist
from api.static_methods import *
import pytz
from django.conf import settings

SCHEMA_VERSION = '2.0b'
BOGUS_REQUEST_ID = 300
STATUS_OK = 200


class PayloadXML:

    def __init__(self, name):
        self.wrapped_object_name = name

    def wrap(self):
        kwargs = {self.wrapped_object_name: self.build()}
        signed_object = oadr_20b.oadrSignedObject(Id=None, **kwargs)
        payload = oadr_20b.oadrPayload(Signature=None, oadrSignedObject=signed_object)
        return payload

    def build(self):
        raise NotImplementedError


class OADRResponseBuilder(PayloadXML):

    def __init__(self, schema_version, status_number, request_id, response_description=None, ven_id=None):
        super(self.__class__, self).__init__('oadrResponse')
        self.schema_version = schema_version
        self.status_number = status_number
        self.request_id = request_id
        self.response_description = response_description
        self.ven_id = ven_id

    def build(self):
        return oadr_20b.oadrResponseType(schemaVersion=self.schema_version,
                                         eiResponse=oadr_20b.EiResponseType(responseCode=self.status_number,
                                                                            responseDescription=self.response_description,
                                                                            requestID=self.request_id),
                                         venID=self.ven_id)


class OADRDistributeEventBuilder(PayloadXML):
    """
    This class is used to compose an OADR Distribute Event instance.
    """

    def __init__(self, ven_id, site_events):
        super(self.__class__, self).__init__('oadrDistributeEvent')
        self.ven_id = ven_id
        self.site_events = site_events

    def build(self):
        return oadr_20b.oadrDistributeEventType(schemaVersion=SCHEMA_VERSION,
                                                eiResponse=build_ei_response(status=STATUS_OK,
                                                                             response_description='OK',
                                                                             request_id=BOGUS_REQUEST_ID),
                                                requestID=BOGUS_REQUEST_ID,
                                                vtnID=settings.VTN_ID,
                                                oadrEvent=self.build_oadr_events())

    def build_oadr_events(self):
        oadr_events = []

        # build list of oadr events
        for site_event in self.site_events:
            oadr_events.append(oadr_20b.oadrEventType(eiEvent=self.build_ei_event(site_event),
                                                      oadrResponseRequired='always'))

        return oadr_events

    def build_ei_event(self, site_event):
        return oadr_20b.eiEventType(eventDescriptor=self.build_event_descriptor(site_event),
                                    eiActivePeriod=self.build_active_period(site_event),
                                    eiEventSignals=self.build_ei_signals(site_event))

    @staticmethod
    def build_event_descriptor(site_event):
        event_id = site_event.dr_event.event_id
        modification_number = site_event.dr_event.modification_number

        modification_reason = None
        priority = 1
        test_event = False
        vtn_comment = None

        created_date_time = datetime.isoformat(datetime.now())
        created_date_time = created_date_time[0:-7]

        event_status = 'far'
        if site_event.status == 'cancelled' or site_event.status == 'CANCELED':
            event_status = 'cancelled'
        else:
            event_status = site_event.dr_event.status

        return oadr_20b.eventDescriptorType(eventID=event_id,
                                            modificationNumber=modification_number,
                                            modificationReason=modification_reason,
                                            priority=priority,
                                            createdDateTime=created_date_time,
                                            eventStatus=event_status,
                                            testEvent=test_event,
                                            vtnComment=vtn_comment)

    def build_active_period(self, site_event):
        return oadr_20b.eiActivePeriodType(properties=self.build_active_period_properties(site_event),
                                           components=None)

    @staticmethod
    def build_active_period_properties(site_event):
        # Calculate duration
        event_start = site_event.dr_event.start
        event_end = site_event.dr_event.end
        event_duration = event_end - event_start
        seconds = event_duration.seconds
        # datetime.timedelta only has a seconds property, so pass in seconds to duration
        duration = isoduration.Duration(seconds=seconds)
        iso_duration = isoduration.duration_isoformat(duration)  # duration in iso format
        duration = oadr_20b.DurationPropType(duration=iso_duration)

        x_ei_notification = oadr_20b.DurationPropType(duration=iso_duration)
        dtstart = oadr_20b.dtstart(date_time=event_start)
        properties = oadr_20b.properties(dtstart=dtstart,
                                         duration=duration,
                                         x_eiNotification=x_ei_notification,
                                         x_eiRampUp=None, x_eiRecovery=None)

        return properties

    def build_ei_signals(self, site_event):

        return oadr_20b.eiEventSignalsType(eiEventSignal=self.build_event_signal(site_event))

    @staticmethod
    def build_event_signal(site_event):
        event_start = site_event.dr_event.start
        event_end = site_event.dr_event.end
        event_duration = event_end - event_start

        seconds = event_duration.seconds

        # datetime.timedelta only has a seconds property, so pass in seconds to duration
        duration = isoduration.Duration(seconds=seconds)

        iso_duration = isoduration.duration_isoformat(duration)  # duration in iso format
        duration = oadr_20b.DurationPropType(duration=iso_duration)
        dtstart = oadr_20b.dtstart(date_time=event_start)
        properties = oadr_20b.properties(dtstart=dtstart, duration=duration)
        report_interval = [oadr_20b.WsCalendarIntervalType(properties=properties)]
        interval = [oadr_20b.IntervalType(dtstart=dtstart, duration=duration)]
        intervals = oadr_20b.intervals(interval=interval)
        return [oadr_20b.eiEventSignalType(intervals=intervals, signalName='simple',
                                           signalType='level')]


class OADRRegisteredReportBuilder(PayloadXML):
    """
    This class builds a RegisteredReport instance to convert to XML and pass back to the VEN.
    An instance of this class is created after the VTN receives an oadrRegisterReport.
    """

    def __init__(self, ven_id, report_specifier_id):
        super(self.__class__, self).__init__('oadrRegisteredReport')
        self.ven_id = ven_id
        self.report_specifier_id = report_specifier_id

    def build(self):

        return oadr_20b.oadrRegisteredReportType(schemaVersion=SCHEMA_VERSION,
                                                 eiResponse=build_ei_response(status=STATUS_OK,
                                                                              response_description='OK',
                                                                              request_id=BOGUS_REQUEST_ID),
                                                 oadrReportRequest=self.build_oadr_report_request(),
                                                 venID=self.ven_id)

    def build_oadr_report_request(self):

        all_report_request_ids = [int(r.report_request_id) for r in Report.objects.all()]
        all_report_request_ids.sort()
        report_request_id = str(all_report_request_ids[-1] + 1) if len(all_report_request_ids) > 0 else '0'

        report = Report(report_request_id=report_request_id, ven_id=self.ven_id, report_status='active')
        report.save()

        return [oadr_20b.oadrReportRequestType(reportRequestID=report_request_id,
                                               reportSpecifier=self.build_report_specifier())]

    def build_report_specifier(self):

        report_specifier_id = self.report_specifier_id
        time = pytz.UTC.localize(datetime.utcnow())
        dtstart = oadr_20b.dtstart(date_time=time)

        # report duration == None is a signal to the Kisensum VEN (outside of the normal OADR protocol)
        # to indicate that this report should continue indefinitely, i.e., until superseded by another report request.

        properties = oadr_20b.properties(dtstart=dtstart, duration=None)
        report_interval = oadr_20b.WsCalendarIntervalType(properties=properties)

        return oadr_20b.ReportSpecifierType(reportSpecifierID=report_specifier_id,
                                            reportInterval=report_interval)

    @staticmethod
    def build_report_back_duration(self):
        return 0

    @staticmethod
    def build_specifier_payload(self):
        return oadr_20b.SpecifierPayloadType(rID=None, readingType=None) # maybe readingType is primitive


