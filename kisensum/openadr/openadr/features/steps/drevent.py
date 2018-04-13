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


#TODO: Add test cases for editting DR event in OVERVIEW page
#TODO: Editting DR event by taking out one or more sites/adding more sites to the list of sites in DR event and test it.

@when('I add a DR Event with DR program "{dr_program_name}", customer "{name}", site "{site_name}", noti date "{noti_date}", noti time "{noti_time}", start date "{start_date}", start time "{start_time}", end date "{end_date}", end time "{end_time}"')
def step_impl(context,  dr_program_name, name, site_name, noti_date, noti_time, start_date, start_time, end_date, end_time):
    br = context.browser
    assert br.current_url.endswith('/vtn/home/') != -1

    br.find_element_by_link_text('Add DR Event').click()
    assert br.current_url.endswith('/vtn/dr_event/') != -1
    print(br.find_element_by_name("sites").get_attribute('value'))

    br.find_element_by_name("dr_program").send_keys(dr_program_name)
    time.sleep(5);
    br.find_element_by_name("sites").send_keys(site_name)

    # Clear existing values
    br.find_element_by_name("scheduled_notification_time_0").clear()
    br.find_element_by_name("scheduled_notification_time_1").clear()
    br.find_element_by_name("start_0").clear()
    br.find_element_by_name("start_1").clear()
    br.find_element_by_name("end_0").clear()
    br.find_element_by_name("end_1").clear()

    br.find_element_by_name("scheduled_notification_time_0").send_keys(noti_date)
    br.find_element_by_name("scheduled_notification_time_1").send_keys(noti_time)
    br.find_element_by_name("start_0").send_keys(start_date)
    br.find_element_by_name("start_1").send_keys(start_time)
    br.find_element_by_name("end_0").send_keys(end_date)
    br.find_element_by_name("end_1").send_keys(end_time)

    br.find_element_by_name("save").click()

    context.execute_steps('''then I am redirected to the home page''')


@when('I add a DR Event with DR program "{dr_program_name}", customer "{name}", with all sites, noti date "{noti_date}", noti time "{noti_time}", start date "{start_date}", start time "{start_time}", end date "{end_date}", end time "{end_time}"')
def step_impl(context,  dr_program_name, name, noti_date, noti_time, start_date, start_time, end_date, end_time):
    br = context.browser
    assert br.current_url.endswith('/vtn/home/') != -1

    br.find_element_by_link_text('Add DR Event').click()
    assert br.current_url.endswith('/vtn/dr_event/') != -1
    print(br.find_element_by_name("sites").get_attribute('value'))

    br.find_element_by_name("dr_program").send_keys(dr_program_name)
    time.sleep(5);

    # Clear existing values
    br.find_element_by_name("scheduled_notification_time_0").clear()
    br.find_element_by_name("scheduled_notification_time_1").clear()
    br.find_element_by_name("start_0").clear()
    br.find_element_by_name("start_1").clear()
    br.find_element_by_name("end_0").clear()
    br.find_element_by_name("end_1").clear()

    br.find_element_by_name("scheduled_notification_time_0").send_keys(noti_date)
    br.find_element_by_name("scheduled_notification_time_1").send_keys(noti_time)
    br.find_element_by_name("start_0").send_keys(start_date)
    br.find_element_by_name("start_1").send_keys(start_time)
    br.find_element_by_name("end_0").send_keys(end_date)
    br.find_element_by_name("end_1").send_keys(end_time)

    br.find_element_by_name("save").click()

    # how to figure out which DR Event was just created?

    print("There are {} DR Events".format(str(DREvent.objects.filter(dr_program__name="dr_program_test").count())))

    context.execute_steps('''then I am redirected to the home page''')


@when('I cancel a DR Event with DR program "{dr_program_name}"')
def step_impl(context, dr_program_name):
    br = context.browser
    assert br.current_url.endswith('/vtn/home/') != -1

    br.find_element_by_link_text(dr_program_name).click()
    assert br.current_url.endswith('/vtn/dr_event/edit/.*') != -1
    br.find_element_by_id("cancel_event").click()
    br.find_element_by_link_text("Cancel").click()
    assert br.current_url.endswith('/vtn/home/') != -1


@when('I edit DR Event "{dr_program_name}" by deselecting site "{site_name}"')
def step_impl(context, dr_program_name, site_name):
    br = context.browser

    br.find_element_by_link_text("Overview").click()
    assert br.current_url.endswith("vtn/home/") != -1

    br.find_element_by_link_text(dr_program_name).click()
    select = Select(br.find_element_by_name('sites'))
    select.deselect_by_visible_text(site_name)
    print(site_name)
    # all_selected_options = select.all_selected_options
    # selected_texts = [option.text for option in all_selected_options]
    # select.deselect_all()
    # for text in selected_texts:
    #     if text != site_name:
    #         select.select_by_visible_text(text)
    br.find_element_by_name("Save").click()


@when('I edit DR Event "{dr_program_name}" by adding site "{site_name}"')
def step_impl(context, dr_program_name, site_name):
    br = context.browser

    br.find_element_by_link_text("Overview").click()
    assert br.current_url.endswith("vtn/home/") != -1

    br.find_element_by_link_text(dr_program_name).click()
    select = Select(br.find_element_by_name('sites'))
    select.select_by_visible_text(site_name)
    br.find_element_by_name("Save").click()


@then('I should see no DR event with DR program "{dr_program_name}"')
def step_impl(context, dr_program_name):
    br = context.browser
    br.find_element_by_link_text("Overview").click()
    assert br.current_url.endswith("/vtn/home/") != -1

    lst = br.find_elements_by_xpath("//*[@id='eventTable']//tbody//td")
    found = False
    for i in range(int(len(lst) / 6)):
        if lst[i * 6].text == dr_program_name:
            found = True
            assert lst[i * 6 + 5].text == "Cancelled"
            break

    assert found == True

    br.find_element_by_link_text("Admin").click()
    br.find_element_by_link_text("DR Events").click()
    br.find_element_by_link_text(dr_program_name).click()
    assert br.find_element_by_name("deleted").is_selected() == True


@then('I should see a DR event of DR program "{dr_program_name}", site "{site_name}", noti date "{noti_date}", noti time "{noti_time}"')
def step_impl(context, dr_program_name, site_name, noti_date, noti_time):
    br = context.browser
    assert br.current_url.endswith('/vtn/home/') != -1

    br.find_element_by_link_text(dr_program_name).click()
    assert br.current_url.endswith('/vtn/dr_event/edit/.*') != -1

    assert br.find_element_by_name("dr_program").get_attribute('value') == "1"
    assert br.find_element_by_name("scheduled_notification_time_0").get_attribute('value') == noti_date
    assert br.find_element_by_name("scheduled_notification_time_1").get_attribute('value') == noti_time
