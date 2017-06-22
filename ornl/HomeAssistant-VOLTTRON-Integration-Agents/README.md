# Home Assistant and VOLTTRON Integration
The agents available in this folder can be used to integrate [VOLTTRON](https://github.com/VOLTTRON/volttron) and [Home Assistant](https://home-assistant.io/). Because of this integration, the information about the components loaded on Home-Assistant are available on the VOLTTRON message bus and other agents can use this information or make changes to them.
Before running the agents, both VOLTTRON and home-assistant should be installed and running. To install and run home-assistant, please follow the instruction on this link: https://home-assistant.io/getting-started/ .

Since home-assistant provides a RESTful API, that API is used for the integrations. Different agents implemented in VOLTTRON for supporting the integration are explained below. For each of these agents, the HASS API address, the API password, and the agent id are provided to the agent in the agent configuration file.
1.	HASS AGENT: This agent uses VOLTTRON as a platform and communicates with home assistant API. This agent is responsible for checking the state of the components loaded on HASS every 30 seconds (this value is configurable) and publishes the information about each device on VOLTTRON message bus. The list of topics used by HASS agent can be found in the following table:     


| Component Name | Message Topic |
|:---:|---|
| Climate | record/hass/climate/entityId | 
| Light | record/hass/light/entityId | 
|Lock | record/hass/lock/entityId | 
| Switch | record/hass/switch/entityId | 
| MQTT | record/hass/mqtt/entityId | 


2.	HASS Climate Agent: This agent subscribes to all the messages published about climate components by HASS Agent. Climate components (https://home-assistant.io/components/climate/) are devices that can manage heating, ventilating, and air conditioning(HVAC) units. This agent can also change the state of a specific (like temperature, set points, fan mode, operation mode, etc.) climate device by sending appropriate service calls to HASS API.

3.	HASS Light Agent: This agent subscribes to all the messages published about light components loaded on HASS API. Light components (https://home-assistant.io/components/light/) provide a mean to control various lighting systems (light bulbs). This agent can also change the state of the light bulbs (such as turn on/off, toggle, etc.) by sending service calls to HASS API.

4.	HASS Lock Agent: This agent subscribes to all the messages published by HASS API regarding lock components. In home assistant lock components (https://home-assistant.io/components/lock/) allow the user to control door lock devices. This agent can also lock/unlock the door locks by sending appropriate service calls to the HASS API.

5.	HASS Switch Agent: This agent subscribes to all messages that are published regarding switch components. The switch components (https://home-assistant.io/components/switch/) allow the user to manage the state of the switches. The agent can turn on, turn off, and toggle the switch by sending appropriate service calls to HASS API. 

Note that the logic used and explained here can be used for integrating any energy management system that provides an API regardless of the programming language used by that system.



