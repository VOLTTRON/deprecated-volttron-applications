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

from vtn.models import Customer, Site, DRProgram, DREvent, SiteEvent, Telemetry

customerNames = ["Clark Kent", "Peter Parker", "Anh Nguyen", "Bob Barcklay", "Nate Hill", "James Sheridan"]
utility_id = ['001','002','003','004','005','006']

for i in range(0,6):
    customer = Customer(name=customerNames[i],utility_id=utility_id[i])
    customer.save()

drprograms = ["capacity bidding program", "peak day pricing program", "direct load control", "emergency demand reponse"]

site_names = ["Montclair", "Oakland", "San Francisco", "Moraga", "Emeryville", "Berkeley"]
site_ids = [('site00' + str(x)) for x in range(1,7)]
locations = [('location00' + str(x)) for x in range(1,7)]
ipAddresses = [('274.524.501.' + str(x)) for x in range(1,7)]
site_address1s = [('121' + str(x) + ' Sunnyhills Rd.') for x in range(0,6)]
city = ['Oakland']*6
state = ['CA']*6
zip = ['94610']*6
contact_names = [("Contact" + str(x)) for x in range(1,7)]
phone_numbers=[("510325405" + str(x)) for x in range(1,7)]
online = [True, False, True, False, True, False]
dr_program_names = [('drprogram' + str(x)) for x in range(0,6)]

## build Sites
for x in range(0,6):
    customer = Customer.objects.get(pk=x+1)
    s = Site(customer=customer,
             site_name=site_names[x],
             site_id=site_ids[x],
             site_location_code=locations[x],
             ip_address=ipAddresses[x],
             site_address1=site_address1s[x],
             city=city[x],
             state=state[x],
             zip=zip[x],
             contact_name=contact_names[x],
             phone_number=phone_numbers[x],
             online=online[x])
    s.save()


    d = DRProgram(name=dr_program_names[x])
    d.save()
    d.sites.add(s)
    d.save()






