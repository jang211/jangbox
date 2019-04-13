import webapp2
from webapp2_extras import sessions
import os
import time
import cloudstorage as gcs
from google.appengine.ext.webapp import template
from google.appengine.api import app_identity
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
from models.user import User
from models.file import File
from models.folder import Folder

my_default_retry_params = gcs.RetryParams(initial_delay = 0.2,
                                          max_delay = 5.0,
                                          backoff_factor = 2,
                                          max_retry_period = 15)
gcs.set_default_retry_params(my_default_retry_params)


def create_file(filename):

	write_retry_params = gcs.RetryParams(backoff_factor = 1.1)
	gcs_file = gcs.open(filename,
                        'w',
                        content_type = 'text/plain',
                        options={'x-goog-meta-foo': 'foo',
                                 'x-goog-meta-bar': 'bar'},
                        retry_params = write_retry_params)
	gcs_file.write('abcde\n')
	gcs_file.write('f'*1024*4 + '\n')
	gcs_file.close()

def listDirectory(path, userkey):
    paths = []
    qry = Folder.query(Folder.user_id == userkey)
    results = qry.fetch()
    path_len = len(path)
    for result in results:
        subpath = result.path[path_len:0]
        paths.append(subpath)
    return paths

class Test(webapp2.RequestHandler):
	def get(self):
		bucket = app_identity.get_default_gcs_bucket_name()

		# List users
		user = User()

		# List objects
		items = []
		stats = gcs.listbucket('/' + bucket)
		for stat in stats:
			items.append(stat.filename)
			self.response.write(stat.filename)
			self.response.write('</br>')

		# Delte all objects
		# for item in items:
		# 	try:
		# 		gcs.delete(item)
		# 	except gcs.NotFoundError:
		# 		pass
class DelTest(webapp2.RequestHandler):
    def get(self):
        bucket = app_identity.get_default_gcs_bucket_name()
        items = []
        stats = gcs.listbucket('/' + bucket)
        for stat in stats:
            items.append(stat.filename)
            self.response.write(stat.filename)
            self.response.write('</br>')

        # Delte all objects
        for item in items:
          try:
              gcs.delete(item)
          except gcs.NotFoundError:
              pass

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
        # Get bucket name
        bucket = os.environ.get('BUCKET_NAME', app_identity.get_default_gcs_bucket_name())


        if (path == ''):
            full_path =  '/' + bucket + '/' + root
        else:
            full_path =  '/' + bucket + '/' + root + '/' + path

        # stats = listDirectory(full_path, root)
        # self.response.write(stats)
        full_path_len = len(full_path)
        # List folder and files in the path
        stats = gcs.listbucket(full_path)

        # Objects to list
        folderitems = []
        fileitems = []
        if path != '':
            folderitems.append({'name': '..', 'size': '', 'cdate': ''});      # To show upper

        for stat in stats:
            x = stat.filename[full_path_len + 1:]
            if x != '' and x.find('/') == -1:
                size = stat.st_size
                ctime = time.strftime("%Y-%m-%d", time.gmtime(stat.st_ctime))
                fileitems.append({'name': x, 'size': stat.st_size, 'cdate': ctime})
            else:
                x = x[:-1]
                if x != '' and x.find('/') == -1:
                    size = stat.st_size
                    ctime = time.strftime("%Y-%m-%d", time.gmtime(stat.st_ctime))
                    # ctime = stat.st_ctime
                    folderitems.append({'name': x, 'size': stat.st_size, 'cdate': ctime})

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

        # self.response.write(nodes)

        # Show home template with parameters
        template_values = {
            'title': 'DropBox',
            'nodes': nodes,
            'folderitems': folderitems,
            'fileitems' : fileitems,
            'path': path
        }
        path = os.path.join(os.path.dirname(__file__), "templates/home.html")
        self.response.write(template.render(path, template_values))

    def post(self):
        folder = self.request.get('folder')
        path = self.request.get('path')
        bucket = os.environ.get('BUCKET_NAME', app_identity.get_default_gcs_bucket_name())
        root = str(self.session.get('root'))

        if (path == ''):     # If in root
            full_path = '/' + bucket + '/' + root + '/' + folder + '/'     # Trailing / means folder
        else:
            full_path = '/' + bucket + '/' + root + '/' + path + '/' + folder + '/'     # Trailing / means folder

        # Create the folder
        create_file(full_path)

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

        file = File(
            name = fname,
            blob_key = upload.key())
        file.put()

        # self.response.write(upload.filename)
        # self.redirect('/download/%s/%s' % (upload.key(), path))

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
        ('/download/([^/]+)?/([^/]+)?', FileDownload),
        ('/uploadUrl', UploadURL),
        ('/delete', Delete),
        ('/upload', Upload),
    ],
    debug=True,
    config=config)
