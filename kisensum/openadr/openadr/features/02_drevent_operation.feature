Feature: Test some operation with DR Event objects

  Scenario: Add DR event

    Given Login with admin
    When I add Customer name "foobar", utility id "123", contact name "test" and phone number "123456789"
    And I add site with customer name "foobar", site name "site1", site ID "123", VEN Name "test", Site Location Code "1233", IPV6 add "1", Site Add "address1", city "city1", state "CA", zip "99999", contact name "name1", phone number "123456"
    And I add a DR Program name "dr_program_test" with all sites
    And I click on Overview
    And I add a DR Event with DR program "dr_program_test", customer "foobar", site "(foobar) site1", noti date "2020-10-31", noti time "14:08:02", start date "2020-10-31", start time "14:08:42", end date "2020-10-31", end time "14:09:03"
    Then I should see a DR event of DR program "dr_program_test", site "site1", noti date "2020-10-31", noti time "14:08:02"

  @skip
    # Skipping for now because we're now displaying 'cancelled' events on the Overview screen
  Scenario: Cancel a DR event
    Given Login with admin
    When I add Customer name "foobar", utility id "123", contact name "test" and phone number "123456789"
    And I add site with customer name "foobar", site name "site1", site ID "123", VEN Name "test", Site Location Code "1233", IPV6 add "1", Site Add "address1", city "city1", state "CA", zip "99999", contact name "name1", phone number "123456"
    And I add a DR Program name "dr_program_test" with all sites
    And I click on Overview
    And I add a DR Event with DR program "dr_program_test", customer "foobar", site "(foobar) site1", noti date "2020-10-31", noti time "14:08:02", start date "2020-10-31", start time "14:08:42", end date "2020-10-31", end time "14:09:03"
    And I cancel a DR Event with DR program "dr_program_test"
    Then I should see no DR event with DR program "dr_program_test"

