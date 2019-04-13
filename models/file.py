from google.appengine.ext import ndb

class File(ndb.Model):
    name = ndb.StringProperty()
    path = ndb.StringProperty()
    size = ndb.StringProperty()
    cdate = ndb.StringProperty()
    blob_key = ndb.BlobKeyProperty()
