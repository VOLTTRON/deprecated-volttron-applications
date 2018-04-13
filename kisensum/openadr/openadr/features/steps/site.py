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


@when('I add site with customer name "{name}", site name "{site_name}", site ID "{site_id}", VEN Name "{ven_name}", '
      'Site Location Code "{loc_code}", IPV6 add "{ipv6_addr}", Site Add "{addr}", '
      'city "{city}", state "{state}", zip "{zip}", contact name "{contact}", phone number "{phone}"')
def step_impl(context, name, site_name, site_id, ven_name, loc_code,
              ipv6_addr, addr, city, state, zip, contact, phone):
    br = context.browser
    br.find_element_by_link_text("Admin").click()

    # Redirect to Admin Page
    assert br.current_url.endswith('/admin/') != -1
    assert br.find_element_by_xpath("//div[@id='content']/h1[1]").text == "Site administration"

    br.find_element_by_link_text("Sites").click()
    assert br.current_url.endswith('/admin/vtn/site/') != -1

    br.find_element_by_link_text("ADD SITE").click()
    assert br.current_url.endswith('/admin/vtn/site/add') != -1

    br.find_element_by_name("customer").send_keys(name)
    br.find_element_by_name("site_name").send_keys(site_name)
    br.find_element_by_name("site_id").send_keys(site_id)
    br.find_element_by_name("ven_name").send_keys(ven_name)
    br.find_element_by_name("site_location_code").send_keys(loc_code)
    br.find_element_by_name("ip_address").send_keys(ipv6_addr)
    br.find_element_by_name("site_address1").send_keys(addr)
    br.find_element_by_name("city").send_keys(city)
    br.find_element_by_name("state").send_keys(state)
    br.find_element_by_name("zip").send_keys(zip)
    br.find_element_by_name("contact_name").send_keys(contact)
    br.find_element_by_name("phone_number").send_keys(phone)

    br.find_element_by_name("_save").click()
    assert br.current_url.endswith('/admin/vtn/site/') != -1


@when('I create a site with customer name "{name}", site name "{site_name}", site ID "{site_id}", VEN Name "{ven_name}", '
      'Site Location Code "{loc_code}", IPV6 add "{ipv6_addr}", Site Add "{addr}", city "{city}", '
      'state "{state}", zip "{zip}", contact name "{contact}", phone number "{phone}"')
def step_impl(context, name, site_name, site_id, ven_name, loc_code,
              ipv6_addr, addr, city, state, zip, contact, phone):
    #TODO: Add clicking the button and filling in the fields
    br = context.browser
    br.find_element_by_link_text(name).click()
    assert br.current_url.find('/vtn/customer-detail/') != -1
    assert br.find_element_by_name("name").get_attribute('value') == name

    br.find_element_by_link_text("Create New Site").click()
    assert br.current_url.find('/vtn/site/create/') != -1

    # # Redirect to Admin Page
    # br.find_element_by_name("customer").send_keys(name)
    br.find_element_by_name("site_name").send_keys(site_name)
    br.find_element_by_name("site_id").send_keys(site_id)
    br.find_element_by_name("site_location_code").send_keys(loc_code)
    br.find_element_by_name("ven_name").send_keys(ven_name)
    br.find_element_by_name("ip_address").send_keys(ipv6_addr)
    br.find_element_by_name("site_address1").send_keys(addr)
    br.find_element_by_name("city").send_keys(city)
    br.find_element_by_name("state").send_keys(state)
    br.find_element_by_name("zip").send_keys(zip)
    br.find_element_by_name("contact_name").send_keys(contact)
    br.find_element_by_name("phone_number").send_keys(phone)

    br.find_element_by_xpath("/html/body/div[@id='container']/div[@class='container']/form/"
                             "div[@class='row justify-content-center top-buffer ']/div[@class='col-4 col-sm-offset-2']/"
                             "button[@class='btn btn-primary btn-lg']").click()
    assert br.current_url.find('/vtn/customer-detail/') != -1


@when('I delete the site with name "{name}"')
def step_impl(context, name):
    br = context.browser
    br.find_element_by_link_text("Admin").click()
    br.find_element_by_link_text("Sites").click()
    assert br.current_url.endswith('/admin/vtn/site/') != -1
    rows = []
    i = 1
    try:
        while True:
            rows += [br.find_element_by_class_name("row"+str(i))]
            i += 1
    except NoSuchElementException:
        pass
    for r in rows:
        if r.find_element_by_class_name("field-site_name").text == name:
            r.find_element_by_name("_selected_action").click()
    br.find_element_by_name("action").send_keys("Delete selected sites")
    br.find_element_by_name("index").click()
    br.find_element_by_name("confirm_action").click()


@then('I should see no site with name "{site_name}" from customer "{name}", DR Program "{dr_program_name}"')
def step_impl(context, site_name, name, dr_program_name):
    br = context.browser
    br.find_element_by_link_text("Admin").click()

    # Redirect to Admin Page
    assert br.current_url.endswith('/admin/') != -1
    assert br.find_element_by_xpath("//div[@id='content']/h1[1]").text == "Site administration"

    br.find_element_by_link_text("Sites").click()
    assert br.current_url.endswith('/admin/vtn/site/') != -1

    try:
        print(br.find_element_by_link_text(name))
        raise AssertionError("Could not delete site.")
    except NoSuchElementException:
        pass

    br.find_element_by_link_text("Overview").click()
    br.find_element_by_link_text(name).click()
    try:
        print(br.find_element_by_link_text(site_name))
        raise AssertionError("Could not delete site.")
    except NoSuchElementException:
        pass

    br.find_element_by_link_text("Admin").click()
    br.find_element_by_link_text("DR Programs").click()
    br.find_element_by_link_text(dr_program_name).click()
    try:
        lst = br.find_element_by_xpath("/html/body[@class=' app-vtn model-drprogram change-form']/div[@id='container']/"
                                     "div[@id='container']/div[@class='row justify-content-center']/div[@id='content']/"
                                     "div[@id='content-main']/form[@id='drprogram_form']/div/fieldset[@class='module aligned ']"
                                     "/div[@class='form-row field-sites']/div/div[@class='related-widget-wrapper']/"
                                     "div[@class='selector']/div[@class='selector-chosen']/select[@id='id_sites_to']/option")
        for i in range(1,len(lst)):
            assert lst[i].text != "(" + name + ") " + site_name
    except NoSuchElementException as err:
        pass



@then('I should see a site with customer name "{name}", site name "{site_name}", site ID "{site_id}"')
def step_impl(context, name, site_name, site_id):
    br = context.browser
    br.find_element_by_link_text("Admin").click()

    # Redirect to Admin Page
    assert br.current_url.endswith('/admin/') != -1
    assert br.find_element_by_xpath("//div[@id='content']/h1[1]").text == "Site administration"

    br.find_element_by_link_text("Sites").click()
    assert br.current_url.endswith('/admin/vtn/site/') != -1
    br.find_element_by_link_text(name).click()
    assert br.current_url.endswith('/admin/vtn/site/.*/change/') != -1

    assert br.find_element_by_name("site_name").get_attribute('value') == site_name
    print(site_id, br.find_element_by_name("site_id").get_attribute('value'))
    assert br.find_element_by_name("site_id").get_attribute('value') == site_id
