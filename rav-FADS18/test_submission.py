#!/usr/bin/env python

import os
import re
import glob
import shutil
import socket
import argparse
import requests
import tempfile
import subprocess
from domjudge import get_problems, get_team_names
from instrument import instrument
import judge


REPO = {
    'alcyone': '/home/rav/work/submitj',
    'gonzales': '/ssd/home/work/csaudk-submitj',
    'novascotia': '/home/rav/codes/submitj',
}


def gethostname():
    global gethostname
    value = socket.gethostname()
    gethostname = lambda: value
    return value


def make_parser(c):
    assert len(c) == 1

    def parse(s):
        if s.startswith(c):
            return int(s[1:])
        else:
            return int(s)

    return parse


parse_problem_id = make_parser('p')
parse_team_id = make_parser('t')
parse_submission_id = make_parser('s')


parser = argparse.ArgumentParser()
parser.add_argument('-V', '--version', dest='override_version', type=int)
parser.add_argument('-n', '--no-patch', dest='patch', action='store_false')
parser.add_argument('-o', '--no-extract', dest='extract', action='store_false')
parser.add_argument('-i', '--no-instrument', dest='instrument', action='store_false')
parser.add_argument('submission_id', type=parse_submission_id)


def setup_submission(submission_id, problems, teams):
    directory = 'submissions/inbox'
    files = glob.glob('%s/c*.s%s.t*.p*.*' % (directory, submission_id))
    if not files:
        raise ValueError(submission_id)
    target_directory = set()
    to_copy = []
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
        to_copy.append((f, filename))

    assert len(target_directory) == 1
    d, = target_directory
    return d, to_copy, problem_name


def extract(d, to_copy):
    paths = []
    for f, filename in to_copy:
        path = os.path.join(d, filename)
        os.makedirs(d, exist_ok=True)
        shutil.copyfile(f, path)
        paths.append(path)

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
                    fp.write('try { %s.testAll(); }\n' % class_name)
                    fp.write('catch (Exception e) { e.printStackTrace(); }\n')
                    fp.write('}}\n')
            except FileExistsError:
                pass
            return f
    else:
        print("No testAll() found.")


version_prefix = '// Version: '


def get_version(path):
    pattern = r'^%s(\d+)$' % re.escape(version_prefix)
    with open(path) as fp:
        try:
            mo = next(mo for line in fp
                      for mo in [re.match(pattern, line)]
                      if mo is not None)
        except StopIteration:
            raise ValueError(path)
    return int(mo.group(1))


def find_commit_after_version(version, directory, filename):
    cmdline = ('git', 'log', '-1', '-S', '%s%s' % (version_prefix, version),
               '--format=%H', '--', filename)
    hash = subprocess.check_output(cmdline, cwd=directory, universal_newlines=True)
    if not hash:
        raise ValueError(version)
    return '%s^' % hash.strip()


def find_patch(hash, directory, filename):
    cmdline = ('git', 'diff', '%s..HEAD' % hash, '--', filename)
    return subprocess.check_output(cmdline, cwd=directory, universal_newlines=True)


def apply_patch(patch, filename):
    basename = os.path.basename(filename)
    with tempfile.TemporaryDirectory() as tmpdir:
        # Open input in text mode to convert CR+LF into LF.
        # We cannot use shutil.copyfile since that preserves line endings.
        target = os.path.join(tmpdir, basename)
        with open(filename) as fsrc, open(target, 'w') as fdst:
            shutil.copyfileobj(fsrc, fdst)
        with tempfile.NamedTemporaryFile('w') as patchfile:
            patchfile.write(patch)
            patchfile.flush()
            subprocess.check_call(
                ('patch', basename, patchfile.name),
                cwd=tmpdir)
            with open(os.path.join(tmpdir, basename)) as fp:
                patched = fp.read()
    with open(filename + '.tmp', 'x') as fp:
        fp.write(patched)
    os.rename(filename + '.tmp', filename)


def print_added_tests(patch):
    added = set()
    removed = set()
    methods = {'+': added, '-': removed}
    for line in patch.splitlines():
        mo = re.match(r'^([+-])\s*public static void ([a-z0-9A-Z]+)', line)
        if mo:
            methods[mo.group(1)].add(mo.group(2))
    new = added - removed
    if new:
        print("Add methods %s" %
              ', '.join(sorted(new, key=lambda s: (len(s), s))))


def patch_test_file(directory, filename, problem, current_version=None):
    if current_version is None:
        current_version = get_version(os.path.join(directory, filename))
    repo = REPO[gethostname()]
    dir_in_repo = 'tasks/%s' % problem.rstrip('12')
    dir_path = os.path.join(repo, dir_in_repo)
    repo_path = os.path.join(dir_path, filename)
    try:
        newest_version = get_version(repo_path)
    except FileNotFoundError:
        print("It would appear the student has submitted to the wrong problem")
        raise
    if current_version == newest_version:
        print("Version %s is the current version" % current_version)
        return
    if current_version > newest_version:
        raise ValueError((current_version, newest_version))
    print("Patching from version %s to version %s" %
          (current_version, newest_version))
    patch = find_patch(
        find_commit_after_version(current_version, dir_path, filename),
        dir_path, filename)
    print_added_tests(patch)
    apply_patch(patch, os.path.join(directory, filename))
    assert get_version(os.path.join(directory, filename)) == newest_version


def remove_package(paths):
    subprocess.check_call(
        ('sed', '-i', '-e', '/package [_a-z0-9.]*;/ d') + tuple(paths))


def get_testcases(problem_name):
    return glob.glob('../../fads-problems/%s/data/*/*.in' % problem_name)


def main(session):
    args = parser.parse_args()
    problems = get_problems(session)
    teams = get_team_names(session)
    directory, target_files, problem_name = setup_submission(
        args.submission_id, problems, teams)
    if args.extract:
        paths = extract(directory, target_files)
        test_file = setup_testall(paths)
    else:
        paths = glob.glob(os.path.join(directory, '*.java'))
        paths = [p for p in paths if not p.endswith('/RunTestAll.java')]
        test_files = [os.path.basename(path) for path in paths
                      if any('testAll()' in line for line in open(path))]
        assert len(test_files) == 1, test_files
        test_file, = test_files
    print("Stored in %s" % directory)

    if directory:
        remove_package(paths)
        if args.patch:
            patch_test_file(directory, test_file, problem_name,
                            args.override_version)
        if args.instrument:
            for path in paths:
                instrument(path)
        subprocess.check_call(['javac'] + glob.glob('%s/*.java' % directory))
        subprocess.check_call(('java', '-cp', directory, 'RunTestAll'))

        main_files = [os.path.basename(path) for path in paths
                      if any('void main(' in line for line in open(path))]
        main_file, = main_files
        for testcase in get_testcases(problem_name):
            print(testcase)
            try:
                judge.main([os.path.join(directory, main_file), testcase])
            except SystemExit as e:
                print(e.args[0])


if __name__ == '__main__':
    with requests.Session() as session:
        main(session)
