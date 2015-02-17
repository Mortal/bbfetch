import os
import re
import sys
import json
import zipfile
import argparse
import subprocess


FILENAME = re.compile(
    r'(?P<handin>[A-Za-z0-9 -]+)_(?P<group>[A-Za-z0-9 -]+)_' +
    r'forsøg_(?P<year>[0-9]{4})-(?P<month>[0-9]{2})-(?P<day>[0-9]{2})-' +
    r'(?P<hour>[0-9]{2})-(?P<minute>[0-9]{2})-(?P<second>[0-9]{2})' +
    r'(?P<suffix>.*)')


METADATA = re.compile(
    br'Navn: (?P<group>[A-Za-z0-9 -]+)\n' +
    br'Opgave: (?P<handin>[A-Za-z0-9 -]+)\n' +
    br'Dato for svar: (?P<time>[0-9a-zA-Z:. ]+)\n' +
    br'Aktuel karakter: (?:(?P<nograde>Endnu ikke karaktergivet)|(?P<grade>\d+\.?\d*))\n\n' +
    br'Svarfelt:\n(?P<answer>.*)\n\n' +
    br'Kommentarer:\n(?P<comments>.*)\n\n' +
    br'Filer:\n(?P<files>.*)\n',
    re.S)


NO_FILES = b'Der blev ikke vedh\xc3\xa6ftet filer til dette svar.'
FILES_FIELD = re.compile(
    br'\tOprindeligt filnavn: (?P<original>.+)\n\tFilnavn: (?P<filename>.+)\n')


EXTENSIONS = ['.pdf']


def guess_params():
    directory = os.path.expanduser('~/Downloads')
    filenames = os.listdir(directory)
    filenames = [
        os.path.join(directory, f)
        for f in filenames
        if f.startswith('gradebook_BB') and f.endswith('.zip')
    ]
    filenames.sort(key=lambda f: os.stat(f).st_mtime)
    filename = filenames[-1]
    print("File: %s" % filename)
    attempt = int(input("Attempt: "))
    return filename, attempt


def print_handin_info(i, group, data):
    try:
        with open(data['comments_file']) as fp:
            comments_size = os.fstat(fp.fileno()).st_size
            comments = '%d B comments' % comments_size
            first_line = fp.readline().strip()
    except FileNotFoundError:
        comments = 'no comments'
        first_line = ''
    annotated_file = os.path.splitext(data['file'])[0] + '.pep'
    if os.path.exists(annotated_file):
        annotations = 'annotated'
    else:
        annotations = 'not annotated'
    print("%d. %s (%s; %s) %s" % (i + 1, group, comments, annotations, first_line))


def previous_handin(group, data):
    handin = os.path.dirname(data['file'])
    o = re.match(r'(.*_)(\d+)', handin)
    print(o)
    if o:
        directory = o.group(1) + str(int(o.group(2)) - 1)
        print(directory)
        base = os.path.join(directory, group)
        annotated = base + '_handin_ann.pdf'
        print(annotated)
        if os.path.exists(annotated):
            return annotated


def handin_loop(i, handin):
    group, data = handin
    previous = previous_handin(group, data)
    print('')
    while True:
        print_handin_info(i, group, data)
        print("0. Back")
        print("1. Annotate and edit comments")
        if previous:
            print("2. Open annotated previous version")

        # Don't catch KeyboardInterrupt here
        j = int(input())

        if j == 1:
            subprocess.call(('pdfa', data['file']))
            subprocess.call(('vim', data['comments_file']))
        elif j == 2 and previous:
            subprocess.call(('xdg-open', previous))
        else:
            break


def grade_loop(handins):
    while True:
        for i, (group, data) in enumerate(handins):
            print_handin_info(i, group, data)
        try:
            i = int(input()) - 1
            if 0 <= i < len(handins):
                handin_loop(i, handins[i])
        except KeyboardInterrupt:
            break


def print_comments(handins):
    for group, data in handins:
        print('%s' % (group,))
        try:
            with open(data['comments_file']) as fp:
                print(fp.read())
        except FileNotFoundError:
            print("no comments\n")


def main():
    args = sys.argv[1:]
    if len(args) == 0:
        zipname, attempt = guess_params()
    elif len(args) == 1:
        zipname = args[0]
        attempt = 1
    else:
        zipname, attempt = args

    reject_invalid = True

    handins = {}

    with zipfile.ZipFile(zipname, 'r') as zf:
        for zinfo in zf.infolist():
            filename = zinfo.filename
            o = re.fullmatch(FILENAME, filename)

            if not o:
                print("Could not match filename: %r" % (filename,))
                continue

            d = o.groupdict()

            d['handin'] = re.sub('^Aflevering ', '', d['handin'])
            d['handin'] += '_%d' % attempt
            d['group'] = re.sub('^Gruppe ([A-Z]*\d+) - ', r'\1-',
                                d['group']).replace(' ', '0')
            # d['suffix'] = re.sub('[^0-9A-Za-z_.-]+', '_', d['suffix'])
            d['extension'] = os.path.splitext(d['suffix'])[1]

            output_folder = d['handin']
            if not os.path.exists(output_folder):
                os.mkdir(output_folder)

            output_base = os.path.join(output_folder, d['group'])

            handin = handins.setdefault(d['group'], {})
            handin.setdefault('comments_file', output_base + '_comments.txt')

            if o.group('suffix') == '.txt':
                data = zf.read(zinfo)
                # print(data)
                # o2 = re.fullmatch(METADATA, data)
                # if not o2:
                #     print("Could not match metadata: %r" % data)
                # else:
                #     files_field = o2.group('files')
                #     if files_field == NO_FILES:
                #         print("No files")
                #     else:
                #         o3 = re.fullmatch(FILES_FIELD, files_field)
                #         original =
                #         print(o3)

                #     for k, v in o2.groupdict().items():
                #         if v:
                #             print("%s:\n%s" % (k, v.decode()))
                #     print('')
            else:
                if reject_invalid and d['extension'] not in EXTENSIONS:
                    print("Rejecting %r" % d['suffix'])
                else:
                    handin['file'] = output_base + '_handin' + d['extension']
                    try:
                        with open(handin['file'], 'xb') as fp:
                            fp.write(zf.read(zinfo))
                            print("extracting %r (%d bytes)"
                                  % (handin['file'], fp.tell()))
                    except FileExistsError:
                        print("skipping %r" % handin['file'])

    handins = sorted(handins.items(), key=lambda x: x[0])
    grade_loop(handins)
    print_comments(handins)


if __name__ == "__main__":
    main()
