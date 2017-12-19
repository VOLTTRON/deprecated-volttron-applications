Feature: Test some operation with Report Page

  @skip
  Scenario: Filter the DR Event by Date Range
    Given Login with admin
    When I add Customer name "foobar", utility id "123", contact name "test" and phone number "123456789"
    And I add site with customer name "foobar", site name "site1", site ID "123", VEN ID "456", VEN Name "test", Site Location Code "1233", IPV6 add "1", Site Add "address1", city "city1", state "CA", zip "99999", contact name "name1", phone number "123456"
    And I add a DR Program name "dr_program_test1" with all sites
    And I add a DR Program name "dr_program_test2" with all sites
    And I add a DR Program name "dr_program_test3" with all sites
    And I click on Overview
    And I add a DR Event with DR program "dr_program_test1", customer "foobar", site "(foobar) site1", noti date "2020-12-21", noti time "14:08:02", start date "2020-12-21", start time "14:08:42", end date "2020-12-31", end time "14:09:03"
    And I add a DR Event with DR program "dr_program_test2", customer "foobar", site "(foobar) site1", noti date "2021-05-31", noti time "14:08:02", start date "2021-05-31", start time "14:08:42", end date "2022-05-31", end time "14:09:03"
    And I add a DR Event with DR program "dr_program_test3", customer "foobar", site "(foobar) site1", noti date "2020-11-11", noti time "14:08:02", start date "2021-12-21", start time "14:08:42", end date "2021-12-31", end time "14:09:03"
    And I filter Date Range "11/10/2020 - 11/01/2021" only
    Then I should see DR Event name "dr_program_test1"
    And I should see DR Event name "dr_program_test2"


  Scenario: Filter the DR Event by DR Program
    Given Login with admin
    When I add Customer name "foobar", utility id "123", contact name "test" and phone number "123456789"
    And I add site with customer name "foobar", site name "site1", site ID "123", VEN ID "456", VEN Name "test", Site Location Code "1233", IPV6 add "1", Site Add "address1", city "city1", state "CA", zip "99999", contact name "name1", phone number "123456"
    And I add a DR Program name "dr_program_test1" with all sites
    And I add a DR Program name "dr_program_test2" with all sites
    And I add a DR Program name "dr_program_test3" with all sites
    And I click on Overview
    And I add a DR Event with DR program "dr_program_test1", customer "foobar", site "(foobar) site1", noti date "2020-12-21", noti time "14:08:02", start date "2020-12-21", start time "14:08:42", end date "2020-12-31", end time "14:09:03"
    And I add a DR Event with DR program "dr_program_test2", customer "foobar", site "(foobar) site1", noti date "2021-05-31", noti time "14:08:02", start date "2021-05-31", start time "14:08:42", end date "2022-05-31", end time "14:09:03"
    And I add a DR Event with DR program "dr_program_test3", customer "foobar", site "(foobar) site1", noti date "2020-11-11", noti time "14:08:02", start date "2021-12-21", start time "14:08:42", end date "2021-12-31", end time "14:09:03"
    And I filter DR Program "dr_program_test1" only
    Then I should only see DR Event name "dr_program_test1"


  Scenario: Filter the DR Event by Date Range and DR Program
    Given Login with admin
    When I add Customer name "foobar", utility id "123", contact name "test" and phone number "123456789"
    And I add site with customer name "foobar", site name "site1", site ID "123", VEN ID "456", VEN Name "test", Site Location Code "1233", IPV6 add "1", Site Add "address1", city "city1", state "CA", zip "99999", contact name "name1", phone number "123456"
    And I add a DR Program name "dr_program_test1" with all sites
    And I add a DR Program name "dr_program_test2" with all sites
    And I add a DR Program name "dr_program_test3" with all sites
    And I click on Overview
    And I add a DR Event with DR program "dr_program_test1", customer "foobar", site "(foobar) site1", noti date "2020-12-21", noti time "14:08:02", start date "2020-12-21", start time "14:08:42", end date "2020-12-31", end time "14:09:03"
    And I add a DR Event with DR program "dr_program_test2", customer "foobar", site "(foobar) site1", noti date "2021-05-31", noti time "14:08:02", start date "2021-05-31", start time "14:08:42", end date "2022-05-31", end time "14:09:03"
    And I add a DR Event with DR program "dr_program_test3", customer "foobar", site "(foobar) site1", noti date "2020-11-11", noti time "14:08:02", start date "2021-12-21", start time "14:08:42", end date "2021-12-31", end time "14:09:03"
    And I filter DR Program "dr_program_test1" and Date Range "11/10/2020 - 11/01/2021"
    Then I should only see DR Event name "dr_program_test1"
