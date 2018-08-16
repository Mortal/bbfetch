'''
Fetch DOMjudge scoreboard, match with Blackboard groups,
and upload DOMjudge points to Blackboard Grade Centre.


INSTALLATION
============

This script depends on bbfetch, so you must first run

    pip install --user https://github.com/Mortal/bbfetch/archive/master.zip

... and create a file named `grading.py` based on the contents of:
https://github.com/Mortal/bbfetch/blob/master/rav-FADS17/grading.py


USAGE
=====

First, you should add Grade Centre columns manually and retrieve their IDs.

Then you should set up problems.csv with the submission deadlines of the
different DOMjudge problems.

In override.json you can specify that certain groups should get points for
problems even though they didn't submit an accepted solution by the deadline.

You should use grading.py to fetch the list of student group memberships.

Finally you can run this script to upload points to Blackboard.


Creating Grade Centre columns
-----------------------------

Go to Blackboard's "Full Grade Centre" and click "Create Column".
'''
import re
import csv
import json
import argparse
import datetime
import collections
from domjudge import get_scoreboard
from grading import Grading
from bbfetch.base import ParserError, logger
from bbfetch.backend import upload_csv


parser = argparse.ArgumentParser()
parser.add_argument('-u', '--upload', action='store_true')


def get_problems():
    problems = collections.OrderedDict()
    with open('problems.csv', newline='') as fp:
        c = csv.reader(fp)
        header = next(c)
        assert header == ['Problem id', 'Deadline', 'Points', 'Grade centre CSV name']
        for problem_id, deadline, points, column in c:
            deadline = datetime.datetime.strptime(deadline, '%Y-%m-%d %H:%M')
            points = int(points)
            problems[problem_id] = (deadline, points, column)
    return problems


def add_overrides(scoreboard):
    try:
        with open('override.json') as fp:
            override = json.load(fp)
    except FileNotFoundError:
        return scoreboard
    for team_name, team_override in override.items():
        assert team_name in scoreboard
        for label, comment in team_override.items():
            assert isinstance(comment, str)
            scoreboard[team_name][label] = (True, comment)
    return scoreboard


def get_points(grading):
    problem_info = get_problems()
    scoreboard = get_scoreboard(grading.session.session)
    scoreboard = add_overrides(scoreboard)
    grade_centre_rows = []
    problem_columns = (
        sorted(set(column_name for deadline, points, column_name in problem_info.values())))
    grade_centre_columns = ['Username'] + problem_columns
    output_rows = []
    output_columns = (
        ['Name', 'Username', 'Group', 'Total'] + problem_columns + list(problem_info.keys()))
    short_problem_columns = [re.sub(r' \[Total Pts: \d+\] \|\d+$', '', c)
                             for c in problem_columns]
    short_output_columns = (
        ['Name', 'Username', 'Group', 'Total'] + short_problem_columns + list(problem_info.keys()))
    for student in grading.gradebook.students.values():
        team_name = grading.get_domjudge_team_name(student)
        grade_centre_row = {
            'Username': student.username,
        }
        grade_centre_rows.append(grade_centre_row)

        data = {
            'Username': student.username,
            'Name': student.name,
            'Total': 0,
        }
        output_rows.append(data)

        for n in problem_columns:
            data[n] = grade_centre_row[n] = 0

        if not team_name:
            data['Group'] = 'None'
            continue
        problems = scoreboard[team_name]
        data['Group'] = team_name
        for label, (solved, time) in problems.items():
            try:
                deadline, points, column_name = problem_info[label]
            except KeyError:
                # Demo problem -> Skip
                continue
            if isinstance(time, datetime.datetime):
                time_str = time.strftime('%Y-%m-%d %H:%M')
            else:
                time_str = str(time)
            if solved and (isinstance(time, str) or time < deadline):
                data[label] = '%s (%s)' % (points, time_str)
                grade_centre_row[column_name] += points
                data[column_name] += points
                data['Total'] += points
            elif solved:
                data[label] = '0 (Late: %s)' % time_str
            else:
                data[label] = '0 (Attempted)'
    output_rows.sort(key=lambda r: (r['Group'], r['Name']))
    with open('judgepoints.csv', 'w') as fp:
        wr = csv.writer(fp)
        wr.writerow(short_output_columns)
        wr.writerows([[str(r.get(c, '')) for c in output_columns]
                      for r in output_rows])
    with open('gradecentre.csv', 'w') as fp:
        wr = csv.writer(fp)
        wr.writerow(grade_centre_columns)
        wr.writerows([[str(r.get(c, '')) for c in grade_centre_columns]
                      for r in grade_centre_rows])


def main():
    args = parser.parse_args()
    grading = Grading.init()
    get_points(grading)
    if args.upload:
        with open('gradecentre.csv') as fp:
            rd = iter(csv.reader(fp))
            columns = next(rd)
            rows = list(rd)
        try:
            upload_csv(grading.session, columns, rows)
        except ParserError as exn:
            try:
                grading.session.relogin()
                upload_csv(grading.session, columns, rows)
            except ParserError as exn:
                logger.error("Parsing error")
                print(exn)
                exn.save()


if __name__ == '__main__':
    main()
