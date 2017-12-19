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

from behave import given, when, then
from vtn.tests.factories import *
import time
from selenium.webdriver.support.ui import Select
from vtn.models import *
import django
from django.db.models import Q
from django.core.exceptions import ObjectDoesNotExist


@then('I should see an active "{site_name}" in Site Events')
def step_impl(context, site_name):
    dr_events = DREvent.objects.all()
    try:
        dr_event = dr_events.get(modification_number=1)
    except ObjectDoesNotExist:
        dr_event = dr_events.get(modification_number=0)

    # Have to edit site name because it includes the customer name in parentheses
    new_site_name = site_name[-5:]
    site_event = SiteEvent.objects.get(site__site_name=new_site_name)
    assert site_event.status in ['far', 'scheduled']
    assert site_event.ven_status == 'not_told'
    assert site_event.dr_event.event_id == dr_event.event_id


@then('I should see a cancelled "{site_name}" in Site Events')
def step_impl(context, site_name):

    # This assert statement should change if the corresponding behave test changes
    assert SiteEvent.objects.filter(~Q(status='cancelled')).count() == 3


@then('I should see a cancelled DR Event and cancelled Site Events')
def step_impl(context):

    dr_events = DREvent.objects.all()
    assert dr_events.count() == 2

    old_dr_event = dr_events.get(superseded=True)
    new_cancelled_dr_event = dr_events.get(status='cancelled')

    # asserts about old_dr_event
    assert old_dr_event.superseded is True

    # asserts about new_cancelled_dr_event
    assert new_cancelled_dr_event.modification_number == 1
    assert new_cancelled_dr_event.status == 'cancelled'
    assert new_cancelled_dr_event.superseded is False

    site_events = SiteEvent.objects.all()

    for site_event in site_events:
        assert site_event.dr_event == new_cancelled_dr_event
        assert site_event.status == 'cancelled'
        assert site_event.ven_status == 'not_told'

