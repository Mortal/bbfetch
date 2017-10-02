import csv
import argparse
import datetime
import collections
from domjudge import get_scoreboard
from grading import Grading
from blackboard.base import ParserError, logger
from blackboard.backend import upload_csv


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


def get_points(grading):
    problem_info = get_problems()
    scoreboard = get_scoreboard(grading.session.session)
    grade_centre_rows = []
    problem_columns = (
        sorted(set(column_name for deadline, points, column_name in problem_info.values())))
    grade_centre_columns = ['Username'] + problem_columns
    output_rows = []
    output_columns = (
        ['Name', 'Username', 'Group'] + problem_columns + list(problem_info.keys()))
    for student in grading.gradebook.students.values():
        team_name = grading.get_domjudge_team_name(student)
        grade_centre_row = {
            'Username': student.username,
        }
        grade_centre_rows.append(grade_centre_row)

        data = {
            'Username': student.username,
            'Name': student.name,
        }
        output_rows.append(data)

        for n in problem_columns:
            data[n] = grade_centre_row[n] = 0

        if not team_name:
            data['Group'] = 'None'
            continue
        solved_problems = scoreboard[team_name]
        data['Group'] = team_name
        for label, time in solved_problems.items():
            try:
                deadline, points, column_name = problem_info[label]
            except KeyError:
                # Demo problem -> Skip
                continue
            if time < deadline:
                data[label] = '%s (%s)' % (points, time)
                grade_centre_row[column_name] += points
                data[column_name] += points
            else:
                data[label] = '0 (Late: %s)' % str(time)
    output_rows.sort(key=lambda r: (r['Group'], r['Name']))
    with open('judgepoints.csv', 'w') as fp:
        wr = csv.writer(fp)
        wr.writerow(output_columns)
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
            logger.error("Parsing error")
            print(exn)
            exn.save()


if __name__ == '__main__':
    main()
