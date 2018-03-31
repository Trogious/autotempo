# autotempo
Automatically approves plans for certain JIRA project IDs based on fixed criteria.

### Requirements
requests >= 2.18

### Environment variables
`AT_USERNAME` - **required** JIRA user ID

`AT_PASSWORD` - **required** JIRA password

`AT_BASE_URL` - **required** JIRA Web URL

`AT_APPROVAL_PROJECT_IDS` - **required** list of JIRA IDs of issues users use as plans in TEMPO

`AT_EXCLUDE_MEMBERS` - *optional* list of user IDs that the auto approval should ignore

`AT_TEAM_LEAD` - *optional* owner of the TEMPO teams whose members should be subjected to auto approval, defaults to: `AT_USERNAME`

`AT_WEEKS_FORWARD` - *optional* number of weeks to look forward for reported plans, dafaults to: 2

##### Miscellaneous
Ready to be run on AWS Lambda.
