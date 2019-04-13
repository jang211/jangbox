import webapp2
from webapp2_extras import sessions
import os
import time
from datetime import datetime
import cloudstorage as gcs
from google.appengine.ext.webapp import template
from google.appengine.api import app_identity
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext import ndb
from models.user import User
from models.folder import Folder
from models.file import File

my_default_retry_params = gcs.RetryParams(initial_delay = 0.2,
                                          max_delay = 5.0,
                                          backoff_factor = 2,
                                          max_retry_period = 15)
gcs.set_default_retry_params(my_default_retry_params)


def create_folder(path, userkey):
    folder = Folder()
    folder.user_id = userkey
    folder.path = path
    now = datetime.now()
    folder.cdate = now.strftime("%m/%d/%Y %H:%M:%S")
    folder.size = ""
    folder_key = folder.put()

def listFolders(path, userkey):
    paths = []
    qry = Folder.query(Folder.user_id == userkey)
    results = qry.fetch()
    # for result in results:
    #     rpath = result.path
    #     if start = rpath.find(path) != -1:
    #         rpath[start + len(path) + 1:]
    #
    #
    #     pathname = result.path
    #     if pathname.find(path) is not -1:
    #         paths.append(result)

    return paths

def listFiles(path):
    files = []
    qry = Files.query(File.path == path)
    results = qry.fetch()
    # for result in results:


class Test(webapp2.RequestHandler):
    def get(self):
        # qrye = Folder.query()
        # results = qrye.fetch()
        # for result in results:
        #     self.response.write(result)
        name = blobstore.BlobInfo("AZ8xfWbbRKvMIiWCk6g9qw==")
        self.response.write(name)

class DelTest(webapp2.RequestHandler):
    def get(self):
        folder = Folder()
        folder.key.delete()

class BaseHandler(webapp2.RequestHandler):              # taken from the webapp2 extrta session example
    def dispatch(self):                                 # override dispatch
        # Get a session store for this request.
        self.session_store = sessions.get_store(request=self.request)

        try:
            # Dispatch the request.
            webapp2.RequestHandler.dispatch(self)       # dispatch the main handler
        finally:
            # Save all sessions.
            self.session_store.save_sessions(self.response)

    @webapp2.cached_property
    def session(self):
        # Returns a session using the default cookie key.
        return self.session_store.get_session()

class Main(BaseHandler):
    def get(self):
        # Get user's root
        root = str(self.session.get('root'))
        if root == 'None':
            self.redirect('/login')

        # Get parameter path
        path = self.request.get('path')

        if (path == ''):
            full_path =  root
        else:
            full_path =  root + '/' + path

        # # List folder and files in the path
        folders = listFolders(full_path, root)

        # self.response.write(folders)

        full_path_len = len(full_path)

        # Objects to list
        folderitems = []
        if path != '':
            folderitems.append({'name': '..', 'size': '', 'cdate': ''});      # To show upper

        for folder in folders:
            x = folder.path[full_path_len:]
            cdate = folder.cdate
            folderitems.append({'name': x, 'size': '', 'cdate': cdate})

        # For breadcrumb
        nodes = []
        if path != '':
            parts = path.split('/')
            for i in range(len(parts)):
                route = ''
                for j in range(i):
                    route += '/' + parts[j]

                route = route[1:]
                if (route == ''):
                    route += parts[i]
                else:
                    route += '/' + parts[i]

                name = parts[i]
                nodes.append({'route': route, 'name': name})

        # # self.response.write(nodes)

        # Show home template with parameters
        template_values = {
            'title': 'DropBox',
            'nodes': nodes,
            'folderitems': folderitems,
            'fileitems' : [],
            'path': path
        }
        path = os.path.join(os.path.dirname(__file__), "templates/home.html")
        self.response.write(template.render(path, template_values))

    def post(self):
        folder = self.request.get('folder')
        path = self.request.get('path')
        root = str(self.session.get('root'))

        if (path == ''):     # If in root
            full_path = root + '/' + folder    # Trailing / means folder
        else:
            full_path = root + '/' + path + '/' + folder   # Trailing / means folder

        # Create the folder
        create_folder(full_path, root)

        self.redirect('/?path=' + path)

