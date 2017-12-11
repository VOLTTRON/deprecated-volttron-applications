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

import csv
from datetime import datetime, timedelta
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.db.models import Case, When, Count, Sum, Min
from django.db.models import Q, Avg
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.views.generic.edit import CreateView, UpdateView, DeleteView, ModelFormMixin
from .forms import *
from django.utils import timezone
from api.static_methods import *
from vtn.tasks import update_event_statuses
from collections import OrderedDict
from django.conf import settings


class CustomerCreate(CreateView):
    form_class = CustomerForm
    template_name = 'vtn/customer_create_form.html'
    success_url = reverse_lazy('vtn:home')


class CustomerUpdate(UpdateView):
    model = Customer
    success_url = reverse_lazy('vtn:home')
    fields = ['name', 'utility_id']


class DREventDelete(DeleteView):
    model = DREvent
    template_name = "vtn/dr_event_confirm_delete.html"


class CustomerDetailView(UpdateView):
    template_name = "vtn/customer_detail.html"
    model = Customer
    fields = '__all__'

    def get_context_data(self, **kwargs):
        context = super(CustomerDetailView, self).get_context_data(**kwargs)
        customer = Customer.objects.get(pk=(self.kwargs['pk']))
        context['sites'] = customer.site_set.all()
        context['customer'] = customer

        return context

    def post(self, request, *args, **kwargs):
        if 'delete-customer' in request.POST:
            Customer.objects.get(pk=self.kwargs['pk']).delete()
            return HttpResponseRedirect(reverse_lazy('vtn:home'))
        else:
            return super(CustomerDetailView, self).post(request, *args, **kwargs)


class SiteDetailView(UpdateView):

    template_name = "vtn/site_detail.html"
    model = Site
    form_class = SiteForm

    def get_context_data(self, **kwargs):
        context = super(SiteDetailView, self).get_context_data(**kwargs)
        context['customer'] = self.object.customer
        context['ven_id'] = self.object.ven_id
        context['ven_name'] = self.object.ven_name
        return context

    def get_form(self, form_class=None):
        form = super(SiteDetailView, self).get_form(form_class)
        form.fields["dr_programs"].queryset = DRProgram.objects.all().order_by('name')
        return form

    # Prepopulate dr programs with already chosen dr programs
    def get_initial(self):
        initial = super(SiteDetailView, self).get_initial()
        initial['dr_programs'] = self.object.drprogram_set.all()
        return initial

    def post(self, request, *args, **kwargs):
        if 'delete_site' in request.POST:
            Site.objects.get(pk=request.POST['pk']).delete()
            return HttpResponseRedirect(reverse_lazy('vtn:customer_detail',
                                                     kwargs={'pk': request.POST['customer']}))
        else:
            # If the DR Programs were altered
            if 'dr_programs' in request.POST:
                dr_programs = DRProgram.objects.all()
                for program in request.POST.getlist('dr_programs'):
                    dr_program = dr_programs.get(pk=program)
                    if dr_program not in self.get_object().drprogram_set.all():
                        dr_program.sites.add(self.get_object())
                        dr_program.save()
            return super(SiteDetailView, self).post(request, *args, **kwargs)


class CreateSiteView(CreateView):

    template_name = "vtn/create_site.html"
    model = Site
    form_class = SiteForm

    def get_initial(self):
        customer = Customer.objects.get(pk=self.kwargs['pk'])
        return {
            'customer': customer
        }

    def get_context_data(self, **kwargs):
        context = super(CreateSiteView, self).get_context_data(**kwargs)
        context['customer'] = Customer.objects.get(pk=self.kwargs['pk'])
        return context

    def get_success_url(self):
        return reverse_lazy('vtn:customer_detail',
                            kwargs={'pk': self.kwargs['pk']})

    def post(self, request, *args, **kwargs):
        form = SiteForm(request.POST)
        self.object = None

        if form.is_valid():
            self.object = form.save(commit=False)
            self.object.ven_id = get_new_ven_ID()
            self.object.save()

            if 'dr_programs' in request.POST:
                dr_programs = DRProgram.objects.all()
                for program in request.POST.getlist('dr_programs'):
                    dr_program = dr_programs.get(pk=program)
                    dr_program.sites.add(self.object)
                    dr_program.save()
            return HttpResponseRedirect(reverse_lazy('vtn:customer_detail',
                                                     kwargs={'pk': request.POST['customer']}))
        else:
            return super(CreateSiteView, self).form_invalid(form)


