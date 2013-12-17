import os
import urllib
import cgi
import datetime
import logging
import sys
from pytz.gae import pytz

from google.appengine.api import users
from google.appengine.ext import ndb


import jinja2
import webapp2

from twilio.rest import TwilioRestClient

# import config file
# this config file defines three functions that just return simple values
#
# def get_twilio_SID()
# returns your twilio SID as a string
#
# def get_twilio_auth_token()
# returns your twilio auth token as a string
#
# get_twilio_calling_number()
# returns you twilio calling numbers as a string, in the form "1XXXYYYYYYY", where XXX is the area code
import appconfig

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

class Post(ndb.Model):
    """Models an individual Guestbook entry with author, content, and date."""
    content = ndb.StringProperty(indexed=False)
    date = ndb.DateTimeProperty(auto_now_add=True)
    type = ndb.StringProperty(choices=["tip", "story", "rant"])
    isSubmitted = ndb.BooleanProperty(default=False)

    #@classmethod
    #def query_it(cls, ancestor_key):
    #    return cls.query(ancestor=ancestor_key).order(-cls.date)

class TextAddress(ndb.Model):
    number = ndb.StringProperty(indexed=True)
    faculty = ndb.StringProperty(indexed=False)
    date = ndb.DateTimeProperty(auto_now_add=True)

class TextMessage(ndb.Model):
    content = ndb.StringProperty(indexed=False)
    date = ndb.DateTimeProperty(auto_now_add=True)
    post_date = ndb.DateProperty(auto_now_add=False)
    successfully_sent = ndb.BooleanProperty(default=False)


class MainHandler(webapp2.RequestHandler):
    def get(self):
        ancestor_key = ndb.Key("Posts", "*all*")
        posts = Post.query(ancestor=ancestor_key).fetch()

        template_values = {
            'posts': posts
        }

        template = JINJA_ENVIRONMENT.get_template('index.html')
        self.response.write(template.render(template_values))

class AjaxHandler(webapp2.RequestHandler):
    def get(self):
        if self.request.get('type') == 'submitpost':
            post = Post(parent=ndb.Key("Posts", "*all*"))
            post.content = cgi.escape(self.request.get('content'))
            post_type = cgi.escape(self.request.get('postType'))
            if post_type == "tip" or post_type == "story" or post_type == "rant":
                post.type = post_type
                post.put()
                params = urllib.urlencode({'message': 'Success! Your post was successfully submitted completely anonymously, and will be shortly posted to our Facebook page "UBC Event Cram!". Why not signup for the Midnight Exam Texts?'})
                self.redirect("/?%s" % params)
            else:
                params = urllib.urlencode({'message': 'Oops! We encountered a small problem. Please try again later.'})
                self.redirect("/?%s" % params)
        elif self.request.get('type') == 'textsignup':
            textaddress = TextAddress(parent=ndb.Key("TextAddresses", "*all*"))
            number = cgi.escape(self.request.get('number'))
            number = number.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "").replace(".", "")
            if number.isdigit() and len(number) == 10:
                if str(number)[:3] == "604" or str(number)[:3] == "250" or str(number)[:3] == "778":
                    textaddress.number = "+1" + number
                    textaddress.put()
                    params = urllib.urlencode({'message': 'Success! You are now signed up to receive our Exam Cram Texts! If you ever wish to unsubscribe, please just visit this page and delete your number.'})
                    self.redirect("/?%s" % params)
                else:
                    params = urllib.urlencode({'message': 'It appears that your phone number is from outside of BC. Unfortunately, the Midnight Texts only work with BC numbers. Sorry about this :('})
                    self.redirect("/?%s" % params)
            else:
                params = urllib.urlencode({'message': 'You did not enter a valid phone number. Please make sure that you include a valid BC area code.'})
                self.redirect("/?%s" % params)
        elif self.request.get('type') == 'addmessage':
            message = TextMessage(parent=ndb.Key("TextMessages", "*all*"))
            message.content = cgi.escape(self.request.get('content'))
            message.post_date = datetime.date(int(cgi.escape(self.request.get('post_year'))),int(cgi.escape(self.request.get('post_month'))),int(cgi.escape(self.request.get('post_day'))))
            message.put()
            self.redirect("/admin")
        elif self.request.get('type') == 'delete':
            key = ndb.Key(urlsafe=cgi.escape(self.request.get('id')))
            entity = key.get()
            entity.key.delete()
            self.redirect("/admin")
        elif self.request.get('type') == 'unsubscribe':
            ancestor_key = ndb.Key("TextAddresses", "*all*")
            numbers = TextAddress.query(ancestor=ancestor_key).fetch()
            unsubscribe_number = "+1" + cgi.escape(self.request.get('number'))
            logging.info("Unsubscribe Number: " + unsubscribe_number)
            for number in numbers:
                if number.number == unsubscribe_number:
                    logging.info("Found a key to remove!")
                    number.key.delete()
            logging.info("Done unsubscrubing!")

        else:
            self.response.write("You shouldn't be seeing this!")
    def post(self):
        self.response.write("You shouldn't be seeing this!")

