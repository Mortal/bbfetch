import re
import logging
import argparse
import html5lib
from xml.etree.ElementTree import ElementTree
from six import BytesIO

import html2text

import blackboard
from blackboard import BlackBoardSession
from visit_stats import get_visit_stats


NS = {'h': 'http://www.w3.org/1999/xhtml'}


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


def get_forum_posts(session):
    for forum_id, name in get_forum_ids(session):
        print(name)
        nonce, tids = get_thread_ids(session, forum_id)
        threads = get_thread_posts(
            session, forum_id, nonce, tids)
        for post in threads:
            yield post


def get_thread_posts(session, forum_id, nonce, threads):
    ids = [i for i, name in threads]

    url = (
        'https://bb.au.dk/webapps/discussionboard/do/message' +
        '?conf_id=%s&forum_id=%s&action=collect' % forum_id +
        '&blackboard.platform.security.NonceUtil.nonce=%s' % nonce +
        ''.join('&formCBs=%s' % t for t in ids) +
        '&requestType=thread&course_id=%s&' % session.course_id)
    r = session.get(url)
    document = html5lib.parse(r.content, encoding=r.encoding)
    return parse_thread_posts(document)


def parse_thread_posts(document):
    post_elements = document.findall('.//h:div[@class="dbThread"]', NS)
    h_dt = '{%s}dt' % NS['h']
    h_dd = '{%s}dd' % NS['h']
    for post in post_elements:
        checkbox = post.find(
            './/h:input[@type="checkbox"][@name="formCBs"]', NS)
        message_id = checkbox.get('value')
        message_title = checkbox.get('title')

        data = []
        for dl in post.findall('.//h:dl', NS):
            key = None
            for c in dl:
                if key == 'Author:':
                    span = c.find('./h:span', NS)
                    if span:
                        data.append(('role', span.get('class')))
                        span = span.find(
                            './h:span[@class="profileCardAvatarThumb"]', NS)
                        direct_text = (
                            [span.text or ''] + [cc.tail or '' for cc in span])
                        raw_text = ''.join(direct_text)
                    else:
                        data.append(('role', 'anonymous'))
                        raw_text = ''.join(c.itertext())
                else:
                    raw_text = ''.join(c.itertext())

                text = ' '.join(raw_text.split())

                if c.tag == h_dt:
                    key = text
                elif c.tag == h_dd:
                    data.append((key, text))
        body = post.find('.//h:div[@class="vtbegenerated"]', NS)
        if body:
            with BytesIO() as buf:
                # We cannot use default_namespace,
                # since it incorrectly errors on unnamespaced attributes
                # See: https://bugs.python.org/issue17088
                ElementTree(body).write(
                    buf, encoding='utf8', xml_declaration=False,
                    method='xml')
                body = buf.getvalue().decode('utf8')
                # Workaround to make it prettier
                body = body.replace(
                    ' xmlns:html="http://www.w3.org/1999/xhtml"', '')
                body = body.replace('<html:', '<')
                body = body.replace('</html:', '</')
                body = html2text.html2text(body)
        else:
            body = ''
        yield dict(
            message_id=message_id,
            message_title=message_title,
            metadata=data,
            body=body)


def get_forum_ids(session):
    url = (
        'https://bb.au.dk/webapps/discussionboard/do/conference' +
        '?action=list_forums&course_id=%s' % session.course_id +
        '&nav=discussion_board&showAll=true')
    r = session.get(url)
    # with open('tmp.html', 'wb') as fp:
    #     fp.write(r.content)
    document = html5lib.parse(r.content, encoding=r.encoding)
    return parse_forum_ids(document)


def parse_forum_ids(document):
    table = document.find('.//h:table[@id="listContainer_datatable"]', NS)
    links = table.findall(
        './h:tbody/h:tr/h:th/h:span[@class="dbheading"]/h:a', NS)
    forums = []
    for l in links:
        mo = re.search(
            r'conf_id=([^&]+)&forum_id=([^&]+)', l.get('href'))
        text = ' '.join(''.join(l.itertext()).split())
        if mo:
            forums.append(((mo.group(1), mo.group(2)), text))
    return forums


def get_thread_ids(session, forum_id):
    url = (
        'https://bb.au.dk/webapps/discussionboard/do/forum' +
        '?action=list_threads&nav=discussion_board' +
        '&course_id=%s' % session.course_id +
        '&conf_id=%s&forum_id=%s' % forum_id +
        '&showAll=true'
    )
    r = session.get(url)
    document = html5lib.parse(r.content, encoding=r.encoding)
    return parse_thread_ids(document)


def parse_thread_ids(document):
    form = document.find('.//h:form[@name="forumForm"]', NS)

    # Seemingly used by BB to cache requests/prevent spam
    nonce_field = form.find(
        './/h:input[@name="blackboard.platform.security.NonceUtil.nonce"]', NS)
    nonce = nonce_field.get('value')

    thread_fields = form.findall('.//h:input[@name="formCBs"]', NS)
    threads = []
    for f in thread_fields:
        threads.append((f.get('value'), f.get('title')))
    return nonce, threads


if __name__ == "__main__":
    main()
