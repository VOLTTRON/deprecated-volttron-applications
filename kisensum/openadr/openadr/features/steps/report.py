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
from selenium.common.exceptions import NoSuchElementException
import time


@when('I filter Date Range "{date_range}" only')
def step_impl(context, date_range):
    br = context.browser
    br.find_element_by_link_text("Report").click()

    # Redirect to Report Page
    assert br.current_url.endswith('/report/') != -1
    br.find_element_by_name("datefilter").send_keys(date_range)
    br.find_element_by_name("filter_button").click()


@when('I filter DR Program "{dr_program_name}" only')
def step_impl(context, dr_program_name):
    br = context.browser
    br.find_element_by_link_text("Report").click()

    # Redirect to Report Page
    assert br.current_url.endswith('/report/') != -1
    br.find_element_by_name("dr_program").send_keys(dr_program_name)
    br.find_element_by_name("filter_button").click()


@when('I filter DR Program "{dr_program_name}" and Date Range "{date_range}"')
def step_impl(context, dr_program_name, date_range):
    br = context.browser
    br.find_element_by_link_text("Report").click()

    # Redirect to Report Page
    assert br.current_url.endswith('/report/') != -1
    br.find_element_by_name("dr_program").send_keys(dr_program_name)
    br.find_element_by_name("datefilter").send_keys(date_range)
    br.find_element_by_name("filter_button").click()


@then('I should see DR Event name "{dr_program_name}"')
def step_impl(context, dr_program_name):
    br = context.browser
    time.sleep(5)
    lst = br.find_elements_by_xpath("//*[@id='filterTable']//tbody//td")
    dr_events = []
    for i in range(0, int(len(lst) / 6)):
        dr_events += [lst[i * 6].text]
        print(lst[i * 6].text)
    assert dr_program_name in dr_events


@then('I should only see DR Event name "{dr_program_name}"')
def step_impl(context, dr_program_name):
    br = context.browser
    time.sleep(20)
    lst = br.find_elements_by_xpath("//*[@id='filterTable']//tbody//td")
    time.sleep(10)
    dr_events = []
    for i in range(0, int(len(lst) / 6)):
        dr_events += [lst[i * 6].text]
    for item in dr_events:
        assert item == dr_program_name
