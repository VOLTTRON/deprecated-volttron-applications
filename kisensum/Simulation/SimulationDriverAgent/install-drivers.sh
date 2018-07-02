# Shell script to install device drivers for SimulationDriverAgent.
#
# This script should be run in a VOLTTRON virtualenv, in which $VOLTTRON_HOME
# and $VOLTTRON_ROOT have been defined as, respectively, the VOLTTRON execution
# directory and VOLTTRON's github installation directory.
#
# This configures a volttron-applications agent. $VOLTTRON_ROOT should contain
# a soft link named "applications" linking to the volttron-applications github
# project installation directory.
#
#
AGENT_ROOT=$VOLTTRON_ROOT/applications/kisensum/Simulation/SimulationDriverAgent

cd $VOLTTRON_ROOT

volttron-ctl config store simulation.driver simload.csv $AGENT_ROOT/simload.csv --csv
volttron-ctl config store simulation.driver devices/campus1/building1/simload $AGENT_ROOT/simload.config

volttron-ctl config store simulation.driver simmeter.csv $AGENT_ROOT/simmeter.csv --csv
volttron-ctl config store simulation.driver devices/campus1/building1/simmeter $AGENT_ROOT/simmeter.config

volttron-ctl config store simulation.driver simpv.csv $AGENT_ROOT/simpv.csv --csv
volttron-ctl config store simulation.driver devices/campus1/building1/simpv $AGENT_ROOT/simpv.config

volttron-ctl config store simulation.driver simstorage.csv $AGENT_ROOT/simstorage.csv --csv
volttron-ctl config store simulation.driver devices/campus1/building1/simstorage $AGENT_ROOT/simstorage.config

echo
echo Simulation drivers configured:
volttron-ctl config list simulation.driver
