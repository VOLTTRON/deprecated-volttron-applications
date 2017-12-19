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
from api.builders import *
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from io import StringIO
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_xml.parsers import XMLParser
from api.xsd import oadr_20b
from vtn.models import *
from django.core.handlers.wsgi import WSGIRequest
from rest_framework import status
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
import logging
import isodate
from django.utils import timezone
import pytz
from rest_framework_xml.renderers import XMLRenderer
from django.conf import settings
from django.db import connection

SCHEMA_VERSION = '2.0b'
VEN_STATUS_ACK = 'acknowledged'
VEN_STATUS_NOT_TOLD = 'not_told'
VEN_STATUS_TOLD = 'told'
BOGUS_REQUEST_ID = 300


logging.basicConfig(format='%(asctime)s %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p',
                    level=logging.DEBUG)
logger = logging.getLogger(__name__)


def update_notification_sent_time(site_events):
    for site_event in site_events:
        site_event.notification_sent_time = timezone.now()
        site_event.ven_status = VEN_STATUS_TOLD
        site_event.save()


def update_last_status_time(ven_id):
    try:
        site = Site.objects.get(ven_id=ven_id)
        site.last_status_time = timezone.now()
        site.save()
    except ObjectDoesNotExist:
        pass


class OADRRenderer(XMLRenderer):

    media_type = 'application/xml'

    def export (self, xsd_object, make_pretty=True):
        buffer = StringIO()
        xsd_object.export(buffer,
                          1,
                          pretty_print = make_pretty
                          )
        return buffer.getvalue()

    def render(self, data, accepted_media_type=None, renderer_context=None):

        if data is None:
            return ''

        if 'result' not in data:
            data['rendered_result'] = ''
        else:
            make_pretty = True # 'html' in accepted_media_type
            data['rendered_result'] = self.export(data['result'], make_pretty)

        return data['rendered_result']


class OADRParser(XMLParser):

    media_type = "application/xml"

    def parse(self, stream, media_type=None, parser_context=None):
        """
        Parses the incoming bytestream as XML and returns the resulting data.

        @todo rest-framework may send in either a WSGIRequest or a StringIO.
        depending on whether the original WSGIRequest has the attribute '_read'
        I don't understand this and need to figure it out. (Bob's comments)
        """
        if isinstance(stream, WSGIRequest):
            return oadr_20b.parseString(stream.body, silence=True)
        elif hasattr(stream, 'buf'):
            return oadr_20b.parseString(stream.buf, silence=True)

        return None


class OADRPoll(APIView):
    """
    Called when the VEN issues an oadrPoll. Responds back, right now, with
    a Distribute Event if there are any un-acknowledged site events.
    """

    parser_classes = (OADRParser,)
    renderer_classes = (OADRRenderer,)

    @csrf_exempt
    def post(self, request, format=None):

        # Make preliminary checks
        try:
            ven_id = request.data.oadrSignedObject.oadrPoll.venID
            # 'Validate' VEN ID if there is one
            if not Site.objects.filter(ven_id=ven_id).exists():
                payload_response = OADRResponseBuilder(SCHEMA_VERSION,
                                                       400,
                                                       BOGUS_REQUEST_ID,
                                                       'No site with given VEN ID found')
                payload_xml = payload_response.wrap()
                update_last_status_time(ven_id)
                logger.warning('No site with given VEN ID found')
                return Response({'result' : payload_xml}, content_type='application/xml', status=status.HTTP_400_BAD_REQUEST)

        except AttributeError as err:
            payload_response = OADRResponseBuilder(SCHEMA_VERSION,
                                                   400,
                                                   BOGUS_REQUEST_ID,
                                                   'Request has no VEN ID')
            payload_xml = payload_response.wrap()
            logging.warning('VTN Poll has no VEN ID')
            return Response({'result' : payload_xml}, content_type='application/xml', status=status.HTTP_400_BAD_REQUEST)

        # A site with that VEN ID exists
        build_events = SiteEvent.objects.filter(site__ven_id=ven_id,
                                                dr_event__scheduled_notification_time__lt=timezone.now(),
                                                dr_event__end__gt=timezone.now()) \
                                                .filter(~Q(ven_status=VEN_STATUS_ACK))

        # Do we have events to send?
        if build_events.count() > 0:
            build_events = SiteEvent.objects.filter(site__ven_id=ven_id,
                                                    dr_event__scheduled_notification_time__lt=timezone.now(),
                                                    dr_event__end__gt=timezone.now())

            # Build OADR distribute event
            payload_event = OADRDistributeEventBuilder(ven_id=ven_id, site_events=build_events)
            payload_xml = payload_event.wrap()

            # Update the notification_sent_time of the involved site events
            update_notification_sent_time(build_events)
            update_last_status_time(ven_id)
            logger.info("VTN sent distribute event")

            return Response({'result' : payload_xml}, content_type='application/xml', status=status.HTTP_200_OK)

        # Nothing to return at this point - return normal status with an empty oadr_response
        else:
            payload_response = OADRResponseBuilder(SCHEMA_VERSION,
                                                   200,
                                                   BOGUS_REQUEST_ID,
                                                   'No events to send',
                                                   ven_id)
            payload_xml = payload_response.wrap()
            update_last_status_time(ven_id)
            return Response({'result' : payload_xml}, content_type='application/xml', status=status.HTTP_200_OK)


