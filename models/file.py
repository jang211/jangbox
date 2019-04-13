from google.appengine.ext import ndb

class File(ndb.Model):
    name = ndb.StringProperty()
    blob_key = ndb.BlobKeyProperty()
