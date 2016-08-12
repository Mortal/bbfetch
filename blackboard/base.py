import json
import time
import logging
import argparse
import datetime
import collections


logger = logging.getLogger('blackboard')


class ParserError(Exception):
    def __init__(self, msg, response, *extra):
        self.msg = msg
        self.response = response
        self.extra = extra

    def __str__(self):
        return self.msg

    def save(self):
        n = datetime.datetime.now()
        filename = n.strftime('%Y-%m-%d_%H%M_parseerror.txt')
        with open(filename, 'w') as fp:
            for r in self.response.history + [self.response]:
                fp.write('%s %s\n' % (r.status_code, r.url))
            fp.write("ParserError: %s\n\n" % self.msg)
            fp.write("Reported encoding: %s\n" % self.response.encoding)
            for s in self.extra:
                fp.write(s + '\n')
        with open(filename, 'ab') as fp:
            fp.write(self.response.content)
        print("ParserError logged to %s" % filename)


class BadAuth(Exception):
    pass


def slowlog(threshold=2):
    t1 = time.time()

    def report(msg, *args, **kwargs):
        t2 = time.time()
        t = t2 - t1
        if t > threshold:
            if kwargs:
                kwargs['t'] = t
                logger.debug(msg, kwargs)
            else:
                args += (t,)
                logger.debug(msg, *args)

    return report


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
        logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)


def wrapper(fun):
    parser = argparse.ArgumentParser()
    parser.add_argument('--quiet', action='store_true')
    parser.add_argument('--username', '-u')
    parser.add_argument('--course')
    parser.add_argument('--cookiejar', default='cookies.txt')
    args = parser.parse_args()
    configure_logging(quiet=args.quiet)

    from blackboard.session import BlackboardSession

    session = BlackboardSession(args.cookiejar, args.username, args.course)
    try:
        fun(session)
    except ParserError as exn:
        print(exn)
        exn.save()
    except BadAuth:
        print("Bad username or password. Forgetting password.")
        session.forget_password()
    session.save_cookies()


class Serializable:
    def refresh(self):
        raise NotImplementedError()

    def serialize(self):
        o = []
        for f in self.FIELDS:
            v = getattr(self, f)
            try:
                v = v.serialize()
            except AttributeError:
                # v does not have a serialize method
                pass
            o.append((f, v))
        return collections.OrderedDict(o)

    def warn_superfluous_key(self, key):
        logger.warning("deserialize() skipping superfluous key %r", key)

    def deserialize_default(self, key):
        raise Exception("deserialize() missing key for %r", key)

    def deserialize(self, o):
        o_k = frozenset(o.keys())
        e_k = frozenset(self.FIELDS)
        for k in o_k - e_k:
            self.warn_superfluous_key(k)
        for k in e_k - o_k:
            o[k] = self.deserialize_default(k)
        for k, v in o.items():
            try:
                getattr(self, k).deserialize(v)
            except AttributeError:
                # Either we don't have attribute k, or it doesn't have
                # a deserialize method
                setattr(self, k, v)

    def save(self, filename=None):
        if filename is None:
            filename = self.filename
        self.filename = filename
        if filename is None:
            raise ValueError("%s.save: You must specify filename" %
                             type(self).__name__)
        o = [('time', time.time())]
        try:
            course_id = self.session.course_id
        except AttributeError:
            pass
        else:
            o.append(('course', course_id))
        o.append(('payload', self.serialize()))
        with open(filename, 'w') as fp:
            json.dump(collections.OrderedDict(o), fp, indent=2)

    def autosave(self):
        filename = getattr(self, 'filename', None)
        if filename is not None:
            self.save(filename)

    def load(self, filename=None, refresh=True):
        if filename is None:
            filename = self.filename
        if filename is None:
            raise ValueError("%s.load: You must specify filename" %
                             type(self).__name__)
        if refresh:
            try:
                with open(filename) as fp:
                    o = json.load(fp)
            except FileNotFoundError:
                for k in self.FIELDS:
                    setattr(self, k, getattr(self, k, None))
                self.refresh()
                self.save(filename=filename)
                return
        else:
            with open(filename) as fp:
                o = json.load(fp)
        if 'course' in o:
            course_id = self.session.course_id
            if course_id != o['course']:
                raise ValueError("%r is about the wrong course" %
                                 filename)
        self.deserialize(o['payload'])
        self.filename = filename
