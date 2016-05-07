import re
import html5lib
from xml.etree.ElementTree import ElementTree
from six import BytesIO
import blackboard
from blackboard.datatable import fetch_datatable
from blackboard.elementtext import element_to_markdown, element_text_content


NS = {'h': 'http://www.w3.org/1999/xhtml'}


def get_forum_posts(session):
    for forum_id, name in get_forum_ids(session):
        print(name)
        nonce, tids = get_thread_ids(session, forum_id)
        threads = get_thread_posts(
            session, forum_id, nonce, tids)
        for post in threads:
            yield post


def print_forum_posts(session):
    for post in get_forum_posts(session):
        print("Title: %s" % post['message_title'])
        for k, v in post['metadata']:
            print("* %s: %s" % (k, v))
        print(post['body'])
        print(79*'=')


def get_thread_posts(session, forum_id, nonce, threads):
    ids = [i for i, name in threads]

    # action=collect_sort&collect_order=ascending&collect_type=date
    # sorts the list of posts by date, but unfortunately this disregards
    # the conf_id, forum_id, formCBs, and instead it simply sorts
    # the previously displayed list of posts.
    # Therefore we use action=collect instead, which by default
    # sorts by date in descending order.
    url = (
        'https://bb.au.dk/webapps/discussionboard/do/message' +
        '?conf_id=%s&forum_id=%s&action=collect' % forum_id +
        '&blackboard.platform.security.NonceUtil.nonce=%s' % nonce +
        ''.join('&formCBs=%s' % t for t in ids) +
        '&requestType=thread&course_id=%s' % session.course_id)
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
                text = element_text_content(c)
                if c.tag == h_dt:
                    key = text
                elif c.tag == h_dd:
                    data.append((key, text))
        body = post.find('.//h:div[@class="dbThreadBody"]', NS)
        if body is not None:
            body = element_to_markdown(body)
        else:
            body = ''
        yield dict(
            message_id=message_id,
            message_title=message_title,
            metadata=data,
            body=body)


def get_forum_ids(session):
    def extract(key, cell, d):
        if key != 'title':
            return d
        link = cell.find('./h:span/h:a', NS)
        v = element_text_content(link)
        mo = re.search(
            r'conf_id=([^&]+)&forum_id=([^&]+)', link.get('href'))
        if not mo:
            raise ValueError("Could not match %s" % link.get('href'))
        return (mo.group(1), mo.group(2)), v

    url = (
        'https://bb.au.dk/webapps/discussionboard/do/conference' +
        '?action=list_forums&course_id=%s' % session.course_id +
        '&nav=discussion_board')
    response, keys, rows = fetch_datatable(session, url, extract=extract)
    title_col = keys.index('title')
    return [row[title_col] for row in rows]


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
    blackboard.wrapper(print_forum_posts)
