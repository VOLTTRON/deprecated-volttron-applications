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

from django import forms
from .models import *
from django.core.exceptions import ValidationError
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.admin.widgets import AdminSplitDateTime
from django.utils import timezone


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        exclude = []


class SiteForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(SiteForm, self).__init__(*args, **kwargs)
        self.fields['dr_programs'] = forms.ModelMultipleChoiceField(queryset=DRProgram.objects.all(), required=False)
        # self.fields['ven_id'] = forms.CharField(required=False)
        # self.fields['ven_name'] = forms.CharField(required=False)

    class Meta:
        model = Site
        exclude = []


class DREventForm(forms.ModelForm):
    scheduled_notification_time = forms.SplitDateTimeField(widget=AdminSplitDateTime())
    start = forms.SplitDateTimeField(widget=AdminSplitDateTime())
    end = forms.SplitDateTimeField(widget=AdminSplitDateTime())

    class Meta:
        model = DREvent
        fields = '__all__'
        widgets = {'status': forms.HiddenInput(),
                   'modification_number': forms.HiddenInput(),
                   'last_status_time': forms.HiddenInput(),
                   'sites': FilteredSelectMultiple('sites', False,)}

    def __init__(self, *args, **kwargs):
        super(DREventForm, self).__init__(*args, **kwargs)
        self.fields['modification_number'].required = False
        self.fields['status'].required = False
        self.fields['last_status_time'].required = False
        self.fields['event_id'].required = False

    def clean(self):
        if self._errors:
            return self._errors
        cleaned_data = super().clean()
        try:
            scheduled_notification_time = cleaned_data['scheduled_notification_time']
            start = cleaned_data['start']
            end = cleaned_data['end']
        except KeyError:
            raise ValidationError('Please enter valid date and time')
        if start > end:
            raise ValidationError('Start time must precede end time')
        if scheduled_notification_time > start:
            raise ValidationError('Notification time must precede start time')
        if scheduled_notification_time < timezone.now() or \
                start < timezone.now() or  \
                end < timezone.now():
            raise ValidationError('All times must be in the future')


class DREventUpdateForm(forms.ModelForm):
    scheduled_notification_time = forms.SplitDateTimeField(widget=AdminSplitDateTime())
    start = forms.SplitDateTimeField(widget=AdminSplitDateTime())
    end = forms.SplitDateTimeField(widget=AdminSplitDateTime())

    class Meta:
        model = DREvent
        fields = '__all__'
        widgets = {'status': forms.HiddenInput(),
                   'modification_number': forms.HiddenInput(),
                   'last_status_time': forms.HiddenInput(),
                   'sites': FilteredSelectMultiple('sites', False, )}

    def __init__(self, *args, **kwargs):
        super(DREventUpdateForm, self).__init__(*args, **kwargs)
        self.fields['modification_number'].required = False
        self.fields['status'].required = False
        self.fields['last_status_time'].required = False
        self.fields['event_id'].required = False

    # This clean method doesn't check the scheduled notification time, because
    # we should be able to change an event after said time has passed.
    def clean(self):
        if self._errors:
            return self._errors
        cleaned_data = super().clean()
        try:
            scheduled_notification_time = cleaned_data['scheduled_notification_time']
            start = cleaned_data['start']
            end = cleaned_data['end']
        except KeyError:
            raise ValidationError('Please enter valid date and time')
        if start > end:
            raise ValidationError('Start time must precede end time')
        if scheduled_notification_time > start:
            raise ValidationError('Notification time must precede start time')
        if start < timezone.now() or end < timezone.now():
            raise ValidationError('All times must be in the future')


# For the export page
class DREventFormFilter(forms.ModelForm):

    dr_program = forms.ModelChoiceField(DRProgram.objects.order_by('name'), empty_label="All")

    class Meta:
        model = DREvent
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(DREventFormFilter, self).__init__(*args, **kwargs)
        self.fields['dr_program'].required = False


class DRProgramForm(forms.ModelForm):
    class Meta:
        model = DRProgram
        exclude = []


class DRProgramEditForm(forms.ModelForm):
    class Meta:
        model = DREvent
        fields = ['dr_program']


class CustomerSiteUpdateForm(forms.ModelForm):

    class Meta:
        exclude = []
        model = Site


# To choose a customer from the DR Event detail screen
class DREventCustomerDetailForm(forms.Form):

        customer = forms.ModelChoiceField(queryset=None, required=True, empty_label="--------- All ---------")


# To choose a customer from the DR Event detail screen
class DREventSiteDetailForm(forms.Form):

        site = forms.ModelChoiceField(queryset=None, required=True, empty_label="--------- All ---------")


# For the event update view
class DREventFilterForm(forms.ModelForm):

    scheduled_notification_time = forms.SplitDateTimeField(widget=AdminSplitDateTime())
    start = forms.SplitDateTimeField(widget=AdminSplitDateTime())
    end = forms.SplitDateTimeField(widget=AdminSplitDateTime())

    class Meta:
        exclude = []
        model = DREvent

    def __init__(self, *args, **kwargs):
        super(DREventFilterForm, self).__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        if instance and instance.pk:
            self.fields['dr_program'].widget.attrs['readonly'] = True


class CreateSiteForm(forms.ModelForm):

    class Meta:
        exclude = []
        model = Site


class TelemetryForm(forms.ModelForm):
    class Meta:
        model = Telemetry
        exclude = []
