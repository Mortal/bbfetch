import os
import re
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--all', action='store_true')
    parser.add_argument('filename')
    parser.add_argument('attempt', type=int, default=1)
    args = parser.parse_args()

    handins = {}

    with zipfile.ZipFile(args.filename, 'r') as zf:
        for zinfo in zf.infolist():
            filename = zinfo.filename
            o = re.fullmatch(FILENAME, filename)

            if not o:
                print("Could not match filename: %r" % (filename,))
                continue

            d = o.groupdict()

            d['handin'] = re.sub('^Aflevering ', '', d['handin'])
            d['handin'] += '_%d' % args.attempt
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
                if not args.all and d['extension'] not in EXTENSIONS:
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
    while True:
        for i, (group, data) in enumerate(handins):
            print("%d. %s" % (i + 1, group))
        i = int(input()) - 1
        if 0 <= i < len(handins):
            group, data = handins[i]
            subprocess.call(('pdfa', data['file']))
            subprocess.call(('vim', data['comments_file']))


if __name__ == "__main__":
    main()
