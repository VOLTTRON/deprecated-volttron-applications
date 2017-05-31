# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2015, Battelle Memorial Institute
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

#}}}
from volttron.platform.messaging import topics
from volttron.platform.messaging import utils

FNCS_BASE_TOPIC = 'fncs'
FNCS_INPUT_TOPIC = 'input'
FNCS_OUTPUT_TOPIC = 'output'

_FNCS_PATH = utils.Topic('{base}//{direction}//{path}')
FNCS_PATH = utils.Topic(_FNCS_PATH.replace('{base}', FNCS_BASE_TOPIC))
FNCS_INPUT_PATH = utils.Topic(FNCS_PATH.replace('{direction}', FNCS_INPUT_TOPIC))
FNCS_OUTPUT_PATH = utils.Topic(FNCS_PATH.replace('{direction}', FNCS_OUTPUT_TOPIC))

_FNCS_DEVICES_PATH = utils.Topic(FNCS_PATH.replace('{path}','{devices}//{campus}//{building}//{unit}//{path!S}//{point}'))
FNCS_DEVICES_PATH = utils.Topic(_FNCS_DEVICES_PATH.replace('{devices}', topics.DRIVER_TOPIC_BASE))
FNCS_DEVICES = FNCS_PATH(direction=FNCS_OUTPUT_TOPIC, path = topics.DRIVER_TOPIC_BASE)
FNCS_DEVICES_INPUT_PATH = utils.Topic(FNCS_DEVICES_PATH.replace('{direction}', FNCS_INPUT_TOPIC))
FNCS_DEVICES_OUTPUT_PATH = utils.Topic(FNCS_DEVICES_PATH.replace('{direction}', FNCS_OUTPUT_TOPIC))
