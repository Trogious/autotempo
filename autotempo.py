#!/usr/bin/env python3

import requests
import os
import datetime
import itertools
import sys
import json


AT_USERNAME = os.getenv('AT_USERNAME')
AT_PASSWORD = os.getenv('AT_PASSWORD')
AT_BASE_URL = os.getenv('AT_BASE_URL')
AT_APPROVAL_PROJECT_IDS = os.getenv('AT_APPROVAL_PROJECT_IDS', '').split(',')
AT_EXCLUDE_MEMBERS = os.getenv('AT_EXCLUDE_MEMBERS', '').split(',')
AT_TEAM_LEAD = os.getenv('AT_TEAM_LEAD', AT_USERNAME)
AT_WEEKS_FORWARD = int(os.getenv('AT_WEEKS_FORWARD', 2))
AT_AUTH = (AT_USERNAME, AT_PASSWORD)
AT_HEADERS = {'Content-Type': 'application/json', 'Accept': 'application/json'}
AT_MORE_THAN_ONE = 'more_than_one_in_a_week'


def log(log_item):
    sys.stderr.write(datetime.datetime.now().isoformat(sep='_')[:19] + ': ' + str(log_item) + '\n')
    sys.stderr.flush()


def jira_post(url, data):
    return requests.post(url, headers=AT_HEADERS, auth=AT_AUTH, data=data)


def jira_put(url, data):
    return requests.put(url, headers=AT_HEADERS, auth=AT_AUTH, data=data)


def jira_get(url):
    return requests.get(url, headers=AT_HEADERS, auth=AT_AUTH)


def copy_only(input_dict, keys):
    return {k: v for k, v in input_dict.items() if k in keys}


def approve_plan(plan):
    approval = {}
    approval['assignee'] = copy_only(plan['assignee'], ['key', 'userKey', 'type'])
    approval['planItem'] = copy_only(plan['planItem'], ['key', 'id', 'type'])
    approval['scope'] = copy_only(plan['scope'], ['id', 'type'])
    approval['start'] = plan['start']
    approval['end'] = plan['end']
    approval['commitment'] = plan['commitment']
    approval['planApproval'] = {}
    approval['planApproval']['requester'] = copy_only(plan['planApproval']['requester'], ['key', 'name'])
    approval['planApproval']['reviewer'] = copy_only(plan['planApproval']['reviewer'], ['key', 'name'])
    approval['planApproval']['statusCode'] = 3
    log('approving: ' + plan['planItem']['key'] + ':' + str(plan['id']) + ' on ' + plan['start'] + '--' + plan['end'] + ' for: ' + plan['planApproval']['requester']['key'])
    resp = jira_put(AT_BASE_URL + '/rest/tempo-planning/1/allocation/' + str(plan['id']), json.dumps(approval))
    if 200 != resp.status_code:
        log(str(resp.status_code) + ': ' + resp.reason)


def get_team_members():
    members = []
    resp = jira_get(AT_BASE_URL + '/rest/tempo-teams/1/team')
    if 200 == resp.status_code:
        team_ids = []
        for team in resp.json():
            if AT_TEAM_LEAD == team['lead']:
                team_ids.append(team['id'])
        for tid in team_ids:
            resp = jira_get(AT_BASE_URL + '/rest/tempo-teams/2/team/' + str(tid) + '/member')
            if 200 == resp.status_code:
                for member in resp.json():
                    if member['member']['activeInJira'] and member['member']['key'] not in AT_EXCLUDE_MEMBERS:
                        members.append(member['member']['key'])
    else:
        log(str(resp.status_code) + ': ' + resp.reason)
    return members


def get_date_from_str(date_str):
    date = map(lambda x: int(x), date_str.split('-'))
    return datetime.date(*date)


def add_approval(user, plan, date, approvals):
    week = date.isocalendar()[1]
    if user in approvals.keys():
        approvals[user].append((week, plan['planItem']['key'], plan))
    else:
        approvals[user] = [(week, plan['planItem']['key'], plan)]