def get_new_ven_ID():
    all_sites = [int(s.ven_id) for s in Site.objects.all()]
    all_sites.sort()
    ven_id = str(all_sites[-1] + 1) if len(all_sites) > 0 else '0'
    return ven_id


def delete_dr_event(request, pk):
    """
    :param pk: the pk of the event that is being cancelled
    :param request: request object
    :return: redirects user to homepage
    """
    old_dr_event = DREvent.objects.get(pk=pk)
    new_dr_event = old_dr_event
    new_dr_event.pk = None
    new_dr_event.deleted = True
    new_dr_event.modification_number = old_dr_event.modification_number + 1
    new_dr_event.status = 'cancelled'
    new_dr_event.save()
    old_dr_event = DREvent.objects.get(pk=pk)
    old_dr_event.superseded = True
    old_dr_event.save()
    site_events = SiteEvent.objects.filter(dr_event=old_dr_event)
    for site_event in site_events:
        site_event.dr_event = new_dr_event
        site_event.ven_status = 'not_told'
        site_event.status = 'cancelled'
        site_event.save()

    return HttpResponseRedirect(reverse_lazy('vtn:home'))


def cancel_dr_event(request, pk):
    """
    :param pk: the pk of the event that is being cancelled
    :param request: request object
    :return: redirects user to homepage
    """
    old_dr_event = DREvent.objects.get(pk=pk)
    new_dr_event = old_dr_event
    new_dr_event.pk = None
    new_dr_event.deleted = True
    new_dr_event.modification_number = old_dr_event.modification_number + 1
    new_dr_event.status = 'cancelled'
    new_dr_event.save()
    old_dr_event = DREvent.objects.get(pk=pk)
    old_dr_event.superseded = True
    old_dr_event.save()
    site_events = SiteEvent.objects.filter(dr_event=old_dr_event)
    for site_event in site_events:
        site_event.dr_event = new_dr_event
        site_event.ven_status = 'not_told'
        site_event.status = 'cancelled'
        site_event.save()

    return HttpResponseRedirect(reverse_lazy('vtn:home'))


def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important!
            messages.success(request, 'Your password was successfully updated!')
            return redirect(reverse_lazy('vtn:home'))
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'vtn/change_password.html', {
        'form': form
                })


def dr_event_export(request, pk):

    """
    This function does the actual exporting of a given
    DR Event's data
    """

    event = DREvent.objects.get(pk=pk)
    sites = Site.objects.filter(siteevent__dr_event=event)

    t_data = Telemetry.objects.filter(site__in=sites) \
                              .filter(reported_on__range=(event.start, event.end)) \
                              .order_by('-reported_on')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="dr-events.csv"'

    writer = csv.writer(response)

    writer.writerow(['DR Program', 'Site', 'Time', 'Baseline Power (kw)', 'Measured Power (kw)'])
    for datum in t_data:
        writer.writerow([event.dr_program, datum.site, datum.created_on.strftime("%Y-%m-%d %I:%M:%S %p"),
                        datum.baseline_power_kw, datum.measured_power_kw])
    return response


def report(request):
    """
    This function gets the initial data for the 'Report' page.
    """

    initial_data = DREvent.objects.all().filter(superseded=False).filter(deleted=False) \
        .order_by('-start') \
        .annotate(numSites=Count('sites')) \
        .select_related('dr_program')
    form = DREventFormFilter()
    return render(request, 'vtn/dr_event_export_filter.html', {'data': initial_data, 'form': form})


