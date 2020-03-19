PNNL developed applications

 - EconomizerRCxAgent - HVAC fault detection algorithm for economizer systems in air-handling units
 and packaged rooftop air conditioners.
 
    -  Temperature sensor faults
    -  Inconsistent temperature sensor readings when economizing
    -  Economizing when conditions are not favorable for economizing
    -  Not economizing when conditions are favorable for economizing
    -  Excess outdoor-air ventilation
    -  Insufficient outdoor-air ventilation
    
   This application has been updated to run with Python3 and a refactor/update is in progress. Config store support
   will be added during the refactor.
   
 - AirsideRCxAgent - HVAC retuning algorithm for variable-air-volume air-handling units to detect common retuning
 opportunities. The application has a passive detect only mode and a auto-correct mode.
 
    -  Low supply-air temperature
    -  High supply-air temperature
    -  No supply-air temperature set point reset
    -  Low duct static pressure
    -  high duct static pressure
    -  No duct static pressure set point reset
    -  Excessive operation during unoccupied hours
    
   This application has been updated to run with Python3 and a refactor/update is in progress.
   
  - ProactiveDiagnosticAgent - Highly configurable application for proactive fault detection. This application can be
  configured for any device that has data available via the VOLTTRON MasterDriver interface. The ProactiveDiagnosticAgent
  will initiate a set of control actions to put device (e.g., AHU, RTU, chiller, etc) into a state to create the necessary
  analytical sensor redundancy (e.g., for AHU close chilled water valve and open the outdoor-air damper to detect sensor
  inconsistencies). The application then evaluates a rule set to determine if a fault is present for the equipment.

    The example config present with the agent shows an example of proactive control of an AHU to detect inconsistencies
  between the mixed-air temperature sensor and the discharge-air temperature sensor.  These configs are essentially
  recipes, a full suite of recipes will be added to the repository as they are tested.
    
    This application has been  coded to run with Python3 supports the VOLTTRON config store.
   
 - ILCAgent - moved to volttron-GS repository.


