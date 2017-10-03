#!/usr/bin/env python

import os
import glob
import shutil
import argparse
import requests
import subprocess
from domjudge import get_problems, get_team_names


def parse_problem_id(s):
    if s.startswith('p'):
        return int(s[1:])
    else:
        return int(s)


def parse_team_id(s):
    if s.startswith('t'):
        return int(s[1:])
    else:
        return int(s)


def parse_submission_id(s):
    if s.startswith('s'):
        return int(s[1:])
    else:
        return int(s)


parser = argparse.ArgumentParser()
parser.add_argument('submission_id', type=parse_submission_id)


def setup_submission(submission_id, problems, teams):
    directory = 'submissions/inbox'
    files = glob.glob('%s/c*.s%s.t*.p*.*' % (directory, submission_id))
    if not files:
        raise ValueError(submission_id)
    target_directory = set()
    paths = []
    for f in files:
        full = os.path.basename(f)
        (contest_id, submission_id_, team_id, problem_id,
         language, attempt, filename) = full.split('.', 6)
        assert parse_submission_id(submission_id_) == submission_id
        team_name = teams[parse_team_id(team_id)]
        problem_name = problems[parse_problem_id(problem_id)]
        d = 'submissions/{p}/{t}-s{s}'.format(
            p=problem_name, t=team_name, s=submission_id)
        target_directory.add(d)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, filename)
        shutil.copyfile(f, path)
        paths.append(path)
    assert len(target_directory) == 1
    d, = target_directory
    print("Stored in %s" % d)
    assert len(paths) >= 1
    return paths


def setup_testall(paths):
    for p in paths:
        d, f = os.path.split(p)
        class_name, ext = os.path.splitext(f)
        if ext != '.java':
            continue
        with open(p) as fp:
            b = any('testAll()' in line for line in fp)
        if b:
            try:
                with open(os.path.join(d, 'RunTestAll.java'), 'x') as fp:
                    fp.write('public class RunTestAll {\n')
                    fp.write('public static void main(String[] a) {\n')
                    fp.write('%s.testAll();\n' % class_name)
                    fp.write('}}\n')
            except FileExistsError:
                pass
            return d
    else:
        print("No testAll() found.")


def main():
    session = requests.Session()
    args = parser.parse_args()
    problems = get_problems(session)
    teams = get_team_names(session)
    paths = setup_submission(args.submission_id, problems, teams)
    directory = setup_testall(paths)
    if directory:
        subprocess.check_call(['javac'] + glob.glob('%s/*.java' % directory))
        subprocess.check_call(('java', '-cp', directory, 'RunTestAll'))


if __name__ == '__main__':
    main()
