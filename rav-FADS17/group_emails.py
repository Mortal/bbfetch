import argparse
import itertools
from grading import Grading


parser = argparse.ArgumentParser()
parser.add_argument('search', nargs='*')


def grouping(xs, key):
    return itertools.groupby(sorted(xs, key=key), key=key)


def search_group_emails(query=None):
    if isinstance(query, str):
        query = (query,)
    grading = Grading.init()
    key = grading.get_student_group_display
    for group, students in grouping(grading.gradebook.students.values(), key=key):
        if query and all(s.lower() not in group.lower() for s in query):
            continue
        yield group, [(student.name, '%s@post.au.dk' % student.student_number)
                      for student in students]


def main():
    args = parser.parse_args()
    for group, students in search_group_emails(args.search):
        print(group, ' '.join('"%s" <%s>,' % (name, address)
                              for name, address in students))


if __name__ == '__main__':
    main()
