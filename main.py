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
from models.shared import Shared

my_default_retry_params = gcs.RetryParams(initial_delay = 0.2,
                                          max_delay = 5.0,
                                          backoff_factor = 2,
                                          max_retry_period = 15)
gcs.set_default_retry_params(my_default_retry_params)

def duplicated(path):
    qry = Folder.query(Folder.path == path)
    result = qry.fetch()
    if len(result) > 0:
        return True
    else:
        return False

       
def create_folder(path, userkey):
    folder = Folder()
    folder.user_id = userkey
    folder.path = path
    now = datetime.now()
    folder.cdate = now.strftime("%m/%d/%Y %H:%M:%S")
    folder.size = ""
    folder_key = folder.put()

def listFolders(path, userkey):
    folders = []
    if (path != userkey): # if root
        folders.append({'name': '..', 'cdate': ''})

    # Get list of folders from datastore
    qry = Folder.query(Folder.user_id == userkey)
    results = qry.fetch()
    for result in results:
        rpath = result.path
        start = rpath.find(path)
        if start != -1:
            sub = rpath[start + len(path) + 1:]
            if sub != '':
                if sub.find('/') == -1:
                    folders.append({'name': sub, 'cdate': result.cdate})

    return folders

def listFiles(path):
    qry = File.query(File.path == path)
    results = qry.fetch()
    return results

def listUsers(userroot):
    qry = User.query()
    results = qry.fetch()
    userlist = []
    for result in results:
        userkey = result.key.id()
        if str(userkey) != str(userroot):
            userlist.append(result)
    return userlist

def listSharedbyFiles(userroot):
    qry = User.query()
    res = qry.fetch()
    userself = ''
    for r in res:
        if str(r.key.id()) == str(userroot):
            userself = r.email
            break
    
    qry = Shared.query(Shared.sh_by != userself)
    results = qry.fetch()
    return results

def listShareFiles(userroot):
    qry = User.query()
    res = qry.fetch()
    userself = ''
    for r in res:
        if str(r.key.id()) == str(userroot):
            userself = r.email
            break
    
    qry = Shared.query(Shared.sh_by == userself)
    results = qry.fetch()
    for result in results:
        result.path = result.path[len(userroot):]
    return results

class BaseHandler(blobstore_handlers.BlobstoreUploadHandler, webapp2.RequestHandler):
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

        # # List files in this folder
        files = listFiles(full_path)

        # List users
        users = listUsers(root)

        # List shared files
        sharedbyfiles = listSharedbyFiles(root)

        # List share files
        sharefiles = listShareFiles(root)


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

        # Find error messages
        error = self.request.get('err')
        errmsg = ''
        if error == 'fdup':
            errmsg = 'Folder already exists.'

        # Show home template with parameters
        template_values = {
            'title': 'DropBox Application | Home',
            'nodes': nodes,
            'folderitems': folders,
            'fileitems' : files,
            'useritems' : users,
            'sharedbyitems' : sharedbyfiles,
            'shareitems' : sharefiles,
            'path': path,
            'errmsg': errmsg
        }
        path = os.path.join(os.path.dirname(__file__), "templates/home.html")
        self.response.write(template.render(path, template_values))

    def post(self):
        folder = self.request.get('folder')
        path = self.request.get('path')
        root = str(self.session.get('root'))

        if (path == ''):     # If in root
            full_path = root + '/' + folder
        else:
            full_path = root + '/' + path + '/' + folder

        if duplicated(full_path):
            self.redirect('/?path=' + path + '&err=fdup')
        else:
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

class DelFolder(BaseHandler):
    def get(self):
        root = self.session.get('root')
        path = self.request.get('path')

        full_path = root + '/' + path

        # Delete folder from datastore. Query condition means it contain sub directory.
        qry = Folder.query(Folder.path >= full_path)
        results = qry.fetch()

        # Query result is not correct, because of condition for querying. So fix them.
        for result in results:
            result_path = result.path
            if result_path.find(path) is not -1:
                result.key.delete()

        # After deleting, make directory for redirecting.
        if path.find('/') is not -1:
            red_path = path[:path.rindex('/')]
        else:
            red_path = ''

        self.redirect('/?path=' + red_path)

class DelFile(BaseHandler):
    def post(self):
        root = self.session.get('root')
        file = self.request.get('file')
        file = file.split(',')
        full_path = root + '/' + file[0]
        filename = file[1]

        # Delete from file model
        qry = File.query(File.path == full_path, File.name == filename)
        res = qry.fetch()
        res[0].key.delete()

        # if file is shared, delete it from sharefile model
        qry = Shared.query(Shared.path == full_path, Shared.name == filename)
        res = qry.fetch()
        res[0].key.delete()

        # Delete from blobstore
        blobstore.delete(res[0].blob_key)

        self.redirect('/?path=' + file[0])


class UploadURL(webapp2.RequestHandler):
    def get(self):
        upload_url = blobstore.create_upload_url('/upload')
        self.response.out.write(upload_url)


class Upload(BaseHandler):
    def post(self):
        upload = self.get_uploads()[0]

        # Path
        root = self.session.get('root')
        path = self.request.POST.get('path')
        if path != '':
            fpath = root + '/' + path
        else:
            fpath = root

        fname = upload.filename;
        fsize = round(blobstore.BlobInfo(upload.key()).size/1000, 2)
        if fsize < 1:
            fsize = 1
        fdate = blobstore.BlobInfo(upload.key()).creation

        qry = File.query(File.path == fpath, File.name == fname)
        result = qry.fetch()
        if len(result) > 0:
            result[0].key.delete()
            blobstore.delete(result[0].blob_key)
            
            # Get file info from blobinfo
        file = File(
            name = fname,
            path = fpath,
            blob_key = upload.key(),
            size = str(fsize),
            cdate = str(fdate.strftime("%m/%d/%Y %H:%M:%S"))
        )
        file.put()

        # self.response.write(upload.filename)
        self.redirect('/?path=' + path)

class FileDownload(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self, file_key, file_name):
        self.response.headers['Content-Type'] = 'application/x-gzip'
        self.response.headers['Content-Disposition'] = 'attachment; filename=' + str(file_name)

        if not blobstore.get(file_key):
            self.error(404)
        else:
            self.send_blob(file_key)

class Sharefile(BaseHandler):
    def post(self):
        root = self.session.get('root')

        userto = self.request.get('selectuser')
        filename = self.request.get('filename')
        path =  self.request.get('path')
        
        if path == '':
            full_path = root
        else:
            full_path = root + '/' + path

        qry = User.query()
        results = qry.fetch()
        for result in results:
            userkey = result.key.id()
            if str(userkey) == str(root):
                share_by = result.email

        # self.response.write(share_by)

        qry = File.query(File.path == full_path, File.name == filename)
        results = qry.fetch()

        shared = Shared()
        shared.name = filename
        shared.path = full_path
        shared.blob_key = results[0].blob_key
        shared.sh_by = share_by
        shared.sh_to = userto
        shared.size = results[0].size
        shared.time = results[0].cdate
        shared.put()

        self.redirect('/?path=' + path)      

config = {}
config['webapp2_extras.sessions'] = {
    'secret_key': 'my_secret_key',
}
app = webapp2.WSGIApplication([
        ('/', Main),
        ('/signup', SignUp),
        ('/login', Login),
        ('/logout', Logout),
        ('/del_folder', DelFolder),
        ('/del_file', DelFile),
        ('/uploadUrl', UploadURL),
        ('/upload', Upload),
        ('/download/([^/]+)?/([^/]+)?', FileDownload),
        ('/sharefile', Sharefile),
    ],
    debug=True,
    config=config)
