======================
 FNCS VOLTTRON Bridge
======================
----------
 Overview
----------
FNCS_Volttron_Bridge.py is a standalone VOLTTRON agent. It is meant to run on a system where the VOLTTRON platform is installed and run. It has a configuration associated with it called FNCS_VOLTTRON_Bridge.config. This repository provides a stub of what this configuration must contain.

--------------
 How it works
--------------
The FNCS VOLTTRON Bridge acts purely as a bi-directional message forwarder between the FNCS message bus and the VOLTTRON message bus.

Executing the FNCS_Volttron_Bridge
==================================
The agent is executed by typeing::

	python FNCS_Volttron_Bridge.py

Where ever the agent is run from that directory must contain the configuration file entitle FNCS_VOLTTRON_Bridge.config. 

The FNCS_VOLTTRON_Bridge.config File
====================================
The configuration file for the agent must contain the following keys with:
	* "simulation_run_time": a string containing the amount of time the FNCS simulation will run. valid entries are strings like "60s" and "4d".
	* "heartbeat_period": The heartbeat period for the agent should always be 1.
	* "heartbeat_multiplier": This determine how long a heartbeat period is for the fncs simulation in seconds. for example if the heartbeat period is 1 second and the heartbeat multiplier is 300 seconds then each 1 second heartbeat represents 5 simulated minutes.
	* "fncs_zpl": This key contains a nested object that represents a FNCS federate configuration information. For information on creating a FNCS federate configuration please see `The FNCS Documentation Page <https://github.com/FNCS/fncs/wiki>`_.
	* "remote_platform_params": This contains all the key value pairs for creating the agents vip address.

.. note:: Both VOLTTRON and FNCS use the ZeroMQ library. In order for the agent to run successfully, the version of zeromq packaged with VOLTTRON and the version compiled with FNCS must be the same. VOLTTRON 4.1 packages 4.1.5 of ZeroMQ. So when Installing FNCS you must download and install version 4.1.5 of ZeroMQ. Version 4.1.5 of ZeroMQ can downloaded from `here <https://github.com/zeromq/zeromq4-1/releases>`_.

How to forward messages to the FNCS bus from the VOLTTRON bus?
==============================================================
The FNCS_Volttron_Bridge agent listens to the fncs/input/* topic on the VOLTTRON bus so if you wish to forward subtopics to the FNCS message bus you must preface your subtopic with fncs/input/. All messages forwarded to FNCS have the topic of the FNCS_Volttron_Bridge/subtopic.

How to forward messages to the VOLTTRON bus from the FNCS bus?
==============================================================
As previously stated you list FNCS message topics you wish to subscribe to in the FNCS_VOLTTRON_Bridge.config file. The FNCS_Volttron_Bridge agent will forward messages from these topics to the VOLTTRON bus on the topic fncs/output/devices/subtopic. The subtopic is the fncs topic you suscribed to.


