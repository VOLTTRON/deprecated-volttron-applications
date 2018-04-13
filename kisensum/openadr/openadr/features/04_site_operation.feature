Feature: Test some operation with Site objects

  Scenario: Add a site
    Given Login with admin
    When I add Customer name "foobar", utility id "123", contact name "test" and phone number "123456789"
    And I add site with customer name "foobar", site name "site1", site ID "123", VEN Name "test", Site Location Code "1233", IPV6 add "1", Site Add "address1", city "city1", state "CA", zip "99999", contact name "name1", phone number "123456"
    Then I should see a site with customer name "foobar", site name "site1", site ID "123"

  Scenario: Create new site through customer in Overview
    Given Login with admin
    When I add Customer name "foobar", utility id "123", contact name "test" and phone number "123456789"
    And I create a site with customer name "foobar", site name "site1", site ID "123", VEN Name "test", Site Location Code "1233", IPV6 add "1", Site Add "address1", city "city1", state "CA", zip "99999", contact name "name1", phone number "123456"
    Then I should see a site with customer name "foobar", site name "site1", site ID "123"

  Scenario: Delete a site
    Given Login with admin
    When I add Customer name "foobar", utility id "123", contact name "test" and phone number "123456789"
    And I add site with customer name "foobar", site name "site1", site ID "123", VEN Name "test", Site Location Code "1233", IPV6 add "1", Site Add "address1", city "city1", state "CA", zip "99999", contact name "name1", phone number "123456"
    And I add a DR Program name "dr_program_test" with all sites
    And I delete the site with name "site1"
    Then I should see no site with name "site1" from customer "foobar", DR Program "dr_program_test"