Feature: Login, Logout and Change Password

  Scenario: Login with valid user and logout

    Given a valid user "foo" with password "bar"
    When I login with username "foo" and password "bar"
    Then I am redirected to the home page
    And I log out

  Scenario: Login with invalid user

    Given a valid user "foo" with password "bar"
    When I login with username "fu" and password "bar"
    Then I should see some error message at login page

  Scenario: Login and change password

    Given a valid user "foo" with password "bar"
    When I login with username "foo" and password "bar"
    And I change password
    Then I am redirected to the home page