def get_more_tables(request):
    """Function that is called to update the DREvent list on the export page.
    Args:
        request : request from an Ajax "GET" call, with a dictionary
                  of what filters are going to be used

    Returns:
        HTML : An updated table if a filter has been applied, or the filter forms
               and a 'fresh' table if the "Clear Filters" button has been pressed.

    """
    form = DREventFormFilter()
    final_events = DREvent.objects.all().order_by('-start') \
                                        .annotate(numSites=Count('sites')) \
                                        .select_related('dr_program') \
                                        .filter(~Q(status='cancelled')).filter(~Q(status='CANCELED')) \
                                        .filter(superseded=False) \
                                        .filter(deleted=False)

    # If the clear filters button was pressed, return all the DR Events
    if 'clearFilters' in request.GET:
        return render(request, 'vtn/clean_dr_event_filter.html', {'data': final_events, 'form': form})

    else:

        # Get submitted filters
        dr_program_num = request.GET.get('drprogram', '')
        date_range = request.GET.get('daterange', '')

        # If there is a DR Program filter
        if dr_program_num != '':
            dr_programs = DRProgram.objects.all().order_by('name')
            programs = dr_programs.get(pk=dr_program_num)
            final_events = final_events.filter(dr_program=programs)

        # If there is a date-range filter
        if date_range != '':
            date_list = [datetime.strptime(x.strip(), '%m/%d/%Y')for x in date_range.split('-')]
            start, end = date_list[0], date_list[1]
            end = end + timedelta(hours=23, minutes=59, seconds=59)
            final_events = final_events.filter(Q(start__gte=start, start__lte=end))
        return render(request, 'vtn/get_more_tables.html', {'data': final_events})


class DREventAdd(CreateView):
    template_name = 'vtn/dr_event_form.html'
    form_class = DREventForm
    model = DREvent
    success_url = reverse_lazy("vtn:home")

    def get_form(self, form_class=form_class):
        form = super(DREventAdd, self).get_form(form_class)
        form.fields["sites"].queryset = Site.objects.all() \
                                                    .select_related('customer') \
                                                    .order_by('customer__name')
        form.fields['scheduled_notification_time'].initial = (timezone.now() + timedelta(hours=1))
        form.fields['start'].initial = (timezone.now() + timedelta(hours=2))
        form.fields['end'].initial = (timezone.now() + timedelta(hours=3))
        return form

    def form_valid(self, form):
        self.object = form.save(commit=False)
        dr_events = DREvent.objects.all().order_by('-event_id')
        try:
            latest_event_id = dr_events[0].event_id
        except IndexError:
            latest_event_id = 0
        self.object.event_id = latest_event_id + 1

        self.object.save()

        # Create the site events
        for site in form.cleaned_data['sites']:
            s = SiteEvent()
            s.dr_event = self.object
            s.site = site
            s.status = 'far'
            s.last_status_time = timezone.now()
            s.opt_in = 'none'
            s.save()

        return super(ModelFormMixin, self).form_valid(form)


