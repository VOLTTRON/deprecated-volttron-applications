Feature: Test some operation with Customer objects

  Scenario: Add customer

    Given Login with username "foo" and password "bar"
    When I add Customer name "foobar", utility id "123", contact name "test" and phone number "123456789"
    Then I am redirected to the home page
    And I should see a Customer "foobar" with utility id "123"

  Scenario: Delete customer

    Given Login with admin
    When I add Customer name "foobar", utility id "123", contact name "test" and phone number "123456789"
    And I add site with customer name "foobar", site name "site1", site ID "123", VEN Name "test", Site Location Code "1233", IPV6 add "1", Site Add "address1", city "city1", state "CA", zip "99999", contact name "name1", phone number "123456"
    And I delete customer "foobar"
    Then I should not see Customer "foobar" nor the site "site1"

  Scenario: Edit customer in Overview

    Given Login with username "foo" and password "bar"
    When I add Customer name "foobar", utility id "123", contact name "test" and phone number "123456789"
    And I click on customer "foobar"
    And I change the name to "foofoobar" and id to "321" and click "save" and "Overview"
    Then I should see a Customer "foofoobar" with utility id "321"

  Scenario: Adding duplicate customers

    Given Login with username "foo" and password "bar"
    When I add Customer name "foobar", utility id "123", contact name "test" and phone number "123456789"
    And I add Customer name "foofoobar", utility id "123", contact name "test" and phone number "123456789"
    Then I should see error with utility already exists
