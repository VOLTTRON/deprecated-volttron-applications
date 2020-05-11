SUNSPEC INVERTER AGENT:

The sunspec inverter agent controls the inverter acting as a DER client. It supports the DER client functions as specified in the SunSpec Common Smart Inverter Profile 2.0.

The device initiates the communication with the utility server. The utility supplies the unique ids SFDI, LFDI and a End device link. Querying the link with the SFDI provides the links to DER function set which will be implemented by the client. If a polling rate is supplied, the client will poll to get the updates accordingly, if not polls every 10 minutes. Also the current status of the client will to be pushed to the utility. 

Requirements for running the agent:
	1. clone the pysunspec repo:

		git clone --recursive https://github.com/sunspec/pysunspec.git

		To install the library run from the pysunspec directory:
		python setup.py install

	2. Edit the sunspecinverter.config according to the inverter settings. 

