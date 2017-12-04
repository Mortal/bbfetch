import os
import re
import sys
import subprocess
import collections
from judgepoints import get_problems


SubmissionBase = collections.namedtuple(
    'Submission', 'id team problem language judging verifier')


class Submission(SubmissionBase):
    @property
    def team_problem(self):
        return (self.team, self.problem)


def get_submissions(s):
    solved = []
    other_teams = []
    other_langs = []
    submissions = []
    for submission in parse_submissions(s):
        if submission.judging == 'correct':
            solved.append(submission.team_problem)
            continue
        mo = re.match(r'fads(\d+)-da(\d+)-(\d+)', submission.team)
        if mo is None:
            other_teams.append(submission.team)
            continue
        if submission.language != 'java':
            other_langs.append(submission.language)
            continue
        submissions.append(submission)
    if other_teams:
        print('Skip solutions by %s' % ', '.join(sorted(set(other_teams))))
    if other_langs:
        print('Skip solutions in %s' % ', '.join(sorted(set(other_langs))))
    solved = set(solved)
    return solved, submissions


def pager(s):
    p = subprocess.Popen(
        ('/usr/bin/less',),
        env=dict(os.environ, LESS='FRX'),
        stdin=subprocess.PIPE,
        universal_newlines=True)
    p.communicate(s)
    p.wait()


def main():
    solved, submissions = get_submissions(sys.stdin.read())
    problem_round = {
        problem_id: deadline
        for problem_id, (deadline, points, column) in get_problems().items()}

    def submission_disc(s: Submission):
        return (
            s.judging != 'timelimit' or not s.problem.endswith('2'),
            s.problem in problem_round,
            problem_round.get(s.problem),
            # s.team_problem not in solved,
        )

    def submission_key(s: Submission):
        return (
            s.judging == 'timelimit' and s.problem.endswith('2'),
            s.problem,
            s.judging != 'wrong-answer',
            hash(s.team),
            -s.id)

    unsolved_last_attempt = {}
    for s in sorted(submissions, key=lambda s: s.id):
        if s.judging == 'timelimit' and s.problem.endswith('2'):
            continue
        if s.team_problem not in solved:
            unsolved_last_attempt[s.team_problem] = s

    o = max(submission_disc(s) for s in submissions)
    submissions = sorted((s for s in submissions if submission_disc(s) == o),
                         key=submission_key)

    def format_submission(s: Submission):
        return '\t'.join(
            map(str, (s.id, s.team_problem in solved,
                      s.team, s.problem, s.judging, s.verifier)))

    problem_data = '\n'.join(format_submission(s) for s in submissions)
    if unsolved_last_attempt:
        problem_data = (
            'Teams with unsolved problems:\n%s\n\n' %
            '\n'.join(format_submission(s)
                      for s in unsolved_last_attempt.values()) +
            'Other submissions:\n%s' % problem_data)
    pager(problem_data)


def parse_submissions(s):
    header_pattern = (
        r'\A\n*home .*\ntime left:.*\ncontest:.*\nlogged in as .*\n' +
        r'Submissions\n\nShow submissions:\n' +
        r'ID\ttime\tteam\tproblem\tlang\tresult\tverified\tby\n')
    mo = re.match(header_pattern, s)
    if mo is None:
        print("Couldn't find header.")
        return
    s = s[mo.end(0):]
    i = 0
    pattern = (
        r's(?P<submission>\d+)\n\t\n(?P<time>\d+:\d+)\n\t\n' +
        r'(?P<team>.*)\n\t\n(?P<problem>.*)\n\t\n(?P<language>.*)\n\t\n' +
        r'(?P<judging>.*)\n\t\n(?P<verified>yes|no|claimed)\n\t\n(?P<by>.*)\n')
    for mo in re.finditer(pattern, s):
        j = mo.start(0)
        if i != j:
            raise Exception("Unmatched: %r" % (s[i:j],))
        i = mo.end(0)

        yield Submission(
            int(mo.group('submission')),
            mo.group('team'),
            mo.group('problem'),
            mo.group('language'),
            mo.group('judging'),
            mo.group('by') if mo.group('verified') == 'yes' else None)


if __name__ == '__main__':
    main()
