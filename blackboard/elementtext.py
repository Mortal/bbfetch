from xml.etree.ElementTree import ElementTree
from six import BytesIO
import html2text


def element_hidden(element):
    if 'hideoff' in element.get('class', ''):
        return True
    if 'display: none' in element.get('style', ''):
        return True


def element_text_content(element, element_hidden=element_hidden):
    def visit(e):
        if not element_hidden(e):
            yield e.text or ''
            for c in e:
                yield ''.join(visit(c))
            yield e.tail or ''

    return ' '.join(''.join(visit(element)).split())


def element_to_html(element):
    with BytesIO() as buf:
        # We cannot use default_namespace,
        # since it incorrectly errors on unnamespaced attributes
        # See: https://bugs.python.org/issue17088
        ElementTree(element).write(
            buf, encoding='utf8', xml_declaration=False,
            method='xml')
        body = buf.getvalue().decode('utf8')

    # Workaround to make it prettier
    body = body.replace(
        ' xmlns:html="http://www.w3.org/1999/xhtml"', '')
    body = body.replace('<html:', '<')
    body = body.replace('</html:', '</')
    return body


def element_to_markdown(element):
    return html2text.html2text(element_to_html(element))


def form_field_value(element):
    NS = {'h': 'http://www.w3.org/1999/xhtml'}
    tag_input = '{%s}input' % NS['h']
    tag_textarea = '{%s}textarea' % NS['h']
    if element.tag == tag_input:
        return element.get('value') or ''
    elif element.tag == tag_textarea:
        return element_text_content(element)
    else:
        raise ValueError("Unknown tag %s" % element.tag)
