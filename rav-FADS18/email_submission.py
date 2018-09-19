import os
import re
import glob
import argparse
import textwrap
import subprocess
import urllib.parse
from test_submission import (
    parse_problem_id, parse_team_id,
    parse_submission_id, get_problems, get_team_names,
)
from group_emails import search_group_emails


def compose_email(recipients, subject, body):
    link = ('mailto:%s?' % ','.join(recipients) +
            urllib.parse.urlencode([('subject', subject),
                                    ('body', body)],
                                   quote_via=urllib.parse.quote))
    subprocess.check_call(('claws-mail', '--compose', link))


judgings = dict(
    wa='wrong-answer',
    rte='run-error',
    tle='timelimit',
)



parser = argparse.ArgumentParser()
parser.add_argument('--judging', '-j',
                    type=lambda k: judgings[k], default='wa')
parser.add_argument('submission_id', type=parse_submission_id)


def analyze_submission(submission_id, problems, teams):
    directory = 'submissions/inbox'
    files = glob.glob('%s/c*.s%s.t*.p*.*' % (directory, submission_id))
    if not files:
        raise ValueError(submission_id)
    metadatas = set(tuple(os.path.basename(f).split('.', 6)[:5])
                    for f in files)
    if len(metadatas) != 1:
        print(metadatas)
    (contest_id, submission_id_, team_id, problem_id, language), = metadatas
    assert submission_id == parse_submission_id(submission_id_)

    team_name = teams[parse_team_id(team_id)]
    problem_name = problems[parse_problem_id(problem_id)]
    (group_name, students), = search_group_emails(team_name.split('-', 1)[1])
    return group_name, students, problem_name


def main(session=None):
    args = parser.parse_args()
    problems = get_problems(session)
    teams = get_team_names(session)
    group_name, students, problem_name = analyze_submission(
        args.submission_id, problems, teams)
    problem_name = re.sub(r'\d+$', '-2', problem_name)
    names = ' og '.join(n.split(' ')[0] for n, e in students)
    context = dict(
        names=names,
        group_name=group_name,
        judging=args.judging,
        problem=problem_name,
    )
    recipients = [email for name, email in students]
    subject = "'{judging}' på '{problem}'"
    body = textwrap.dedent('''
    Hej {names} ({group_name})

    Jeg kan se I har fået '{judging}' på FADS-opgaven '{problem}'.

    Jeg har tilføjet et nyt testcase til opgaven som forhåbentlig kan
    hjælpe jer med at finde jeres fejl.

    Mvh. Mathias Rav
    ''').strip()
    compose_email(recipients,
                  subject.format(**context),
                  body.format(**context))


if __name__ == '__main__':
    main()
