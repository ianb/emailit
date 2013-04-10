import os
import urllib
import re
from webob import Request, Response
from webob import exc
from paste.exceptions.errormiddleware import make_error_middleware
from tempita import HTMLTemplate, html_quote
from tempita import html as html_literal
from formencode.validators import Email
from formencode.api import Invalid
from lxml import html
try:
    # Python 2.5:
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
except ImportError:
    # Python 2.4:
    from email.MIMEMultipart import MIMEMultipart
    from email.MIMEText import MIMEText
import smtplib

here = os.path.dirname(__file__)

## FIXME: these don't auto-reload or restart the server on edit:
form_html = HTMLTemplate.from_filename(os.path.join(here, 'form.html'))
result_html = HTMLTemplate.from_filename(os.path.join(here, 'result.html'))

class EmailIt(object):

    ## FIXME: should have some kind of host restriction, like ScriptTranscluder
    def __init__(self, smtp_server='localhost', smtp_username=None, smtp_password=None, smtp_use_tls=False):
        self.smtp_server = smtp_server
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.smtp_use_tls = smtp_use_tls

    def __call__(self, environ, start_response):
        req = Request(environ)
        if req.method == 'GET':
            meth = self.form
        else:
            meth = self.process
        try:
            res = meth(req)
        except exc.HTTPException, e:
            return e(environ, start_response)
        return res(environ, start_response)

    def form(self, req, error=None):
        if 'url' not in req.params:
            raise exc.HTTPBadRequest('You did not include a URL parameter').exception
        url = req.params['url']
        page = self.get_url(url)
        html = form_html.substitute(req=req, page=page, error=error, nl2br=nl2br)
        return Response(content_type='text/html', charset='utf8', body=html)

    def process(self, req):
        try:
            url = req.params['url']
            email_to = req.params['email_to']
            name_from = req.params['name_from']
            email_from = req.params['email_from']
            message = req.params['message']
            subject = req.params.get('subject')
        except KeyError, e:
            raise exc.HTTPBadRequest('A parameter was missing: %s' % e).exception
        errors = []
        if not url:
            errors.append('No URL given')
        if not email_from:
            errors.append('You must give a From email address')
        if not name_from:
            errors.append('You must give a From name')
        try:
            email_to = self.split_email_to(email_to)
        except ValueError, e:
            errors.append(str(e))
        if errors:
            return self.form(req, error='\n'.join(errors))
        result = self.send_email(url=url, email_to=email_to, name_from=name_from, email_from=email_from,
                                 subject=subject, message=message)
        html = result_html.substitute(req=req, result=result, email_to=email_to)
        return Response(content_type='text/html', charset='utf8', body=html)

    def split_email_to(self, email_to):
        lines = email_to.splitlines()
        errors = []
        validator = Email()
        emails = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                emails.append(validator.to_python(line))
            except Invalid, e:
                errors.append(str(e))
        if errors:
            raise ValueError('\n'.join(errors))
        if not emails:
            raise ValueError('You must enter an email')
        return emails

    def get_url(self, url):
        try:
            f = urllib.urlopen(url)
            content = f.read()
            f.close()
            return Page(url, content)
        except Exception, e:
            raise exc.HTTPServerError(
                'Could not fetch the page %s: %s' % (url, e))

    def send_email(self, url, email_to, name_from, email_from, subject, message):
        page = self.get_url(url)
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = '%s <%s>' % (name_from, email_from)
        ## FIXME: charset?
        text_message = '%s sent you the URL: %s' % (name_from, url)
        if message:
            text_message += '\n' + message
        text = MIMEText(text_message, _subtype='plain')
        msg.attach(text)
        page = MIMEText(page.html, _subtype='html')
        msg.attach(page)
        server = smtplib.SMTP(self.smtp_server)
        if self.smtp_use_tls:
            server.ehlo()
            server.starttls()
            server.ehlo()
        if self.smtp_username and self.smtp_password:
            server.login(self.smtp_username, self.smtp_password)
        try:
            for email in email_to:
                msg['To'] = email
                s = server.sendmail(email_from, email, msg.as_string())
        finally:
            server.close()

def nl2br(s):
    if not isinstance(s, html_literal):
        s = html_quote(s)
    s = s.replace('\n', '<br>\n')
    return html_literal(s)

class Page(object):

    def __init__(self, url, raw_html):
        ## FIXME: maybe I should just use lxml.html.parse(url)?
        self.url = url
        self.raw_html = raw_html
        ## FIXME: add url here:
        self.doc = html.fromstring(raw_html)
        titles = self.doc.xpath('//title')
        if titles:
            self.title = titles[0].text_content()
        else:
            self.title = None
        self.doc.make_links_absolute(url)
        self.html = html.tostring(self.doc)

def make_app(global_conf, smtp_server=None,
             smtp_username=None, smtp_password=None,
             smtp_password_filename=None,
             smtp_use_tls=None):
    from paste.deploy.converters import asbool
    if smtp_server is None:
        smtp_server = global_conf.get('smtp_server', 'localhost')
    if smtp_username is None:
        smtp_username = global_conf.get('smtp_username')
    if smtp_password is None:
        smtp_password = global_conf.get('smtp_password')
    if smtp_use_tls is None:
        smtp_use_tls = global_conf.get('smtp_use_tls')
    if smtp_password_filename is None:
        smtp_password_filename = global_conf.get('smtp_password_filename')
    if smtp_password_filename:
        f = open(os.path.expanduser(smtp_password_filename), 'rb')
        smtp_password = f.read().strip()
        f.close()
    smtp_use_tls = asbool(smtp_use_tls)
    app = EmailIt(smtp_server=smtp_server,
                  smtp_username=smtp_username,
                  smtp_password=smtp_password,
                  smtp_use_tls=smtp_use_tls)
    app = make_error_middleware(app, global_conf)
    return app

