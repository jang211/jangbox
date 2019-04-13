from google.appengine.ext import ndb

class File(ndb.Model):
    user = ndb.StringProperty()
    blob_key = ndb.BlobKeyProperty()