# The difference between this view and DREventAdd is that
# this view is called when editing a DR Event.
class DREventCreate(CreateView):

    template_name = "vtn/dr_event_update_form.html"
    model = DREvent
    form_class = DREventUpdateForm

    def get_form(self, form_class=form_class):
        form = super(DREventCreate, self).get_form(form_class)
        dr_event = DREvent.objects.get(pk=self.kwargs['pk'])
        dr_program = dr_event.dr_program
        queryset_sites = dr_program.sites.all().select_related('customer').order_by('customer')
        form.fields["sites"].queryset = queryset_sites
        dr_event = DREvent.objects.get(pk=self.kwargs['pk'])

        form.fields['dr_program'].initial = dr_event.dr_program
        form.fields['start'].initial = dr_event.start
        form.fields['end'].initial = dr_event.end
        form.fields['scheduled_notification_time'].initial = dr_event.scheduled_notification_time
        form.fields['modification_number'].initial = dr_event.modification_number + 1
        form.fields['status'].initial = dr_event.status

        site_events = SiteEvent.objects.filter(dr_event=dr_event).filter(~Q(status='cancelled'))
        sites = [s.site for s in site_events]
        form.fields['sites'].initial = sites
        return form

    def get_context_data(self, **kwargs):
        context = super(DREventCreate, self).get_context_data(**kwargs)
        context['pk'] = self.kwargs['pk']
        return context

    def form_valid(self, form):

        # Get old DR Event and mark it as superseded. Also get old site events
        old_dr_event = DREvent.objects.get(pk=self.kwargs['pk'])  # Add exception handling here (put in try block)

        # Get the newly created DR Event
        self.object = form.save(commit=False)
        # Set correct previous version, and modification number

        self.object.modification_number = old_dr_event.modification_number + 1
        self.object.event_id = old_dr_event.event_id
        self.object.save()

        old_site_events = SiteEvent.objects.filter(dr_event=old_dr_event)
        old_dr_event.superseded = True
        old_dr_event.save()
        old_dr_event = DREvent.objects.get(pk=self.kwargs['pk'])  # Add exception handling here (put in try block)

        # Get list of sites that were enrolled in the old DR Event
        old_sites = list(old_site_events.values_list('site', flat=True))

        # Need to compare sites
        # Get list of sites that were just chosen in the form
        form_sites = [site.pk for site in form.cleaned_data['sites']]

        # Sites that need new site events
        new_sites_to_be_created = list(set(form_sites) - set(old_sites))

        # Sites that remained in the form's chosen sites
        existing_sites_to_be_updated = list(set(form_sites) & set(old_sites))

        # Sites/site-events that we don't need
        sites_to_be_superseded = list(set(old_sites) - set(form_sites))
        site_events_to_be_removed = SiteEvent.objects.filter(site__in=sites_to_be_superseded) \
                                                     .filter(dr_event=old_dr_event)

        # Get remaining (existing) site events to update below
        remaining_site_events = SiteEvent.objects.filter(dr_event=old_dr_event) \
                                                 .filter(site__pk__in=existing_sites_to_be_updated)

        for site_pk in new_sites_to_be_created:
            site = Site.objects.get(pk=site_pk)
            s = SiteEvent()
            s.dr_event = self.object
            s.site = site
            s.status = 'scheduled'
            s.last_status_time = timezone.now()
            # s.modification_number = 0
            s.opt_in = 'none'
            s.save()

        #  For sites removed from the event, mark them 'cancelled' and point
        # them to new DR Event
        #  1. 'Delete' these site-events by marking them  cancelled
        for site_event_to_be_removed in site_events_to_be_removed:
            site_event_to_be_removed.status = 'cancelled'
            site_event_to_be_removed.dr_event = self.object
            site_event_to_be_removed.ven_status = 'not_told'
            site_event_to_be_removed.save()

        #  With remaining site events, re-point them to new DR Event
        for site_event in remaining_site_events:
            site_event.dr_event = self.object
            site_event.status = 'scheduled'
            site_event.ven_status = 'not_told'
            site_event.save()

        return super(ModelFormMixin, self).form_valid(form)


@login_required
def overview(request):

    if request.method == "GET":

        update_event_statuses()

        customers = Customer.objects.annotate(sites=Count('site'),
                                              online=Count(Case(When(site__online=True, then=1))),
                                              offline=Count(Case(When(site__online=False, then=1)))) \
                                    .order_by('name')

        # DR Event Table
        dr_event_data = DREvent.objects.filter(end__gt=timezone.now()) \
                                       .filter(superseded=False) \
                                       .annotate(numSites=Count('sites')) \
                                       .select_related('dr_program') \
                                       .order_by('start')

        dr_program_edit_form = DRProgramEditForm()

        context = {'customers': customers, 'dr_event_data': dr_event_data, 'form': dr_program_edit_form}
        return render(request, 'vtn/home.html', context)

    # The form was submitted to edit a DR Program
    else:
        return HttpResponseRedirect(reverse_lazy('vtn:edit_program', kwargs={'pk': request.POST['dr_program']}))


