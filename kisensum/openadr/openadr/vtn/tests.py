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
from vtn.models import DREvent, DRProgram, Customer, Site, SiteEvent, Telemetry
from django.test import TestCase, RequestFactory
from django.utils import timezone
import pytest
import factory
import names
import random
from faker import Faker
from datetime import datetime, timedelta
import string
from vtn.views import *


fake = Faker()

# class CustomerFactory(factory.django.DjangoModelFactory):
#     class Meta:
#         model = 'vtn.Customer'
#
#     name = factory.LazyAttribute(lambda o: names.get_full_name())
#     utility_id = factory.LazyAttribute(lambda o: random.randint(1000000, 9999999))
#     contact_name = factory.LazyAttribute(lambda o: names.get_full_name())
#     phone_number = factory.LazyAttribute(lambda o: random.randint(1000000000, 9999999999))
#
#
# class SiteFactory(factory.django.DjangoModelFactory):
#     class Meta:
#         model = 'vtn.Site'
#
#     site_name = factory.LazyAttribute(lambda o: ''.join(fake.words(nb=2)))
#     site_id = factory.Sequence(lambda n: 100 + n)
#     site_location_code = factory.Sequence(lambda n: 200 + n)
#     ip_address = factory.LazyAttribute(lambda n: fake.ipv4())
#     ven_name = factory.Sequence(lambda n: "vtn{}".format(n))
#     site_address1 = factory.LazyAttribute(lambda o: fake.street_address())
#     city = factory.LazyAttribute(lambda o: fake.city())
#     state = factory.LazyAttribute(lambda o: fake.state_abbr())
#     zip = factory.LazyAttribute(lambda o: fake.zipcode())
#     contact_name = factory.LazyAttribute(lambda o: names.get_full_name())
#     phone_number = factory.LazyAttribute(lambda o: random.randint(100000000, 999999999))
#     online = factory.LazyAttribute(lambda o: fake.boolean())
#     reporting_status = factory.LazyAttribute(lambda o: fake.boolean())
#
#     @factory.lazy_attribute
#     def customer(self):
#         customers = Customer.objects.all()
#         return customers[random.randint(0, len(customers)-1)]
#
#
#     @factory.lazy_attribute
#     def ven_id(self):
#         # example = '919a1dfa088fe14b79f9'
#         # pattern = 100-999 + letter + 1-10 + three letters + 0 + 10-99 + two letters + 10-99 + letter
#         # + 10-99 + letter + 1-9
#         letters = string.ascii_lowercase
#         return (str(random.randint(100, 999)) +
#                random.choice(letters) +
#                str(random.randint(1, 9)) +
#                random.choice(letters) + random.choice(letters) + random.choice(letters) +
#                str(0) +
#                str(random.randint(10, 99)) +
#                random.choice(letters) + random.choice(letters) +
#                str(random.randint(10, 99)) +
#                random.choice(letters))
#
#
# class DRProgramFactory(factory.django.DjangoModelFactory):
#     class Meta:
#         model = 'vtn.DRProgram'
#
#     name = factory.Sequence(lambda n: "drprogram{}".format(n))
#


class SimpleTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='nate', email='nate@...', password='secret')

    def test_details(self):
        request = self.factory.get('/site_detail')

        request.user = self.user
        response = CreateSiteView.as_view(request)
        self.assertEqual(response.status_code, 200)