class EIReport(APIView):
    """
    VEN requests that are coming this way:
        - oadrRegisterReport
        - oadrCreatedReport (in response to oadrRegisterReport)
        - oadrUpdateReport
        - oadrCanceledReport
    """

    parser_classes = (OADRParser,)
    renderer_classes = (OADRRenderer,)

    @csrf_exempt
    def post(self, request, format=None):

        # CHECK IF REGISTER REPORT WAS SENT
        if request.data.oadrSignedObject.oadrRegisterReport is not None:
            try:
                ven_id = request.data.oadrSignedObject.oadrRegisterReport.venID

                oadr_reports = request.data.oadrSignedObject.oadrRegisterReport.oadrReport

                for oadr_report in oadr_reports:
                    try:
                        report_specifier_id = oadr_report.reportSpecifierID

                    except AttributeError as err:
                        payload_response = OADRResponseBuilder(SCHEMA_VERSION,
                                                               400,
                                                               BOGUS_REQUEST_ID,
                                                               'Report specifier ID not found',
                                                               ven_id)
                        payload_xml = payload_response.wrap()
                        update_last_status_time(ven_id)
                        logging.warning("No report specifier ID found in RegisterReport")
                        return Response({'result' : payload_xml}, content_type='application/xml',
                                        status=status.HTTP_400_BAD_REQUEST)

                    payload_registered_report = OADRRegisteredReportBuilder(ven_id, report_specifier_id)
                    payload_registered_xml = payload_registered_report.wrap()
                    update_last_status_time(ven_id)
                    return Response({'result' : payload_registered_xml}, content_type='application/xml',
                                    status=status.HTTP_200_OK)

            except (AttributeError, Exception) as err:
                payload_response = OADRResponseBuilder(SCHEMA_VERSION,
                                                       400,
                                                       BOGUS_REQUEST_ID,
                                                       'Register Report missing elements')
                payload_xml = payload_response.wrap()
                logger.warning("RegisterReport is missing elements")
                return Response({'result' : payload_xml}, content_type='application/xml', status=status.HTTP_400_BAD_REQUEST)

        # CHECK IF CREATED REPORT WAS SENT
        elif request.data.oadrSignedObject.oadrCreatedReport is not None:
            try:
                request_id = request.data.oadrSignedObject.oadrCreatedReport.eiResponse.requestID
                report_request_ids = request.data.oadrSignedObject.oadrCreatedReport.oadrPendingReports.reportRequestID

                for report_request_id in report_request_ids:
                    try:
                        report = Report.objects.get(report_request_id=report_request_id)
                    except ObjectDoesNotExist as err:
                        logger.warning("Report with report request ID {} not found".format(report_request_id))

                payload_response = OADRResponseBuilder(SCHEMA_VERSION,
                                                       200,
                                                       request_id)
                payload_xml = payload_response.wrap()
                return Response({'result' : payload_xml}, content_type='application/xml', status=status.HTTP_200_OK)

            except AttributeError as err:
                payload_response = OADRResponseBuilder(SCHEMA_VERSION,
                                                       400,
                                                       BOGUS_REQUEST_ID,
                                                       'Created report missing elements')
                payload_xml = payload_response.wrap()
                logger.warning('CreatedReport XML missing sent from VEN is missing elements')
                return Response({'result' : payload_xml}, content_type='application/xml', status=status.HTTP_400_BAD_REQUEST)

        # CHECK IF UPDATED REPORT WAS SENT
        elif request.data.oadrSignedObject.oadrUpdateReport is not None:
            try:
                request_id = request.data.oadrSignedObject.oadrUpdateReport.requestID
                oadr_reports = request.data.oadrSignedObject.oadrUpdateReport.oadrReport
                ven_id = request.data.oadrSignedObject.oadrUpdateReport.venID

            except AttributeError:
                payload_response = OADRResponseBuilder(SCHEMA_VERSION,
                                                       400,
                                                       BOGUS_REQUEST_ID,
                                                       'Update report missing elements')
                payload_xml = payload_response.wrap()
                logger.warning("UpdateReport XML from VEN is missing elements")
                return Response({'result' : payload_xml}, content_type='application/xml', status=status.HTTP_400_BAD_REQUEST)

            try:
                site = Site.objects.get(ven_id=ven_id)
            except (ObjectDoesNotExist, MultipleObjectsReturned):
                response_description = 'No site with the given VEN ID'
                payload_response = OADRResponseBuilder(SCHEMA_VERSION,
                                                       400,
                                                       BOGUS_REQUEST_ID,
                                                       response_description)
                payload_xml = payload_response.wrap()
                logger.warning("No site with the given VEN ID in UpdateReport")
                return Response({'result' : payload_xml}, content_type='application/xml', status=status.HTTP_400_BAD_REQUEST)
            for oadr_report in oadr_reports:
                try:
                    intervals = oadr_report.intervals.interval
                except AttributeError:
                    response_description = 'No intervals given'
                    payload_response = OADRResponseBuilder(SCHEMA_VERSION,
                                                           400,
                                                           BOGUS_REQUEST_ID,
                                                           response_description)
                    payload_xml = payload_response.wrap()
                    logger.warning("No intervals given in UpdateReport")
                    return Response({'result' : payload_xml}, content_type='application/xml', status=status.HTTP_400_BAD_REQUEST)
                for interval in intervals:
                    start = interval.dtstart.get_date_time()
                    start.replace(tzinfo=pytz.utc)
                    if start is not None:
                        baseline_power = 'n.a.'
                        actual_power = 'n.a.'
                        report_payloads = interval.streamPayloadBase
                        for report_payload in report_payloads:
                            rID = report_payload.rID
                            if rID == 'baseline_power':
                                baseline_power = report_payload.payloadBase.value
                            elif rID == 'actual_power':
                                actual_power = report_payload.payloadBase.value
                        reported_on = pytz.timezone(settings.TIME_ZONE).localize(datetime.now())
                        if baseline_power != 'n.a.' and actual_power != 'n.a.':
                            t = Telemetry(site=site, created_on=start,
                                          reported_on=reported_on,
                                          baseline_power_kw=baseline_power,
                                          measured_power_kw=actual_power)
                            t.save()
            payload_response = OADRResponseBuilder(SCHEMA_VERSION,
                                                   200,
                                                   request_id)
            payload_xml = payload_response.wrap()
            return Response({'result' : payload_xml}, content_type='application/xml', status=status.HTTP_200_OK)

        # CHECK IF CANCELED REPORT WAS SENT
        elif request.data.oadrSignedObject.oadrCanceledReport is not None:
            try:
                request_id = request.data.oadrSignedObject.oadrCanceledReport.eiResponse.requestID
                oadr_report_ids = request.data.oadrSignedObject.oadrCanceledReport.oadrPendingReports.reportRequestID
                ven_id = request.data.oadrSignedObject.oadrCanceledReport.venID

            except AttributeError:
                payload_response = OADRResponseBuilder(SCHEMA_VERSION,
                                                       400,
                                                       BOGUS_REQUEST_ID,
                                                       'Canceled report missing elements')
                payload_xml = payload_response.wrap()
                logger.warning("CanceledReport XML from VEN is missing elements")
                return Response({'result': payload_xml}, content_type='application/xml',
                                status=status.HTTP_400_BAD_REQUEST)

            ven_report_request_ids = Report.objects.filter(ven_id=ven_id).filter(~Q(report_status='cancelled')) \
                                                   .values_list('report_request_id', flat=True)

            ven_report_request_ids = list(ven_report_request_ids)

            for report_request_id in ven_report_request_ids:
                if report_request_id not in oadr_report_ids:
                    report_to_cancel = Report.objects.get(report_request_id=report_request_id)
                    report_to_cancel.report_status = 'cancelled'
                    report_to_cancel.save()

            payload_response = OADRResponseBuilder(SCHEMA_VERSION,
                                                   200,
                                                   request_id)
            payload_xml = payload_response.wrap()
            return Response({'result' : payload_xml}, content_type='application/xml', status=status.HTTP_200_OK)

        else:
            response_description = "VEN sent an error code"
            try:
                response_code = request.data.oadrSignedObject.oadrResponse.eiResponse.responseCode
                request_id = request.data.oadrSignedObject.oadrResponse.eiResponse.requestID
                logger.warning('VEN sent an error response code of {}'.format(response_code))
                payload_response = OADRResponseBuilder(SCHEMA_VERSION,
                                                       204,
                                                       request_id,
                                                       response_description)
                payload_xml = payload_response.wrap()
                return Response({'result' : payload_xml}, content_type='application/xml', status=status.HTTP_204_NO_CONTENT)
            except AttributeError:
                payload_response = OADRResponseBuilder(SCHEMA_VERSION,
                                                       400,
                                                       BOGUS_REQUEST_ID,
                                                       response_description)
                payload_xml = payload_response.wrap()
                logger.warning("Could not parse VEN's error code")
                return Response({'result' : payload_xml}, content_type='application/xml', status=status.HTTP_400_BAD_REQUEST)