class SignUp(BaseHandler):

	def get(self):
		template_values = {
			'title' : 'DropBox Application | Sign Up',
			'errmsg' : '',
		}
		path = os.path.join(os.path.dirname(__file__), "templates/signup.html")
		self.response.write(template.render(path, template_values))

	def post(self):
		email = self.request.get("userEmail")
		upass = self.request.get("userPassword")
		upass_c = self.request.get("confirmPassword")

		if upass != upass_c:
			template_values = {
				'title' : 'DropBox Application | Sign Up',
				'errmsg' : 'Password dismatch',
				'email' : email,
			}
			# self.redirect('/signup')
			path = os.path.join(os.path.dirname(__file__), "templates/signup.html")
			self.response.write(template.render(path, template_values))
		else:
			if self.checkUser(email) > 0:
				template_values = {
					'title' : 'DropBox Application | Sign Up',
					'errmsg' : 'User duplicated',
					'email' : email,
				}
				# self.redirect('/signup')
				path = os.path.join(os.path.dirname(__file__), "templates/signup.html")
				self.response.write(template.render(path, template_values))
			else:
				user = User()
				user.password = upass
				user.email = email

				user_key = user.put()

				# Create root object for user

				# self.createUserRoot(str(user_key.id()))

				# Put session variable user as user's key
				self.session['root'] = str(user_key.id())

                folder = Folder()
                folder.user_id = str(user_key.id())
                folder.path = str(user_key.id())
                folder_key = folder.put()

				# Redirect to home
                self.redirect('/')

	def checkUser(self, useremail):
		qry = User.query(User.email == useremail)
		results = qry.fetch()
		return len(results)

	# def createUserRoot(self, root):
	# 	# bucket_name = app_identity.get_default_gcs_bucket_name()
	# 	# filename = '/' + bucket_name + '/' + root + '/'
 #        folder = Folder()
 #        folder.user_id =
 #        folder.path = root
	# 	create_file(filename)

class Login(BaseHandler):
    def get(self):
        template_values = {
        	'title' : 'DropBox Application | Login',
            'errmsg': ''
        }
        path = os.path.join(os.path.dirname(__file__), "templates/login.html")
        self.response.write(template.render(path, template_values))

    def post(self):
        email = self.request.get('Email')
        upass = self.request.get('Password')
        qry = User.query(User.email == email, User.password == upass)
        qry_res = qry.fetch()

        if len(qry_res) != 0:
            self.session['root'] = str(qry_res[0].key.id())
            self.redirect('/')
        else:
            template_values = {
            	'title' : 'DropBox Application | Login',
                'errmsg': 'Invalid Email or password'
            }
            path = os.path.join(os.path.dirname(__file__), "templates/login.html")
            self.response.write(template.render(path, template_values))

class Logout(BaseHandler):
    def get(self):
        self.session.clear()
        self.redirect('/login')

class Delete(BaseHandler):
    def get(self):
        bucket = os.environ.get('BUCKET_NAME', app_identity.get_default_gcs_bucket_name())
        root = str(self.session.get('root'))
        path = self.request.get('path')

        full_path = '/' + bucket + '/' + root + '/' + path
        try:
            gcs.delete(full_path)

        except gcs.NotFoundError:
            try:
                gcs.delete(full_path + '/')
            except gcs.NotFoundError:
                pass

            pass

        upper = path[0:path.rindex('/')]
        self.redirect('/?path=' + upper);

class UploadURL(webapp2.RequestHandler):
    def get(self):
        upload_url = blobstore.create_upload_url('/upload')
        self.response.out.write(upload_url)


class Upload(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        upload = self.get_uploads()[0]
        # Path
        fpath = self.request.POST.get('path')
        fname = upload.filename;

        # Get file info from blobinfo

        file = File(
            name = fname,
            blob_key = upload.key())
        file.put()

        # self.response.write(upload.filename)
        # self.redirect('/download/%s/%s' % (upload.key(), path))

class FileDownload(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self, file_key, file_name):
        self.response.headers['Content-Type'] = 'application/x-gzip'
        self.response.headers['Content-Disposition'] = 'attachment; filename=' + str(file_name)

        if not blobstore.get(file_key):
            self.error(404)
        else:
            self.send_blob(file_key)

config = {}
config['webapp2_extras.sessions'] = {
    'secret_key': 'my_secret_key',
}
app = webapp2.WSGIApplication([
        ('/', Main),
        ('/signup', SignUp),
        ('/login', Login),
        ('/logout', Logout),
        ('/test', Test),
        ('/delTest', DelTest),
        ('/delete', Delete),
        ('/uploadUrl', UploadURL),
        ('/upload', Upload),
        ('/download/([^/]+)?/([^/]+)?', FileDownload),

    ],
    debug=True,
    config=config)
