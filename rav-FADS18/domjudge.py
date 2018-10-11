import os
import json
import time
import datetime
import requests


DOMAIN = 'https://domjudge.cs.au.dk'
CACHE = 'domjudge-cache'


def timed_get(session, url):
    print('GET %s' % url, flush=True, end='')
    try:
        t1 = time.time()
        response = session.get(url)
        t2 = time.time()
        print(' [%.2f s]' % (t2 - t1), end='')
        return response
    finally:
        print('', flush=True)


def api_contests(session):
    response = timed_get(session, DOMAIN + '/api/contests')
    return response.json()


def api_scoreboard(session, contest_id):
    response = timed_get(session, DOMAIN + '/api/scoreboard?cid=%s' % contest_id)
    return response.json()


def api_teams(session):
    response = timed_get(session, DOMAIN + '/api/teams')
    return response.json()


def api_problems(session, contest_id):
    response = timed_get(session, DOMAIN + '/api/problems?cid=%s' % contest_id)
    return response.json()


def get_unique_contest(session):
    path = os.path.join(CACHE, 'unique_contest.json')
    try:
        with open(path) as fp:
            contest = json.load(fp)
    except FileNotFoundError:
        contests = api_contests(session)
        if not isinstance(contests, list):
            raise Exception("contests is not a list: %r" % (contests,))
        if len(contests) == 0:
            raise Exception("No contests")
        if len(contests) > 1:
            raise Exception("Multiple active contests")
        contest, = contests
        try:
            fp = open(path, 'w')
        except FileNotFoundError:
            os.makedirs(CACHE)
            fp = open(path, 'w')
        with fp:
            json.dump(contest, fp, indent=2)
    return contest


def fetch_problems(session):
    contest = get_unique_contest(session)
    problems = api_problems(session, contest['id'])
    return {problem['id']: problem['label'] for problem in problems}


def fetch_team_names(session):
    teams = api_teams(session)
    return {team['id']: team['name'] for team in teams}


class CachedDict:
    class DictView:
        def __init__(self, cached_dict, session):
            self._source = cached_dict
            self._session = session

        def __getitem__(self, k):
            return self._source(self._session, k)

    def __init__(self, fetch_fn, filename):
        self._fetch_fn = fetch_fn
        self._path = os.path.join(CACHE, filename)
        self._cache = None
        self._fetched = None
        self._negative = set()

    def __call__(self, session, k):
        if k in self._negative:
            raise KeyError(k)
        if self._cache is None:
            self.read_or_fetch(session)
        try:
            return self._cache[k]
        except KeyError:
            print('%s: %s not found in cache; refetching' %
                  (os.path.basename(self._path), k))
            self.refetch(session)
            try:
                return self._cache[k]
            except KeyError:
                self._negative.add(k)
                raise

    def refetch(self, session, force=False):
        if self._fetched and not force:
            return
        try:
            self._cache = self._fetch_fn(session)
        except Exception:
            if session is None:
                msg = 'Refetch requested, but no session supplied'
                raise Exception(msg) from None
            raise
        self._fetched = True
        self._write_cache()

    def _write_cache(self):
        try:
            fp = open(self._path, 'w')
        except FileNotFoundError:
            os.makedirs(CACHE)
            fp = open(self._path, 'w')
        with fp:
            json.dump(self._cache, fp, indent=2)

    def read_or_fetch(self, session):
        try:
            with open(self._path) as fp:
                self._cache = {int(k): v for k, v in json.load(fp).items()}
        except FileNotFoundError:
            self.refetch(session)

    def dict_view(self, session):
        self.read_or_fetch(session)
        return self.DictView(self, session)


get_team_name = CachedDict(fetch_team_names, 'teams.json')
get_team_names = get_team_name.dict_view
get_problem_label = CachedDict(fetch_problems, 'problems.json')
get_problems = get_problem_label.dict_view


def get_scoreboard(session):
    contest = get_unique_contest(session)
    start_time = datetime.datetime.strptime(contest['start_time'].replace('.000', ''), '%Y-%m-%dT%H:%M:%S%z')
    scoreboard = api_scoreboard(session, contest['id'])
    team_names = get_team_names(session)
    result = {}
    for team in scoreboard:
        team_name = team_names[team['team_id']]
        problems = {}
        for problem in team['problems']:
            if problem['solved']:
                # p['time'] does not include penalty time
                elapsed = datetime.timedelta(minutes=problem['time'])
                problems[problem['label']] = (True, start_time + elapsed)
            elif problem['num_judged']:
                problems[problem['label']] = (False, None)
        result[team_name] = problems
    return result


if __name__ == '__main__':
    with requests.Session() as session:
        s = get_scoreboard(session)
    with open('scoreboard.json', 'w') as fp:
        json.dump(s, fp, indent=2, default=str)
