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
from vtn.tests.factories import UserFactory


@given('a valid user "{username}" with password "{password}"')
def step_impl(context, username, password):

    # Creates a dummy user for our tests (user is not authenticated at this point)
    u = UserFactory(username=username)
    u.set_password(password)

    # Don't omit to call save() to insert object in database
    u.save()


@when('I login with username "{username}" and password "{password}"')
def step_impl(context, username, password):
    br = context.browser
    br.get(context.base_url + '/vtn/login/')

    assert br.find_element_by_tag_name('h1').text == "Utility OpenADR Application"

    # Checks for Cross-Site Request Forgery protection input
    assert br.find_element_by_name('csrfmiddlewaretoken').is_enabled()

    # Fill login form and submit it (valid version)
    br.find_element_by_name('username').send_keys(username)
    br.find_element_by_name('password').send_keys(password)
    br.find_element_by_name('login').click()


@then('I am redirected to the home page')
def step_impl(context):
    br = context.browser

    assert br.find_element_by_tag_name('h1').text == "Utility OpenADR Application"

    # Checks success status
    assert br.current_url.endswith('/vtn/home/')


@then('I should see some error message at login page')
def step_impl(context):
    br = context.browser

    assert br.find_element_by_tag_name('h1').text == "Utility OpenADR Application"

    # Checks status
    assert br.current_url.endswith('/vtn/login/')
    error = br.find_element_by_css_selector('ul.errorlist.nonfield')
    assert error.text.find("enter a correct username and password") != -1


@then('I log out')
def step_impl(context):
    br = context.browser

    br.find_element_by_partial_link_text("Welcome").click()
    br.find_element_by_link_text('Logoff').click()

    assert br.current_url.endswith('/vtn/logout/')


def change_password(br, old_password, new_password):
    br.find_element_by_name("old_password").send_keys(old_password)
    br.find_element_by_name("new_password1").send_keys(new_password)
    br.find_element_by_name("new_password2").send_keys(new_password)
    br.find_element_by_name("change_password").click()
    return br


@when('I change password')
def step_impl(context):
    br = context.browser

    print(br.current_url)

    br.find_element_by_partial_link_text("Welcome").click()
    br.find_element_by_link_text("Change password").click()

    assert br.current_url.endswith('/vtn/password_change/')

    # Password is too short
    br = change_password(br, "bar", "barr")

    error = br.find_element_by_class_name("errorlist").text
    assert error.find("password is too short") != -1

    # Password is too common and entirely numeric
    br = change_password(br, "bar", "123456789")

    error = br.find_element_by_class_name("errorlist").text
    assert error.find("password is too common") != -1 and \
           error.find("password is entirely numeric") != -1

    # Successful password change
    br = change_password(br, "bar", "kisensum")


@when('I click on Overview')
def step_impl(context):
    br = context.browser
    br.find_element_by_link_text("Overview").click()
    context.execute_steps('''then I am redirected to the home page''')

