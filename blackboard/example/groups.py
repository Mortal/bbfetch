import blackboard
from blackboard.backend import fetch_groups


def print_groups(session):
    users = fetch_groups(session)
    for user in users.values():
        print("%s %s (%s, %s) is in %s" %
              (user['first_name'], user['last_name'],
               user['username'], user['role'], user['groups']))


if __name__ == "__main__":
    blackboard.wrapper(print_groups)