class AdminHandler(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            logging.info("User with email \"" + user.email() + "\" tried to login")
            if (user.email() == "emailkurtis@gmail.com") or (user.email() == "aatighpour@gmail.com") or (user.email() == "ausacademic@gmail.com") or (user.email() == "melissalachica@gmail.com"):
                ancestor_key = ndb.Key("Posts", "*all*")
                posts = Post.query(ancestor=ancestor_key).fetch()

                ancestor_key = ndb.Key("TextAddresses", "*all*")
                numbers = TextAddress.query(ancestor=ancestor_key).fetch()

                ancestor_key = ndb.Key("TextMessages", "*all*")
                messages = TextMessage.query(ancestor=ancestor_key).fetch()

                template_values = {
                    'posts': posts,
                    'numbers': numbers,
                    'messages': messages,
                    }

                template = JINJA_ENVIRONMENT.get_template('admin.html')
                self.response.write(template.render(template_values))
            else:
                greeting = ('Unfortunately, your account does not currently have admin access. Please contact kurtis at emailkurtis@gmail.com to request admin access. <a href="%s">Sign Out</a>' % users.create_logout_url('/'))
                self.response.out.write('<html><body>%s</body></html>' % greeting)
        else:
            greeting = ('<a href="%s">Sign in</a>.' % users.create_login_url('/admin'))
            self.response.out.write('<html><body>%s</body></html>' % greeting)

class TestTextHandler(webapp2.RequestHandler):
    def get(self):
        # replace with your credentials from: https://www.twilio.com/user/account
        account_sid = appconfig.get_twilio_SID()
        auth_token = appconfig.get_twilio_auth_token()
        calling_number = appconfig.get_twilio_calling_number()
        client = TwilioRestClient(account_sid, auth_token)

        rv = client.messages.create(to="+16049968785", from_=calling_number, body="FACT: Seventeen hours of sustained wakefulness leads to a decrease in performance equivalent to a blood alcohol-level of 0.05%. Unless you've always wanted to try writing an exam drunk, you should get some sleep.")
        self.response.write(str(rv))


class TextHandler(webapp2.RequestHandler):
    def get(self):
        # replace with your credentials from: https://www.twilio.com/user/account
        account_sid = appconfig.get_twilio_SID()
        auth_token = appconfig.get_twilio_auth_token()
        calling_number = appconfig.get_twilio_calling_number()
        client = TwilioRestClient(account_sid, auth_token)

        # Set timezone to Pacific
        tz = pytz.timezone('America/Vancouver')

        ancestor_key = ndb.Key("TextMessages", "*all*")
        messages = TextMessage.query(TextMessage.post_date == datetime.datetime.now(tz).date(), ancestor=ancestor_key).fetch()
        ancestor_key = ndb.Key("TextAddresses", "*all*")
        numbers = TextAddress.query(ancestor=ancestor_key).fetch()
        numbers_messaged = []
        if len(messages) < 3 and len(numbers) < 200:
            for message in messages:
                for number in numbers:
                    if number.number not in numbers_messaged:
                        try:
                            rv = client.messages.create(to=number.number, from_=calling_number, body=message.content)
                            self.response.write(str(rv))
                            numbers_messaged.append(number.number)
                        except:
                            logging.info("Failed to send to number " + number.number + ". Probably because of blacklist; safe to ignore.")

app = webapp2.WSGIApplication([
                                  ('/', MainHandler),
                                  ('/ajax',AjaxHandler),
                                  ('/admin', AdminHandler),
                                  ('/sendtexts', TextHandler),
                                  ('/testtexts', TestTextHandler)
                              ], debug=True)
