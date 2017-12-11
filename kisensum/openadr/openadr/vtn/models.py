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

from django.db import models
from django.core.urlresolvers import reverse, reverse_lazy
from django.contrib.auth.models import User


class Customer(models.Model):
    name = models.CharField('Name', db_index=True, max_length=100, unique=True)
    utility_id = models.CharField('Utility ID', max_length=100, unique=True)
    contact_name = models.CharField('Contact Name', max_length=100, blank=True)
    phone_number = models.CharField('Phone Number', max_length=13, null=True)

    def get_absolute_url(self):
        return reverse_lazy('vtn:customer_detail', kwargs={'pk': self.pk})

    def __str__(self):
        return "{}".format(self.name)

    def sites(self):
        return self.site_set.all()


class DRProgram(models.Model):

    class Meta:
        verbose_name_plural = "DR Programs"
        verbose_name = "DR Program"

    name = models.CharField('Program Name', max_length=100, unique=True)
    sites = models.ManyToManyField('Site', blank=True)

    def __str__(self):
        return self.name


class Site(models.Model):
    customer = models.ForeignKey(Customer)
    site_name = models.CharField('Site Name', max_length=100)
    site_id = models.CharField('Site ID', max_length=100)
    ven_id = models.CharField('VEN ID', max_length=100, unique=True, blank=True)
    ven_name = models.CharField('VEN Name', max_length=100, unique=True)
    site_location_code = models.CharField('Site Location Code', max_length=100)
    ip_address = models.CharField('IP address', max_length=100, blank=True)
    site_address1 = models.CharField('Address Line 1', max_length=100)
    site_address2 = models.CharField('Address Line 2', max_length=100, blank=True, null=True)
    city = models.CharField('City', max_length=100)
    state = models.CharField('State (abbr.)', max_length=2)
    zip = models.CharField('Zip', max_length=5)
    contact_name = models.CharField('Contact Name', max_length=100)
    phone_number = models.CharField('Phone Number', max_length=13)
    online = models.BooleanField(default=False)
    last_status_time = models.DateTimeField('Last Status Time', blank=True, null=True)

    def get_absolute_url(self):
        return reverse_lazy('vtn:customer_detail', kwargs={'pk': self.customer.pk})

    def __str__(self):
        return "({}) {}".format(self.customer.name, self.site_name)


class DREvent(models.Model):

    class Meta:
        verbose_name_plural = "DR Events"
        verbose_name = "DR Event"

    STATUS_CHOICES = (
        ('scheduled', 'scheduled'),
        ('far', 'far'),
        ('near', 'near'),
        ('active', 'active'),
        ('completed', 'completed'),
        ('cancelled', 'cancelled'),
        ('unresponded', 'unresponded')
    )

    dr_program = models.ForeignKey(DRProgram)
    scheduled_notification_time = models.DateTimeField('Scheduled Notification Time')
    start = models.DateTimeField('Event Start')
    end = models.DateTimeField('Event End')
    sites = models.ManyToManyField(Site, through='SiteEvent', related_name='Sites1')
    modification_number = models.IntegerField('Modification Number', default=0)
    status = models.CharField('Event Status', max_length=100, choices=STATUS_CHOICES, default='far')
    last_status_time = models.DateTimeField('Last Status Time', blank=True, null=True)
    superseded = models.BooleanField('Superseded', default=False)
    event_id = models.IntegerField('Event ID')
    deleted = models.BooleanField(default=False)

    def __str__(self):
        return "{}: starts at {}. Ends at {}".format(self.dr_program.name, self.start, self.end)

    def get_absolute_url(self):
        return reverse_lazy('vtn:home')


class SiteEvent(models.Model):

    class Meta:
        verbose_name_plural = "Site Events"

    STATUS_CHOICES = (
        ('scheduled', 'scheduled'),
        ('far', 'far'),
        ('near', 'near'),
        ('active', 'active'),
        ('completed', 'completed'),
        ('cancelled', 'cancelled'),
        ('unresponded', 'unresponded')
    )

    OPT_IN_CHOICES = (
        ('optIn', 'optIn'),
        ('optOut', 'optOut'),
        ('none', 'Neither')
    )

    VEN_STATUS_CHOICES = (
        ('not_told', 'not_told'),
        ('told', 'told'),
        ('acknowledged', 'acknowledged')
    )

    dr_event = models.ForeignKey(DREvent)
    status = models.CharField(max_length=100, choices=STATUS_CHOICES, default='scheduled')
    notification_sent_time = models.DateTimeField('Notification Sent Time', blank=True, null=True)
    last_status_time = models.DateTimeField('Last Status Time')
    modification_number = models.IntegerField('Modification Number', default=0)
    opt_in = models.CharField(max_length=100, choices=OPT_IN_CHOICES, default='none')
    ven_status = models.CharField(max_length=100, choices=VEN_STATUS_CHOICES, default='not_told')
    last_opt_in = models.DateTimeField('Last opt-in', blank=True, null=True)
    site = models.ForeignKey(Site)
    previous_version = models.ForeignKey('self', blank=True, null=True)
    deleted = models.BooleanField(default=False)


class Telemetry(models.Model):

    class Meta:
        verbose_name_plural = "Telemetry"

    site = models.ForeignKey(Site)
    created_on = models.DateTimeField(auto_created=True)
    reported_on = models.DateTimeField(null=True, blank=True)
    baseline_power_kw = models.FloatField('Baseline Power (kw)', blank=True, null=True)
    measured_power_kw = models.FloatField('Measured Power (kw)', blank=True, null=True)


class Report(models.Model):

    REPORT_STATUS_CHOICES = (
        ('active', 'active'),
        ('cancelled', 'cancelled'),
        ('cancelled_requested', 'cancelled_requested'),
    )

    report_status = models.CharField('Report Status', max_length=100, choices=REPORT_STATUS_CHOICES, default='active')
    report_request_id = models.CharField('Report Request ID', max_length=100, blank=True, null=True, unique=True)
    ven_id = models.CharField('VEN ID', max_length=100, blank=True)
