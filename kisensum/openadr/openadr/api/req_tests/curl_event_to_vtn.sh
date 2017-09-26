#echo Issuing EIEvent request with $1.xml
#curl -X POST -d @$1.xml --header "Content-Type:application/soap+xml" -v http://127.0.0.1:8080/OpenADR2/Simple/2.0b/EIEvent
curl -X POST -d "@sample_oadr_poll.xml" --header "Content-Type: application/xml"  http://127.0.0.1:8000/OpenADR2/Simple/2.0b/OadrPoll/