import json
import datetime
import requests


DOMAIN = 'https://domjudge.cs.au.dk'


def api_contests(session):
    response = session.get(DOMAIN + '/api/contests')
    return response.json()


def api_scoreboard(session, contest_id):
    response = session.get(DOMAIN + '/api/scoreboard?cid=%s' % contest_id)
    return response.json()


def api_teams(session):
    response = session.get(DOMAIN + '/api/teams')
    return response.json()


def get_team_names(session):
    teams = api_teams(session)
    return {team['id']: team['name'] for team in teams}


def get_scoreboard(session):
    contests = api_contests(session)
    if len(contests) == 0:
        raise Exception("No contests")
    if len(contests) > 1:
        raise Exception("Multiple active contests")
    contest, = contests.values()
    start_time = datetime.datetime.fromtimestamp(contest['start'])
    scoreboard = api_scoreboard(session, contest['id'])
    team_names = get_team_names(session)
    result = {}
    for team in scoreboard:
        team_name = team_names[team['team']]
        solved_problems = {}
        for problem in team['problems']:
            if problem['solved']:
                # p['time'] does not include penalty time
                elapsed = datetime.timedelta(minutes=problem['time'])
                solved_problems[problem['label']] = start_time + elapsed
        result[team_name] = solved_problems
    return result


if __name__ == '__main__':
    with requests.Session() as session:
        s = get_scoreboard(session)
    with open('scoreboard.json', 'w') as fp:
        json.dump(s, fp, indent=2, default=str)