# For the filter event
def get_dr_event_form(request):

    dr_program = request.GET.get('dr_program', '')
    if dr_program != '':
        dr_program = DRProgram.objects.get(pk=dr_program)

        form = DREventFilterForm()
        sites = dr_program.sites.all().order_by('site_name')
        form.fields["sites"].queryset = sites
        form.fields["sites"].initial = sites
        return render(request, 'vtn/dr_event_filter_form.html', {'form': form, 'dr_program': dr_program})


def get_dr_event_details(request, pk):
    # This function is called when a customer or site is selected
    # on the DR Event detail screen. It loads the graph data for
    # the specified customer or site.

    customer = request.GET.get('customer', '')
    site_pk = request.GET.get('site', '')
    context = {}
    event = DREvent.objects.get(pk=pk)

    if customer != '':
        if customer == 'empty':
            sites = Site.objects.filter(siteevent__dr_event=event)
        else:
            customers = Customer.objects.all().order_by('pk')
            customer = customers.get(pk=customer)
            sites = Site.objects.filter(siteevent__dr_event=event).filter(customer=customer)
    elif site_pk == 'empty':
        sites = Site.objects.filter(siteevent__dr_event=event)
    else:
        sites = Site.objects.filter(pk=site_pk)

    start = event.start
    end = event.end

    date_slice = "trunc(extract(epoch from created_on) / '{}' ) * {}".format(str(settings.GRAPH_TIMECHUNK_SECONDS),
                                                                             str(settings.GRAPH_TIMECHUNK_SECONDS))
    t_data = Telemetry.objects.filter(site__in=sites) \
        .filter(created_on__range=(start, end)) \
        .extra(select={'date_slice': date_slice}) \
        .values('date_slice', 'site') \
        .annotate(avg_baseline_power_kw=Avg('baseline_power_kw'),
                  avg_measured_power_kw=Avg('measured_power_kw'),
                  time=Min('created_on'))
    if t_data.count() == 0:
        context['no_data_for_sites'] = 'True'
        return render(request, 'vtn/dr_event_customer_detail.html', context)
    else:
        co = t_data.order_by('-created_on')
        context['t_data'] = t_data
        last = co.first()['time']
        first = co.last()['time']
        difference = (last - first).seconds
        quarter = difference // 4
        last = last - timedelta(seconds=quarter)
        first = first + timedelta(seconds=quarter)
        context['start_focus'] = first
        context['end_focus'] = last

        sum_baseline = {}
        sum_measured = {}
        for datum in t_data:
            if datum['date_slice'] in sum_baseline:
                sum_baseline[datum['date_slice']] += datum['avg_baseline_power_kw']
            else:
                sum_baseline[datum['date_slice']] = datum['avg_baseline_power_kw']
            if datum['date_slice'] in sum_measured:
                sum_measured[datum['date_slice']] += datum['avg_measured_power_kw']
            else:
                sum_measured[datum['date_slice']] = datum['avg_measured_power_kw']

        context['sum_baseline'] = OrderedDict(sorted(sum_baseline.items(), key=lambda t: t[0]))
        context['sum_measured'] = OrderedDict(sorted(sum_measured.items(), key=lambda t: t[0]))
        context['no_data_for_sites'] = 'False'

        return render(request, 'vtn/dr_event_customer_detail.html', context)


def dr_event_dispatch(request, pk):
    # This function is called after a user clicks on a DR Event on the
    # overview screen. It "routes" the request to either the DR Event
    # update screen or DR Event detail screen, depending on whether the
    # event's start time has passed.

    event = DREvent.objects.get(pk=pk)
    # if event.start < datetime.now(tz=timezone.utc):
    if event.start < timezone.now():
        return HttpResponseRedirect(reverse_lazy('vtn:dr_event_detail', kwargs={'pk': pk}))

    else:
        return HttpResponseRedirect(reverse_lazy('vtn:dr_event_update', kwargs={'pk': pk}))


