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


@given('Login with username "{username}" and password "{password}"')
def step_impl(context, username, password):
    context.execute_steps('''
                          given a valid user "%s" with password "%s"
                          when I login with username "%s" and password "%s"
                          ''' % (username, password, username, password))


@given('Login with admin')
def step_impl(context):
    # Creates a dummy user for our tests (user is not authenticated at this point)
    u = AdminFactory()
    u.set_password("admin")
    u.save()
    context.execute_steps(''' 
                          when I login with username "admin" and password "admin"
                          ''')


@when('I add Customer name "{username}", utility id "{id}", contact name "{contact}" and phone number "{phone}"')
def step_impl(context, username, id, contact, phone):
    br = context.browser
    br.find_element_by_link_text("Add Customer").click()

    # Go to Add Customer page
    assert br.current_url.endswith('/vtn/customer/add/')

    br.find_element_by_name("name").send_keys(username)
    br.find_element_by_name("utility_id").send_keys(id)
    br.find_element_by_name("contact_name").send_keys(contact)
    br.find_element_by_name("phone_number").send_keys(phone)
    br.find_element_by_name("save").click()

    # # Go back to homepage
    # context.execute_steps('''then I am redirected to the home page''')


@when('I delete customer "{name}"')
def step_impl(context, name):
    br = context.browser
    br.find_element_by_link_text("Admin").click()

    # Redirect to Admin Page
    assert br.current_url.endswith('/admin/') != -1
    assert br.find_element_by_xpath("//div[@id='content']/h1[1]").text == "Site administration"

    br.find_element_by_link_text("Customers").click()
    assert br.current_url.endswith('/admin/vtn/customer/') != -1

    # Go to Customers Detail page
    br.find_element_by_link_text(name).click()
    assert br.current_url.endswith('/change/') != -1

    # Delete the customer
    br.find_element_by_link_text('Delete').click()
    assert br.current_url.endswith('/delete/') != -1

    br.find_element_by_xpath("//input[@type='submit']").click()

    assert br.current_url.endswith('/admin/vtn/customer/') != -1


@when('I click on customer "{name}"')
def step_impl(context, name):
    br = context.browser

    assert br.current_url.endswith('/vtn/home/')
    user = br.find_element_by_link_text(name)

    # Check for customer detail
    user.click()
    assert br.current_url.find('/vtn/customer-detail/') != -1
    assert br.find_element_by_name("name").get_attribute('value') == name


@when('I change the name to "{new_name}" and id to "{new_id}" and click "save" and "Overview"')
def step_impl(context, new_name, new_id):
    br = context.browser

    save_button = br.find_element_by_name("Save")
    assert br.current_url.find('/vtn/customer-detail/') != -1
    br.find_element_by_name("name").clear()
    br.find_element_by_name("name").send_keys(new_name)
    br.find_element_by_name("utility_id").clear()
    br.find_element_by_name("utility_id").send_keys(new_id)

    save_button.click()
    assert br.current_url.find('/vtn/customer-detail/') != -1

    br.find_element_by_link_text("Overview").click()


@then('I should see a Customer "{username}" with utility id "{id}"')
def step_impl(context, username, id):
    br = context.browser
    # Should be able to find 'foobar' customer name in homepage
    c = br.find_element_by_link_text(username)

    # Check for customer detail
    c.click()
    assert br.current_url.find('/vtn/customer-detail/') != -1
    assert br.find_element_by_name("name").get_attribute('value') == username
    assert br.find_element_by_name("utility_id").get_attribute('value') == id


@then('I should not see Customer "{username}" nor the site "{site_name}"')
def step_impl(context, username, site_name):
    br = context.browser

    br.find_element_by_link_text("Overview").click()
    assert br.current_url.endswith('/vtn/home/')

    assert br.find_elements_by_xpath("//table[@id='customerTable']/tbody/tr/td") == []
    br.find_element_by_link_text("Admin").click()
    br.find_element_by_link_text("Sites").click()
    try:
        br.find_element_by_link_text(site_name).click()
        raise AssertionError("Could not delete the site related to {}".format(username))
    except NoSuchElementException:
        pass


@then('I should see error with utility already exists')
def step_impl(context):
    br = context.browser
    error_mess = "* Customer with this Utility ID already exists."

    assert br.current_url.endswith('/vtn/customer/add/')
    assert br.find_element_by_name("customer_error").text == error_mess
