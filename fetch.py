import logging
import argparse

import blackboard
from blackboard import BlackBoardSession
from visit_stats import get_visit_stats
from forum import get_forum_posts


def configure_logging(quiet):
    """Configure the Python logging module."""
    handlers = []
    handlers.append(logging.FileHandler('fetch.log', 'a'))
    if not quiet:
        handlers.append(logging.StreamHandler(None))
    fmt = '[%(asctime)s %(levelname)s] %(message)s'
    datefmt = None
    formatter = logging.Formatter(fmt, datefmt, '%')
    for handler in handlers:
        handler.setFormatter(formatter)
        blackboard.logger.addHandler(handler)
    blackboard.logger.setLevel(logging.DEBUG)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--quiet', action='store_true')
    parser.add_argument('--username', '-u')
    parser.add_argument('--course', default='_43290_1')
    parser.add_argument('--cookiejar', default='cookies.txt')
    args = parser.parse_args()
    configure_logging(quiet=args.quiet)

    session = BlackBoardSession(args.cookiejar, args.username, args.course)

    table = get_visit_stats(session)
    with open('visit_stats.txt', 'a') as fp:
        for name, time in table:
            fp.write('%s %s\n' % (time, name))

    with open('forum_posts.txt', 'a') as fp:
        for post in get_forum_posts(session):
            for k, v in post['metadata']:
                fp.write("%s %s\n" % (k, v))
            fp.write('\n')
            fp.write(post['body'] + '\n')
            fp.write('='*79 + '\n')

    session.save_cookies()


if __name__ == "__main__":
    main()