class DREventDetail(TemplateView):
    template_name = "vtn/dr_event_detail.html"

    def get_context_data(self, **kwargs):
        context = super(DREventDetail, self).get_context_data(**kwargs)
        event = DREvent.objects.get(pk=self.kwargs['pk'])
        sites = DREvent.objects.get(pk=self.kwargs['pk']).sites.all()
        customer_form = DREventCustomerDetailForm()
        site_form = DREventSiteDetailForm()

        # Fill out context fields
        customer_form.fields['customer'].queryset = Customer.objects.filter(site__in=sites).distinct()
        site_form.fields['site'].queryset = Site.objects.filter(siteevent__dr_event=event)
        context['event'] = event
        context['customerForm'] = customer_form
        context['siteForm'] = site_form
        context['status'] = get_status(event)
        context['pk'] = self.kwargs['pk']
        context['start'] = event.start
        context['end'] = event.end

        # Get site events for "Site Detail" tab
        context['site_events'] = SiteEvent.objects.filter(dr_event=event)
        site_events = SiteEvent.objects.filter(dr_event=event)

        for site_event in site_events:
            site_event.last_stat = get_most_recent_stat(event, site_event.site)

        context['site_events'] = site_events

        # Only get those sites that have a corresponding Site Event
        sites = Site.objects.filter(siteevent__dr_event=event)

        # If there is no telemetry, tell template there is none so 'No data' is displayed
        if Telemetry.objects.filter(site__in=sites).filter(created_on__range=(event.start, event.end)).count() == 0:
            context['no_data'] = True

        # If there is telemetry...
        else:
            start = event.start
            end = event.end

            date_slice = "trunc(extract(epoch from created_on) / '{}' ) * {}".format(
                str(settings.GRAPH_TIMECHUNK_SECONDS),
                str(settings.GRAPH_TIMECHUNK_SECONDS))
            t_data = Telemetry.objects.filter(site__in=sites) \
                                      .filter(created_on__range=(start, end)) \
                                      .extra(select={'date_slice': date_slice}) \
                                      .values('date_slice', 'site') \
                                      .annotate(avg_baseline_power_kw=Avg('baseline_power_kw'),
                                                avg_measured_power_kw=Avg('measured_power_kw'),
                                                time=Min('created_on'))

            co = t_data.order_by('-created_on')
            context['t_data'] = t_data
            last = co.first()['time']
            first = co.last()['time']
            difference = (last - first).seconds
            quarter = difference // 4
            last = last - timedelta(seconds=quarter)
            first = first + timedelta(seconds=quarter)
            context['start_focus'] = first
            context['end_focus'] = last

            sum_baseline = {}
            sum_measured = {}
            for datum in t_data:
                if datum['date_slice'] in sum_baseline:
                    sum_baseline[datum['date_slice']] += datum['avg_baseline_power_kw']
                else:
                    sum_baseline[datum['date_slice']] = datum['avg_baseline_power_kw']
                if datum['date_slice'] in sum_measured:
                    sum_measured[datum['date_slice']] += datum['avg_measured_power_kw']
                else:
                    sum_measured[datum['date_slice']] = datum['avg_measured_power_kw']

            context['sum_baseline'] = OrderedDict(sorted(sum_baseline.items(), key=lambda t: t[0]))
            context['sum_measured'] = OrderedDict(sorted(sum_measured.items(), key=lambda t: t[0]))

        return context


def get_most_recent_stat(dr_event, site):
    """
    :param site: The site to get the most recent measured power stat for.
    :param dr_event: Used to get start and end times for telemetry.
    :return: Ideally, returns the difference between the site's baseline power
             and its actual power. If there is no baseline, it returns 'N.A.
    """
    try:
        t_data = Telemetry.objects.filter(site=site) \
                                  .filter(reported_on__range=(dr_event.start, dr_event.end)) \
                                  .order_by('-reported_on')[0]
        if t_data.baseline_power_kw is not None:
            return t_data.baseline_power_kw - t_data.measured_power_kw
        else:
            return t_data.measured_power_kw
    except (IndexError, Exception):
        return 'N.A.'


def get_status(dr_event):

    if dr_event.start < timezone.now():
        return "Active"
    elif dr_event.scheduled_notification_time < timezone.now():
        return "Notification"

