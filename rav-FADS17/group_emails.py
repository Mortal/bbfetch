import argparse
import itertools
from grading import Grading


parser = argparse.ArgumentParser()
parser.add_argument('search', nargs='*')


def grouping(xs, key):
    return itertools.groupby(sorted(xs, key=key), key=key)


def main():
    args = parser.parse_args()
    grading = Grading.init()
    key = grading.get_student_group_display
    for group, students in grouping(grading.gradebook.students.values(), key=key):
        if args.search and all(s.lower() not in group.lower() for s in args.search):
            continue
        print(group, ' '.join('"%s" <%s@post.au.dk>,' % (student.name, student.student_number) for student in students))


if __name__ == '__main__':
    main()
