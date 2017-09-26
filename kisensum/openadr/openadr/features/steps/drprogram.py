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
from selenium.webdriver.support.ui import Select


@when('I add a DR Program name "{dr_program_name}"')
def step_impl(context, dr_program_name):
    br = context.browser
    br.find_element_by_link_text("Admin").click()

    # Redirect to Admin Page
    assert br.current_url.endswith('/admin/') != -1
    assert br.find_element_by_xpath("//div[@id='content']/h1[1]").text == "Site administration"

    br.find_element_by_link_text("DR Programs").click()
    assert br.current_url.endswith('/admin/vtn/drprogram/') != -1

    br.find_element_by_link_text("ADD DR PROGRAM").click()
    assert br.current_url.endswith('/admin/vtn/drprogram/add') != -1

    br.find_element_by_name("name").send_keys(dr_program_name)

    br.find_element_by_name("_save").click()
    assert br.current_url.endswith('/admin/vtn/drprogram/') != -1


@when('I add a DR Program name "{dr_program_name}" with all sites')
def step_impl(context, dr_program_name):
    br = context.browser
    br.find_element_by_link_text("Admin").click()

    # Redirect to Admin Page
    assert br.current_url.endswith('/admin/') != -1
    assert br.find_element_by_xpath("//div[@id='content']/h1[1]").text == "Site administration"

    br.find_element_by_link_text("DR Programs").click()
    assert br.current_url.endswith('/admin/vtn/drprogram/') != -1

    br.find_element_by_link_text("ADD DR PROGRAM").click()
    assert br.current_url.endswith('/admin/vtn/drprogram/add') != -1

    br.find_element_by_name("name").send_keys(dr_program_name)
    br.find_element_by_link_text("Choose all").click()

    br.find_element_by_name("_save").click()
    assert br.current_url.endswith('/admin/vtn/drprogram/') != -1


@when('I click on DR Program name "{dr_program_name}"')
def step_impl(context, dr_program_name):
    br = context.browser
    br.find_element_by_link_text(dr_program_name).click()
    assert br.current_url.endswith('/admin/vtn/drprogram/.*/change/') != -1


@when('I change DR Program name to "{name}"')
def step_impl(context, name):
    br = context.browser
    br.find_element_by_name("name").clear()
    br.find_element_by_name("name").send_keys(name)
    br.find_element_by_name("_save").click()
    assert br.current_url.endswith('/admin/vtn/drprogram/') != -1


@when('I delete the DR Program name "{dr_program_name}"')
def step_impl(context, dr_program_name):
    br = context.browser
    br.find_element_by_link_text("Admin").click()
    br.find_element_by_link_text("DR Programs").click()
    rows = []
    i = 1
    try:
        while True:
            rows += [br.find_element_by_class_name("row"+str(i))]
            i += 1
    except NoSuchElementException:
        pass
    for r in rows:
        if r.find_element_by_class_name("field-name").text == dr_program_name:
            r.find_element_by_name("_selected_action").click()
    br.find_element_by_name("action").send_keys("Delete selected sites")
    br.find_element_by_name("index").click()
    br.find_element_by_name("confirm_action").click()


@then('I should see no DR program name "{dr_program_name}" from customer "{name}", site "{site_name}"')
def step_impl(context, dr_program_name, name, site_name):
    br = context.browser
    br.find_element_by_link_text("Admin").click()

    # Redirect to Admin Page
    assert br.current_url.endswith('/admin/') != -1
    assert br.find_element_by_xpath("//div[@id='content']/h1[1]").text == "Site administration"

    br.find_element_by_link_text("DR Programs").click()
    assert br.current_url.endswith('/admin/vtn/drprogram/') != -1

    try:
        print(br.find_element_by_link_text(dr_program_name))
        raise AssertionError("Could not delete dr_program.")
    except NoSuchElementException:
        pass

    br.find_element_by_link_text("Admin").click()
    br.find_element_by_link_text("DR Events").click()
    assert br.current_url.endswith('/admin/vtn/drevent/') != -1
    try:
        print(br.find_element_by_link_text(dr_program_name))
        raise AssertionError("Could not delete dr_program.")
    except NoSuchElementException:
        pass

    br.find_element_by_link_text("Overview").click()
    br.find_element_by_link_text(name).click()
    br.find_element_by_link_text(site_name).click()
    select = Select(br.find_element_by_name('dr_programs'))
    dr_program_options = [option.text for option in select.all_selected_options]
    assert dr_program_name not in dr_program_options


@then('I should see a DR program name "{dr_program_name}"')
def step_impl(context, dr_program_name):
    br = context.browser
    br.find_element_by_link_text("Admin").click()
    br.find_element_by_link_text("DR Programs").click()

    br.find_element_by_link_text(dr_program_name).click()
    assert br.current_url.endswith('/admin/vtn/drprogram/.*/change/') != -1
    br.find_element_by_link_text("Overview").click()

    context.execute_steps('''then I am redirected to the home page''')
