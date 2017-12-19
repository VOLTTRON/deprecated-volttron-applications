Feature: Test some operation with Site Event objects

  Scenario: Test Site Event

    Given Login with admin
    When I add Customer name "foobar", utility id "123", contact name "test" and phone number "123456789"
    And I add site with customer name "foobar", site name "site1", site ID "1", VEN Name "test1", Site Location Code "1233", IPV6 add "1", Site Add "address1", city "city1", state "CA", zip "99999", contact name "name1", phone number "123456"
    And I add site with customer name "foobar", site name "site2", site ID "2", VEN Name "test2", Site Location Code "1234", IPV6 add "2", Site Add "address1", city "city1", state "CA", zip "99999", contact name "name1", phone number "123456"
    And I add site with customer name "foobar", site name "site3", site ID "3", VEN Name "test3", Site Location Code "1235", IPV6 add "3", Site Add "address1", city "city1", state "CA", zip "99999", contact name "name1", phone number "123456"
    And I add site with customer name "foobar", site name "site4", site ID "4", VEN Name "test4", Site Location Code "1236", IPV6 add "3", Site Add "address1", city "city1", state "CA", zip "99999", contact name "name1", phone number "123456"
    And I add a DR Program name "dr_program_test" with all sites
    And I click on Overview
    And I add a DR Event with DR program "dr_program_test", customer "foobar", with all sites, noti date "2020-10-31", noti time "14:08:02", start date "2020-10-31", start time "14:08:42", end date "2020-10-31", end time "14:09:03"
    Then I should see an active "(foobar) site1" in Site Events
    And I should see an active "(foobar) site2" in Site Events
    And I should see an active "(foobar) site3" in Site Events


  Scenario: Test Site Event after deselecting a site

    Given Login with admin
    When I add Customer name "foobar", utility id "123", contact name "test" and phone number "123456789"
    And I add site with customer name "foobar", site name "site1", site ID "1", VEN Name "test1", Site Location Code "1233", IPV6 add "1", Site Add "address1", city "city1", state "CA", zip "99999", contact name "name1", phone number "123456"
    And I add site with customer name "foobar", site name "site2", site ID "2", VEN Name "test2", Site Location Code "1234", IPV6 add "2", Site Add "address1", city "city1", state "CA", zip "99999", contact name "name1", phone number "123456"
    And I add site with customer name "foobar", site name "site3", site ID "3", VEN Name "test3", Site Location Code "1235", IPV6 add "3", Site Add "address1", city "city1", state "CA", zip "99999", contact name "name1", phone number "123456"
    And I add site with customer name "foobar", site name "site4", site ID "4", VEN Name "test4", Site Location Code "1236", IPV6 add "3", Site Add "address1", city "city1", state "CA", zip "99999", contact name "name1", phone number "123456"
    And I add a DR Program name "dr_program_test" with all sites
    And I click on Overview
    And I add a DR Event with DR program "dr_program_test", customer "foobar", with all sites, noti date "2020-10-31", noti time "14:08:02", start date "2020-10-31", start time "14:08:42", end date "2020-10-31", end time "14:09:03"
    And I edit DR Event "dr_program_test" by deselecting site "(foobar) site3"
    Then I should see an active "(foobar) site1" in Site Events
    And I should see an active "(foobar) site2" in Site Events
    And I should see a cancelled "(foobar) site3" in Site Events
    And I should see an active "(foobar) site4" in Site Events


  Scenario: Test Site Event after adding a site

    Given Login with admin
    When I add Customer name "foobar", utility id "123", contact name "test" and phone number "123456789"
    And I add site with customer name "foobar", site name "site1", site ID "1", VEN Name "test1", Site Location Code "1233", IPV6 add "1", Site Add "address1", city "city1", state "CA", zip "99999", contact name "name1", phone number "123456"
    And I add site with customer name "foobar", site name "site2", site ID "2", VEN Name "test2", Site Location Code "1234", IPV6 add "2", Site Add "address1", city "city1", state "CA", zip "99999", contact name "name1", phone number "123456"
    And I add site with customer name "foobar", site name "site3", site ID "3", VEN Name "test3", Site Location Code "1235", IPV6 add "3", Site Add "address1", city "city1", state "CA", zip "99999", contact name "name1", phone number "123456"
    And I add site with customer name "foobar", site name "site4", site ID "4", VEN Name "test4", Site Location Code "1236", IPV6 add "3", Site Add "address1", city "city1", state "CA", zip "99999", contact name "name1", phone number "123456"
    And I add a DR Program name "dr_program_test" with all sites
    And I click on Overview
    And I add a DR Event with DR program "dr_program_test", customer "foobar", site "(foobar) site1", noti date "2020-10-31", noti time "14:08:02", start date "2020-10-31", start time "14:08:42", end date "2020-10-31", end time "14:09:03"
    And I edit DR Event "dr_program_test" by adding site "(foobar) site2"
    Then I should see an active "(foobar) site1" in Site Events
    And I should see an active "(foobar) site2" in Site Events


  Scenario: Test Site Events after cancelling DR Event

    Given Login with admin
    When I add Customer name "foobar", utility id "123", contact name "test" and phone number "123456789"
    And I add site with customer name "foobar", site name "site1", site ID "1", VEN Name "test1", Site Location Code "1233", IPV6 add "1", Site Add "address1", city "city1", state "CA", zip "99999", contact name "name1", phone number "123456"
    And I add site with customer name "foobar", site name "site2", site ID "2", VEN Name "test2", Site Location Code "1234", IPV6 add "2", Site Add "address1", city "city1", state "CA", zip "99999", contact name "name1", phone number "123456"
    And I add site with customer name "foobar", site name "site3", site ID "3", VEN Name "test3", Site Location Code "1235", IPV6 add "3", Site Add "address1", city "city1", state "CA", zip "99999", contact name "name1", phone number "123456"
    And I add site with customer name "foobar", site name "site4", site ID "4", VEN Name "test4", Site Location Code "1236", IPV6 add "3", Site Add "address1", city "city1", state "CA", zip "99999", contact name "name1", phone number "123456"
    And I add a DR Program name "dr_program_test" with all sites
    And I click on Overview
    And I add a DR Event with DR program "dr_program_test", customer "foobar", with all sites, noti date "2020-10-31", noti time "14:08:02", start date "2020-10-31", start time "14:08:42", end date "2020-10-31", end time "14:09:03"
    And I cancel a DR Event with DR program "dr_program_test"
    Then I should see a cancelled DR Event and cancelled Site Events
