volttron-ctl remove --force --name sunspecinverteragent-4.0    
volttron-pkg package SunspecInverter/
volttron-pkg configure ~/.volttron/packaged/sunspecinverteragent-4.0-py2-none-any.whl SunspecInverter/sunspecinverter.config
volttron-ctl install ~/.volttron/packaged/sunspecinverteragent-4.0-py2-none-any.whl 
volttron-ctl start --name sunspecinverteragent-4.0

