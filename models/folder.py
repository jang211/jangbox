from google.appengine.ext import ndb

class Folder(ndb.Model):
	user_id = ndb.StringProperty()
	path = ndb.StringProperty()
