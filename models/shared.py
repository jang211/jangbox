from google.appengine.ext import ndb

class Shared(ndb.Model):
	name = ndb.StringProperty()
	path = ndb.StringProperty()
	blob_key = ndb.BlobKeyProperty()
	sh_by = ndb.StringProperty()
	sh_to = ndb.StringProperty()
	size = ndb.StringProperty()
	time = ndb.StringProperty()
