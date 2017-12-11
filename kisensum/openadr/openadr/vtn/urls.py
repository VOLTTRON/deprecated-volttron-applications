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

from django.conf.urls import url
from django.views.generic import RedirectView
from vtn import views
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

app_name = 'vtn'

urlpatterns = [
    url(r'^$', RedirectView.as_view(url='/vtn/login')),

    url(r'^home/$',views.overview, name='home'),
    url(r'^login/$', auth_views.login, {'template_name': 'login.html'}, name='login'),
    url(r'^logout/$', auth_views.logout, {'template_name': 'logged_out.html'}, name='logout'),
    url(r'^customer-detail/(?P<pk>\w+)$', views.CustomerDetailView.as_view(), name='customer_detail'),
    url(r'^site-detail/(?P<pk>\w+)$', views.SiteDetailView.as_view(), name='site_detail'),
    url(r'^dr_event/$', login_required(views.DREventAdd.as_view()), name='dr_event'),
    url(r'^customer-edit/(?P<pk>[0-9]+)$', views.CustomerUpdate.as_view(), name='customer_update'),
    url(r'customer/add/$', views.CustomerCreate.as_view(), name='customer_add'),
    url(r'^export/(?P<pk>[0-9]+)/$', login_required(views.dr_event_export), name='export_dr_events_csv'),
    url(r'^report/$', login_required(views.report), name='report'),
    url(r'^export/filter/$', login_required(views.get_more_tables), name='get_more_tables'),
    url(r'^dr-event/add/$', login_required(views.get_dr_event_form), name='get_dr_event_form'),
    url(r'site/create/(?P<pk>[0-9]+)/$', login_required(views.CreateSiteView.as_view()), name='create_site'),
    url(r'^home/(?P<pk>[0-9]+)/$', login_required(views.delete_dr_event), name='dr_event_delete'),
    url(r'dr_event/(?P<pk>[0-9]+)/$', login_required(views.dr_event_dispatch), name='dr_event_dispatch'),
    url(r'dr_event/view/(?P<pk>[0-9]+)/$', login_required(views.DREventCreate.as_view()), name='dr_event_update'),
    url(r'dr_event/detail/(?P<pk>[0-9]+)/$', login_required(views.DREventDetail.as_view()), name='dr_event_detail'),
    url(r'dr_event/detail/(?P<pk>[0-9]+)/customer/$', login_required(views.get_dr_event_details), name='dr_event_get_details'),
    url(r'^home/(?P<pk>[0-9]+)/$', login_required(views.cancel_dr_event), name='dr_event_cancel'),

    url(r'password_change/$', login_required(views.change_password), name='change_password'),
]

urlpatterns += router.urls
