import blackboard
# from groups import get_groups
from gradebook import Gradebook


def get_assignments(session, gb):
    # groups = get_groups(session)

    assignments = {}
    for assignment in gb.assignments.keys():
        by_attempt_id = {}
        user_groups = {}
        for user_id, s in gb.students.items():
            try:
                assignment_data = s['assignments'][assignment]
            except KeyError:
                continue
            for i, a in enumerate(assignment_data['attempts']):
                first = i == 0
                last = i == (len(assignment_data['attempts']) - 1)
                data = by_attempt_id.setdefault(
                    a['groupAttemptId'],
                    dict(users=set(), first=first, last=last, **a))
                data['users'].add(user_id)
                user_groups.setdefault(user_id, []).append(
                    data['users'])

        for user_id, groups in user_groups.items():
            groups = frozenset(map(frozenset, groups))
            if len(groups) > 1:
                print("%s has handed in assignment " % user_id +
                      "%s in multiple different groups: " % assignment +
                      "%s" % (groups,))

        assignments[assignment] = by_attempt_id
    return assignments


def print_assignments(session):
    def group_key(group):
        k = ()
        for v in group['groupName'].split():
            try:
                k += (0, int(v))
            except ValueError:
                k += (1, v)
        return k + (group['last'],)

    gb = Gradebook(session, 'gradebook.json')
    assignments = get_assignments(session, gb)
    for assignment, groups in sorted(assignments.items(), key=lambda x: x[0]):
        print('='*79)
        print("Assignment %s" % assignment)
        groups = sorted(groups.values(), key=group_key)
        for attempt in groups:
            if not attempt['last']:
                continue
            members = sorted(
                '%s %s' % (s['first_name'], s['last_name'])
                for s in (gb.students[i] for i in attempt['users'])
            )
            if attempt['groupStatus'] != 'ng':
                score = attempt['groupScore']
                if score == 1:
                    tag = '✔'
                elif score == 0:
                    tag = '✘'
                else:
                    tag = '%g' % score
            elif attempt['first']:
                tag = ' '
            else:
                tag = '.'
            print("[%s] %s (%s)%s" %
                  (tag, attempt['groupName'], ', '.join(members),
                   '' if attempt['last'] else ' Superseded by later attempt'))


if __name__ == "__main__":
    blackboard.wrapper(print_assignments)