class EIEvent(APIView):
    parser_classes = (OADRParser,)
    renderer_classes = (OADRRenderer,)

    @csrf_exempt
    def post(self, request, format=None):

        # IS THIS A REQUEST EVENT?
        if request.data.oadrSignedObject.oadrRequestEvent is not None:
            try:
                ven_id = request.data.oadrSignedObject.oadrRequestEvent.venID

                site_events = SiteEvent.objects.filter(site__ven_id=ven_id,
                                                       dr_event__scheduled_notification_time__lt=timezone.now()) \
                                               .filter(~Q(ven_status='acknowledged'))

                oadr_distribute_event = OADRDistributeEventBuilder(ven_id, site_events)

                payload_xml = oadr_distribute_event.wrap()

                update_notification_sent_time(site_events)

                return Response({'result' : payload_xml}, content_type='application/xml')
            except (AttributeError, Exception) as err:
                response_description = 'Elements missing in request event'
                payload_response = OADRResponseBuilder(SCHEMA_VERSION,
                                                       400,
                                                       BOGUS_REQUEST_ID,
                                                       response_description)
                payload_xml = payload_response.wrap()
                logger.warning("Elements missing in VEN's RequestEvent XML")
                return Response({'result' : payload_xml}, content_type='application/xml', status=status.HTTP_400_BAD_REQUEST)

        # IS THIS A CREATED EVENT?
        elif request.data.oadrSignedObject.oadrCreatedEvent is not None:
            try:
                ven_id = request.data.oadrSignedObject.oadrCreatedEvent.eiCreatedEvent.venID
                request_id = request.data.oadrSignedObject.oadrCreatedEvent.eiCreatedEvent.eiResponse.requestID
                signed_object = request.data.oadrSignedObject
                event_responses = signed_object.oadrCreatedEvent.eiCreatedEvent.eventResponses.get_eventResponse()
                for event_response in event_responses:
                    try:
                        event_id = event_response.qualifiedEventID.eventID
                        opt_response = event_response.optType
                    except AttributeError as err:

                        response_description = "No event ID or opt response"
                        payload_response = OADRResponseBuilder(SCHEMA_VERSION,
                                                               400,
                                                               BOGUS_REQUEST_ID,
                                                               response_description)
                        payload_xml = payload_response.wrap()
                        update_last_status_time(ven_id)
                        logger.warning("No event ID or opt response in VEN's CreatedEvent XML")
                        return Response({'result' : payload_xml}, content_type='application/xml', status=status.HTTP_400_BAD_REQUEST)

                    try:
                        # this should only return one site event
                        site_events = SiteEvent.objects.filter(dr_event__event_id=event_id,
                                                               site__ven_id=ven_id)

                        for site_event in site_events:
                            site_event.ven_status = VEN_STATUS_ACK
                            site_event.last_status_time = timezone.now()
                            site_event.opt_in = opt_response
                            site_event.last_opt_in = timezone.now()
                            site_event.save()

                        payload_response = OADRResponseBuilder(SCHEMA_VERSION,
                                                               200,
                                                               request_id,
                                                               "Saved 'acknowledged' VEN status and updated statuses",
                                                               ven_id)
                        payload_xml = payload_response.wrap()
                        update_last_status_time(ven_id)
                        return Response({'result' : payload_xml}, content_type='application/xml', status=status.HTTP_200_OK)

                    except (MultipleObjectsReturned, ObjectDoesNotExist):
                        payload_response = OADRResponseBuilder(SCHEMA_VERSION,
                                                               500,
                                                               request_id,
                                                               "Database error",
                                                               ven_id)
                        payload_xml = payload_response.wrap()
                        update_last_status_time(ven_id)
                        logger.warning("VTN database error when processing CreatedEvent")
                        return Response({'result' : payload_xml}, content_type='application/xml', status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            except (AttributeError, Exception) as err:
                response_description = "Elements missing in created event"
                payload_response = OADRResponseBuilder(SCHEMA_VERSION,
                                                       400,
                                                       BOGUS_REQUEST_ID,
                                                       response_description)
                payload_xml = payload_response.wrap()
                logger.warning(response_description)
                return Response({'result' : payload_xml}, content_type='application/xml', status=status.HTTP_400_BAD_REQUEST)


        else:
            response_description = "VEN sent an error code"
            response_code = request.data.oadrSignedObject.oadrResponse.eiResponse.responseCode
            logger.warning('VEN sent an error response code of {}'.format(response_code))
            payload_response = OADRResponseBuilder(SCHEMA_VERSION,
                                                   204,
                                                   BOGUS_REQUEST_ID,
                                                   response_description)
            payload_xml = payload_response.wrap()
            return Response({'result' : payload_xml}, content_type='application/xml', status=status.HTTP_204_NO_CONTENT)