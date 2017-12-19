# Shell script to install ReferenceAppAgent as a VOLTTRON agent.
#
# This script should be run in a VOLTTRON virtualenv, in which $VOLTTRON_HOME
# and $VOLTTRON_ROOT have been defined as, respectively, the VOLTTRON execution
# directory and VOLTTRON's github installation directory.
#
# This is a volttron-applications agent. $VOLTTRON_ROOT should contain
# a soft link named "applications" linking to the volttron-applications github
# project installation directory.
#
#
AGENT_ROOT=$VOLTTRON_ROOT/applications/kisensum/ReferenceAppAgent

cd $VOLTTRON_ROOT
export VIP_SOCKET="ipc://$VOLTTRON_HOME/run/vip.socket"
python scripts/install-agent.py \
    -s $AGENT_ROOT \
    -i referenceappagent \
    -c $AGENT_ROOT/referenceappagent.config \
    -t referenceappagent \
    -f
