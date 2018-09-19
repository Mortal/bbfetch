'''
Generates student-passwords-YEAR.{ipe,pdf,txt}.
The text file can be fed to /usr/local/bin/create_accounts,
but remember to update create_accounts to $CATID=2; (Self-Registered)
and $ROLES=array(3); (Team) before creating the accounts.
'''
import argparse
import textwrap
import subprocess


parser = argparse.ArgumentParser()
parser.add_argument('-y', '--year', type=int, required=True)
parser.add_argument('-c', '--classes', type=int, required=True)
parser.add_argument('--hold', type=int, default=0)
parser.add_argument('-g', '--groups', type=int, required=True)
parser.add_argument('-l', '--password-length', type=int, default=10)
parser.add_argument('-R', '--rows', type=int, default=10)
parser.add_argument('-C', '--columns', type=int, default=2)


def make_passwords(pw_length, num_pw):
    output = subprocess.check_output(
        ('pwgen', '-cBn', str(pw_length), str(num_pw)),
        universal_newlines=True)
    passwords = output.split()
    if len(passwords) != num_pw:
        raise ValueError('pwgen failed to return right number of passwords')
    if any(len(p) != pw_length for p in passwords):
        raise ValueError('pwgen failed to return right length of passwords')
    return passwords


def make_passwords_dict(password_length, classes, groups):
    password_list = make_passwords(password_length,
                                   len(classes) * groups)
    password_iter = iter(password_list)
    passwords = {}
    for c in classes:
        for g in range(groups):
            key = '%s-%02d' % (c, g+1)
            passwords[key] = next(password_iter)
    return passwords


def make_ipe_source(fp, passwords, classes, rows, columns):
    width = 595
    height = 842
    col_width = width / columns  # 297.5
    row_height = height / rows  # 84.2

    fp.write(textwrap.dedent(r'''
        <?xml version="1.0"?>
        <!DOCTYPE ipe SYSTEM "ipe.dtd">
        <ipe version="70206" creator="Ipe 7.2.7">
        <preamble>\newcommand{\outputcode}[2]{User: \texttt{#1} Password: \texttt{#2}}</preamble>
        <ipestyle name="basic"><layout paper="%(width)s %(height)s" origin="0 0" frame="%(width)s %(height)s" crop="no"/>
        </ipestyle>
        <page>
    ''').lstrip() % dict(width=width, height=height))
    for c in classes:
        fp.write('<layer name="l%s"/>\n' % c)
    for c in classes:
        fp.write('<view layers="l%s" active="l%s"/>\n' % (c, c))
    for c in classes:
        fp.write('<group layer="l%s">\n' % c)
        group = 1
        for col in range(columns):
            x = (col + 0.5) * col_width
            for row in range(rows):
                y = (rows - row - 0.5) * row_height
                user = '%s-%02d' % (c, group)
                group += 1
                try:
                    pw = passwords[user]
                except KeyError:
                    if group == 2:
                        # No passwords -- reraise
                        raise
                    continue
                fp.write(textwrap.dedent(r'''
                    <text pos="%(x)s %(y)s" stroke="black" type="label"
                    halign="center" valign="center">
                    \outputcode{%(user)s}{%(pw)s}</text>
                ''').lstrip() % dict(x=x, y=y, user=user, pw=pw))
        fp.write('</group>\n')
    fp.write('</page>\n</ipe>\n')


def main():
    args = parser.parse_args()
    prefix = 'fads%s-' % (args.year % 100)
    class_names = (
        [prefix + 'da%s' % (c+1) for c in range(args.classes)]
        + [prefix + 'hold%s' % (c+1) for c in range(args.hold)]
    )
    passwords = make_passwords_dict(
        args.password_length, class_names, args.groups)
    base = 'student-passwords-%s' % args.year
    with open('%s.txt' % base, 'x') as fp:
        for k, v in sorted(passwords.items()):
            fp.write('%s %s\n' % (k, v))
    with open('%s.ipe' % base, 'x') as fp:
        make_ipe_source(fp, passwords, class_names,
                        args.rows, args.columns)
    subprocess.check_call(
        ('ipetoipe', '-pdf', '%s.ipe' % base, '%s.pdf' % base))
    print('Created %s.{pdf,txt}.\n' % base +
          'Check that /usr/local/bin/create_accounts uses the right ' +
          'CATID and ROLES,\n' +
          'and feed %s.txt to create_accounts to create the accounts.' % base)


if __name__ == '__main__':
    main()
