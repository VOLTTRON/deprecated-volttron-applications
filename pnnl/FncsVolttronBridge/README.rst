# FNCS_Volttron_Bridge
FNCS_Volttron_Bridge.py is a standalone VOLTTRON agent. It is meant to run on a system where the VOLTTRON platform is installed and run. It has a configuration associated with it called FNCS_VOLTTRON_Bridge.config. This repository provides a stub of what this configuration must contain.

## How to forward messages to the FNCS bus from the VOLTTRON bus
The FNCS_Volttron_Bridge agent listens to the fncs/input/* topic on the VOLTTRON bus so if you wish to forward subtopics to the FNCS message bus you must place your subtopic on the fncs/input/ topic. All messages forwarded to FNCS have the topic of the FNCS_Volttron_Bridge/fncs/input/subtopic.

## How to forward messages to the VOLTTRON bus from the FNCS bus
As previously stated you list FNCS message topics you wish to subscribe to in the FNCS_VOLTTRON_Bridge.config file. The FNCS_Volttron_Bridge agent will forward messages from these topics to the VOLTTRON bus on the topic fncs/output/devices/subtopic. The subtopic is the fncs topic you suscribed to.