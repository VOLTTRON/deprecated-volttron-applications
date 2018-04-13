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

import pytest
import gevent
import requests

from volttron.platform import get_services_core

AGENT_CONFIG = {
    "db_path": "$VOLTTRON_HOME/data/openadr.sqlite"
}

web_address = ""


@pytest.fixture(scope="module")
def agent(request, volttron_instance_module_web):
    """Create a test agent that interacts with other agents (e.g., the OpenADRVenAgent)."""
    ven_agent = volttron_instance_module_web.build_agent()

    # Install and start an Open ADR VEN agent.
    agent_id = volttron_instance_module_web.install_agent(agent_dir='services/core/OpenADRVenAgent',
                                                          config_file=AGENT_CONFIG,
                                                          vip_identity='test_venagent',
                                                          start=True)
    print('OpenADR agent id: ', agent_id)

    def stop():
        volttron_instance_module_web.stop_agent(agent_id)
        ven_agent.core.stop()

    gevent.sleep(3)        # wait for agents and devices to start
    request.addfinalizer(stop)
    return ven_agent


class TestOpenADRVenAgent:
    """Regression tests for the Open ADR VEN Agent."""

    # @todo While testing, employ simulated devices and actuation/control agents

    def test_openadr(self, agent):
        # Test that a GET of the "oadr_request_event" XML succeeds, returning a response with a 200 status code
        url = '{}/OpenADR2/Simple/2.0b/EIEvent'.format(web_address)
        xml_filename = get_services_core('OpenADRVenAgent/tests/oadr_request_event.xml')
        xml_file = open(xml_filename, 'rb')
        headers = {'content-type': 'application/sep+xml'}
        response = requests.get(url, data=xml_file, headers=headers)
        assert response.status_code == 200

        # Test that the PUT caused an update to the agent's list of events
        assert agent.vip.rpc.call('test_ven_agent', 'get_events').get(timeout=10) is None