def collect_for_auto_approve(plan, members, approvals):
    approval = plan['planApproval']
    if approval['statusCode'] in [1, 3] and 'key' in plan['planItem'].keys() and plan['planItem']['key'] in AT_APPROVAL_PROJECT_IDS and approval['requester']['key'] in members and AT_TEAM_LEAD == approval['reviewer']['key']:
        start_date = get_date_from_str(plan['start'])
        end_date = get_date_from_str(plan['end'])
        diff_days = (end_date - start_date).days
        start_week_day = start_date.isocalendar()[2]
        if diff_days == 0:
            add_approval(approval['requester']['key'], plan, start_date, approvals)
        elif diff_days == 3 and start_week_day == 5:
            add_approval(approval['requester']['key'], plan, start_date, approvals)
            add_approval(approval['requester']['key'], plan, end_date, approvals)


# def log_week_group(wg, u):
#    log('%d %s %s %s' % (wg[0], wg[1], wg[2]['start'] + '--' + wg[2]['end'] + ' ' + str(AT_MORE_THAN_ONE in wg[2].keys()), u))


def remove_duplicated_plans(plans):
    groupped = itertools.groupby(plans, key=lambda p: p['id'])
    plans[:] = [next(group[1]) for group in groupped]


def verify_week_groups(week_groups, approved_plans, date_now):
    for week_groupper in week_groups:
        week_grouper1, week_grouper2 = itertools.tee(week_groupper[1])
        same_in_one_week = len(list(week_grouper1))
        if same_in_one_week == 1:
            for week_group in week_grouper2:
                plan = week_group[2]
                if AT_MORE_THAN_ONE not in plan.keys() and plan['planApproval']['statusCode'] == 1:
                    updated_date = get_date_from_str(plan['updated'])
                    end_date = get_date_from_str(plan['end'])
                    if (date_now - updated_date).days > 1 and -8 < (end_date - date_now).days < (AT_WEEKS_FORWARD * 7) + 1:
                        approved_plans.append(plan)
        else:
            for week_group in week_grouper2:
                week_group[2][AT_MORE_THAN_ONE] = True
                for ap in approved_plans:
                    if ap['id'] == week_group[2]['id']:
                        approved_plans.remove(ap)
                        break


def verify_for_auto_approve(approvals, date_now):
    approved_plans = []
    for user in approvals.keys():
        approvals[user].sort(key=lambda x: x[1])
        groupped = itertools.groupby(approvals[user], key=lambda x: x[1])
        for groupper in groupped:
            project_groups = []
            for group in groupper[1]:
                project_groups.append(group)
            project_groups.sort(key=lambda x: x[0])
            groupped_by_week = itertools.groupby(project_groups, key=lambda x: x[0])
            verify_week_groups(groupped_by_week, approved_plans, date_now)
    remove_duplicated_plans(approved_plans)
    return approved_plans


def handle_approvals(resp, date_now):
    members = get_team_members()
    approved = 0
    if len(members) > 0:
        approvals = {}
        for r in resp:
            if 'planApproval' in r.keys():
                collect_for_auto_approve(r, members, approvals)
        for plan in verify_for_auto_approve(approvals, date_now):
            approve_plan(plan)
            approved = approved + 1
    return approved


def main():
    if None not in [AT_USERNAME, AT_PASSWORD, AT_BASE_URL] and len(AT_APPROVAL_PROJECT_IDS) > 0 and len(AT_APPROVAL_PROJECT_IDS[0]) > 0:
        time_now = datetime.datetime.now()
        start_date = time_now - datetime.timedelta(weeks=1)
        end_date = time_now + datetime.timedelta(weeks=AT_WEEKS_FORWARD + 1)
        resp = jira_get(AT_BASE_URL + '/rest/tempo-planning/1/allocation?startDate=' + start_date.isoformat()[:10] + '&endDate=' + end_date.isoformat()[:10])
        if 200 == resp.status_code:
            return handle_approvals(resp.json(), time_now.date())
        else:
            log(str(resp.status_code) + ': ' + resp.reason)
    else:
        log('required env variables NOT set')
    return 0


def lambda_handler(events, context):
    return main()


if __name__ == '__main__':
    main()
