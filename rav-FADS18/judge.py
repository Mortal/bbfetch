#!/usr/bin/env python

import os
import shlex
import argparse
import tempfile
import functools
import contextlib
import subprocess


AC, WA = 'AC', 'WA'
EXIT_AC = 42
EXIT_WA = 43


def testcase_input(s):
    base, ext = os.path.splitext(s)
    if ext != '.in':
        raise ValueError('Expected testcase ending in .in')
    if not os.path.exists(s):
        raise FileNotFoundError(s)
    ans = base + '.ans'
    if not os.path.exists(ans):
        raise FileNotFoundError(ans)
    return s, ans


def runnable(s):
    base, ext = os.path.splitext(s)
    if ext == '.py':
        if not os.path.exists(s):
            raise FileNotFoundError(s)
        return ('python', s)
    elif ext == '.java':
        compiled = base + '.class'
        if not os.path.exists(compiled):
            raise FileNotFoundError(compiled)
        dirname = os.path.dirname(base)
        class_name = os.path.basename(base)
        if not dirname:
            return ('java', class_name)
        return ('java', '-cp', dirname, class_name)
    else:
        raise ValueError('unknown extension %r' % ext)


def get_output_validator_path(testcase_input):
    return os.path.join(
        os.path.dirname(testcase_input) or '.',
        '../../output_validators/run')


def is_executable(path):
    return os.access(path, os.X_OK, effective_ids=True)


def judge(input, answer, program):
    program_cmdline = ' '.join(map(shlex.quote, program))
    program_with_input = '%s < %s' % (program_cmdline,
                                      shlex.quote(input))
    with contextlib.ExitStack() as stack:
        output_validator = get_output_validator_path(input)
        has_output_validator = is_executable(output_validator)
        if has_output_validator:
            temp_dir = stack.enter_context(tempfile.TemporaryDirectory())
            validator_line = ' '.join(
                map(shlex.quote, (output_validator, input, answer, temp_dir)))
        else:
            validator_line = 'diff %s -' % shlex.quote(answer)

        bash_line = '%s | %s' % (
            program_with_input, validator_line)
        print(bash_line)
        returncode = subprocess.call(('bash', '-c', bash_line))

        if has_output_validator:
            if returncode == EXIT_AC:
                return AC
            elif returncode == EXIT_WA:
                with open(os.path.join(temp_dir, 'judgemessage.txt')) as fp:
                    print(fp.read(), end='')
                return WA
        else:
            if returncode == 0:
                return AC
            elif returncode == 1:
                return WA
        return 'judging-error(%s)' % returncode


parser = argparse.ArgumentParser()
parser.add_argument('program', type=runnable)
parser.add_argument('testcase', type=testcase_input)


def main(args=None):
    args = parser.parse_args(args)
    input, answer = args.testcase
    r = judge(input, answer, args.program)
    if r == AC:
        print('accepted')
    elif r == WA:
        raise SystemExit('wrong-answer')
    else:
        raise SystemExit(str(r))


if __name__ == '__main__':
    main()
