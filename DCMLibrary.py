"""
DCMLibrary.py - Useful functions for DICOM data manipulation
"""
import requests
import os
import pydicom as pd
import numpy as np
from subprocess import call, DEVNULL

# Optional Modes
DEBUG = False
USE_HTTP = False

# Setup
http = 'http'
if USE_HTTP:
	cert = False
	http += '://'
else:
	cert = os.path.dirname(os.path.abspath(__file__)) + r'\CertFile.crt'
	http += 's://'

###########################################################################################################################
### DICOM Gateway #########################################################################################################
###########################################################################################################################


def QIDO(URL,
         study=None,
         series=None,
         SOP=None,
         patientId=None,
         dataSource=None,
         anonymize=None,
         mode=None,
         token=None,
         verify=True):
	"""
	Query for a DICOM study, series, or instance by it's UIDs
		Options for anonymize are None and 'yes'
		Option for mode are None and 'xml'
		Assumes JSON if mode is None
	"""
	if patientId != None:
		URL += 'studies?PatientID=' + patientId
	elif study != None and series == None and SOP == None:
		URL += 'studies?StudyInstanceUID=' + study
	elif study != None and series != None and SOP == None:
		URL += 'studies/' + study + '/series?SeriesInstanceUID=' + series
	elif study == None and series != None and SOP == None:
		URL += 'series?SeriesInstanceUID=' + series
	elif study != None and series != None and SOP != None:
		URL += 'studies/' + study + '/series/' + series + '/instances?SOPInstanceUID=' + SOP
	elif study != None and series == None and SOP != None:
		URL += 'studies/' + study + '/instances?SOPInstanceUID=' + SOP
	elif study == None and series == None and SOP != None:
		URL += 'instances?SOPInstanceUID=' + SOP
	else:
		print('Error: Not enough values to query')
		return []
	if dataSource != None:
		URL += '?datasource=' + dataSource
	if anonymize != None:
		URL += '?anonymize=' + anonymize
	headers = {}
	if token != None:
		headers['Authorization'] = 'Bearer ' + token
	mode = str(mode)
	if verify == True:
		verify = cert
	if mode.lower() == 'xml':
		from requests_toolbelt.multipart import decoder
		headers['Accept'] = 'multipart/related; type=application/dicom+xml'
		r = requests.get(url=URL, headers=headers, verify=verify)
		if r.status_code != 200 or DEBUG:
			print(r.status_code)
			print(r.text)
		if r.status_code == 204:
			return []
		data = decoder.MultipartDecoder.from_response(r)
		ds = []
		for i in range(0, len(data.parts)):
			ds.append(data.parts[i].content)
		return ds
	else:
		headers['Accept'] = 'application/json'
		r = requests.get(url=URL, headers=headers, verify=verify)
		if r.status_code != 200 or DEBUG:
			print(r.status_code)
			print(r.text)
		if r.status_code != 204:
			return r.json()
		else:
			return []


def WADO(URL,
         study,
         series=None,
         SOP=None,
         frames=None,
         dataSource=None,
         anonymize=None,
         mode=None,
         token=None,
         verify=True):
	"""
	Retrieve a DICOM study, series, or instance XML/JSON metadata or DICOM object binary
		Options for anonymize are None and 'yes'
		Options for mode are None, 'xml', and 'json'
		Assumes DICOM object binary if mode is None
		
		NOTE: You must save the DICOM data to a file in order to read it's pixel array data
		This is because of the way PIL/GDCM reads image pixel data, which is called upon by pydicom
		Use exportDS to easily save WADO-RS DICOM object binary results
	"""
	URL += study
	if series != None:
		URL += '/series/' + series
		if SOP != None:
			URL += '/instances/' + SOP
			if frames != None:
				URL += '/frames/' + frames
	mode = str(mode)
	if mode.lower() in ['xml', 'json']:
		URL += '/metadata/'
	if dataSource != None:
		URL += '?datasource=' + dataSource
	if anonymize != None:
		URL += '?anonymize=' + anonymize
	headers = {}
	if token != None:
		headers['Authorization'] = 'Bearer ' + token
	if verify == True:
		verify = cert
	if mode.lower() == 'json':
		headers['Accept'] = 'application/dicom+json'
		r = requests.get(url=URL, headers=headers, verify=verify)
		if r.status_code != 200 or DEBUG:
			print(r.status_code)
			print(r.text)
		return r.json()
	elif mode.lower() == 'xml':
		headers['Accept'] = 'application/dicom+xml'
		r = requests.get(url=URL, headers=headers, verify=verify)
		if r.status_code not in [200, 206] or DEBUG:
			print(r.status_code)
			print(r.text)
		return r.content
	else:
		from requests_toolbelt.multipart import decoder
		headers['Accept'] = 'multipart/related; type=application/dicom'
		r = requests.get(url=URL, headers=headers, verify=verify)
		if r.status_code != 200 or DEBUG:
			print(r.status_code)
			if r.status_code != 200:
				print(r.text)
		data = decoder.MultipartDecoder.from_response(r)
		ds = []
		for i in range(len(data.parts)):
			ds.append(
			    pd.dcmread(pd.filebase.DicomBytesIO(data.parts[i].content)))
		return ds


def exportDS(ds, outDir=None, openDir=True):
	"""
	Export a list if pydicom datasets to a folder, naming each file by modality
		Creates and returns a temporary directory to save to if not given one
		Opens directory folder in file explorer by default
	"""
	if outDir == None:
		from tempfile import mkdtemp
		outDir = mkdtemp()
	counter = {}

	if type(ds) == pd.dataset.FileDataset:
		ds = [ds]
	for dsi in ds:
		try:
			modality = dsi.Modality
		except:
			modality = 'IMG'
		if modality not in counter:
			counter[modality] = 0
		dsi.save_as(outDir + '\\' + modality + str(counter[modality]) + '.dcm')
		counter[modality] += 1
	if openDir:
		os.startfile(outDir)
	return outDir


def STOW(URL, inDir, study=None, dataSource=None, token=None, verify=True):
	"""
	Store DICOM file(s) to server using RESTful API
		inDir is either a DICOM file, directory of DICOM files, pydicom dataset, or list of pydicom datasets
		Works recursively through subdirectories to collect DICOM files if given a directory
		NOTE: Limited to 1024 DICOM instances due to a multipart request limitation
	"""
	if study != None:
		URL += study
	if dataSource != None:
		URL += '?datasource=' + dataSource
	headers = {}
	if token != None:
		headers['Authorization'] = 'Bearer ' + token
	files = []
	if type(inDir) == pd.dataset.FileDataset:
		from tempfile import NamedTemporaryFile
		dcm = NamedTemporaryFile().name
		inDir.save_as(dcm)
		files.append(
		    ('file', ('file', open(dcm, 'rb').read(), 'application/dicom')))
		os.remove(dcm)
	elif type(inDir) == list:
		from tempfile import NamedTemporaryFile
		dcm = NamedTemporaryFile().name
		for ds in inDir:
			if type(ds) == pd.dataset.FileDataset:
				ds.save_as(dcm)
				files.append(
				    ('file', ('file', open(dcm,
				                           'rb').read(), 'application/dicom')))
		os.remove(dcm)
		if files == []:
			print('Error: No DICOM files found in inDir')
			return {}
	elif os.path.isdir(inDir):
		for root, _dirs, f in os.walk(inDir):
			for dcm in f:
				try:
					pd.dcmread(root + '\\' + dcm)
					files.append(
					    ('file', ('file', open(root + '\\' + dcm, 'rb').read(),
					              'application/dicom')))
				except:
					pass
		if files == []:
			print('Error: No DICOM files found in inDir')
			return {}
	elif os.path.isfile(inDir):
		try:
			pd.dcmread(inDir)
			files.append(
			    ('file', ('file', open(inDir,
			                           'rb').read(), 'application/dicom')))
		except:
			print('Error: inDir is not a DICOM file. Skipping file...')
	else:
		print('Error: inDir is neither a file nor directory')
		return {}
	if verify == True:
		verify = cert
	r = requests.post(url=URL, files=files, headers=headers, verify=verify)
	print(r.status_code)
	if r.status_code not in [200, 202] or DEBUG:
		print(r.text)
	return r.content


def C_STORE(server, inDir, ae_title=b'DicomServerSCP', port=104):
	"""
	Store DICOM file(s) to server using C-STORE
		inDir is either a DICOM file, directory of DICOM files, pydicom dataset, or list of pydicom datasets
		Works recursively through subdirectories to collect DICOM files if given a directory
	"""
	from pynetdicom import AE, build_context
	from socket import gethostbyname

	if type(ae_title) != bytes:
		ae_title = ae_title.encode()
	ae = AE(ae_title=str.encode(os.getenv('COMPUTERNAME')))

	if type(inDir) == list:
		ds = inDir
	elif type(inDir) == pd.dataset.FileDataset:
		ds = [inDir]
	elif type(inDir) == str:
		if os.path.isfile(inDir):
			ds = [pd.dcmread(inDir)]
		elif os.path.isdir(inDir):
			ds = []
			for root, _dirs, files in os.walk(inDir):
				for f in files:
					try:
						ds.append(pd.dcmread(root + '\\' + f))
					except:
						pass

	for i in range(len(ds)):
		try:
			cx = build_context(ds[i].SOPClassUID,
			                   [ds[i].file_meta.TransferSyntaxUID])
			if cx not in ae.requested_contexts:
				ae.requested_contexts.append(cx)
		except:
			pass

	n = 0
	maxRetry = 5
	for i in range(maxRetry):
		try:
			print('Attempting to establish association with ' + server + ':' +
			      str(port) + ' using Called AE Title ' + ae_title.decode() +
			      ' and Calling AE Title ' + os.getenv('COMPUTERNAME'))
			assoc = ae.associate(gethostbyname(server),
			                     port,
			                     ae_title=ae_title)
			assoc.dimse_timeout = None
			assoc.acse_timeout = None
			assoc.network_timeout = None
			assoc.maximum_pdu_size = 0
			if assoc.is_established:
				print('Association Established')
				while True:
					print('Sending SOP Instance ' + ds[n].SOPInstanceUID)
					assoc.send_c_store(ds[n])
					n += 1
					if n >= len(ds):
						break
				assoc.release()
				if len(ds) == 1:
					print('C-STORED 1 instance')
				else:
					print('C-STORED ' + str(len(ds)) + ' instances')
			else:
				print('Error: Failed to Establish Association')
			break
		except Exception as e:
			if i == maxRetry - 1:
				print('Error: Failed to C-STORE after five attempts')
			else:
				print('Error: ' + str(e))


###########################################################################################################################
### DICOM Data Manipulation and Visualization #############################################################################
###########################################################################################################################


def renameDCM(inDir, patientName=None):
	"""
	Change the Patient Name, IDs, and dates of a DICOM file, directory of DICOM files, pydicom dataset, or list of datasets
		Returns output as a list
	"""
	import random
	from copy import deepcopy

	# Parse input so that it is a list
	if type(inDir) == list:
		ds = inDir
	elif type(inDir) == pd.dataset.FileDataset:
		ds = [inDir]
	elif type(inDir) == str:
		if os.path.isfile(inDir):
			ds = [pd.dcmread(inDir)]
		elif os.path.isdir(inDir):
			ds = []
			for root, _dirs, files in os.walk(inDir):
				for f in files:
					try:
						ds.append(pd.dcmread(root + '\\' + f))
					except:
						pass
	else:
		print('Error: inDir is neither a file, directory, list, nor dataset')
		exit()

	# New patient name logic using names libary based on original study patient sex and modality
	if patientName == None:
		import names

		try:
			modality = ds[0].Modality
		except:
			modality = None
		try:
			gender = ds[0].PatientSex
		except:
			gender = None

		if gender == 'M':
			patientName = names.get_last_name() + '^' + names.get_first_name(
			    'male')
		elif gender == 'F' or modality == 'MG':
			patientName = names.get_last_name() + '^' + names.get_first_name(
			    'female')
		else:
			patientName = names.get_last_name() + '^' + names.get_first_name()

	def str_hash(input, l):
		"""
		Simple string hash function
		"""
		h = hash(input)
		if h < 0:
			h = -h
		h = str(h)
		if len(h) > l:
			h = h[:l]
		return h

	# Identifier generation for IDs and UIDs
	identifier1 = str_hash(patientName, 7)

	# Dictionary and list for anonymization mapping
	AccessionNumber = pd.tag.Tag(0x8, 0x50)
	StudyID = pd.tag.Tag(0x20, 0x10)
	uidmap = {}
	out = []

	# Anonymize DICOM datasets
	for i in range(len(ds)):
		# Global patient information
		out.append(deepcopy(ds[i]))
		out[-1].PatientName = patientName
		out[-1].PatientID = identifier1

		# Study Instance UID
		if ds[i].StudyInstanceUID in uidmap:
			out[-1].StudyInstanceUID = uidmap[ds[i].StudyInstanceUID]
		else:
			out[-1].StudyInstanceUID = '1.2.840.' + identifier1 + '.' + str(
			    random.randint(10000000, 99999999))
			uidmap[ds[i].StudyInstanceUID] = out[-1].StudyInstanceUID

		# Accession Number
		if AccessionNumber not in ds[i]:
			ds[i].add_new((0x8, 0x50), 'SH',
			              str_hash(ds[i].StudyInstanceUID, 16))
		if ds[i].AccessionNumber in uidmap:
			out[-1].AccessionNumber = uidmap[ds[i].AccessionNumber]
		else:
			out[-1].AccessionNumber = str_hash(out[-1].StudyInstanceUID, 16)
			uidmap[ds[i].AccessionNumber] = out[-1].AccessionNumber

		# Study ID
		if StudyID not in ds[i]:
			ds[i].add_new((0x20, 0x10), 'SH',
			              str_hash(ds[i].AccessionNumber, 16))
		if ds[i].StudyID in uidmap:
			out[-1].StudyID = uidmap[ds[i].StudyID]
		else:
			out[-1].StudyID = str_hash(out[-1].AccessionNumber, 16)
			uidmap[ds[i].StudyID] = out[-1].StudyID

		# Series Instance UID
		if ds[i].SeriesInstanceUID in uidmap:
			out[-1].SeriesInstanceUID = uidmap[ds[i].SeriesInstanceUID]
		else:
			out[-1].SeriesInstanceUID = out[-1].StudyInstanceUID + '.' + str(
			    random.randint(1000000000, 9999999999))
			uidmap[ds[i].SeriesInstanceUID] = out[-1].SeriesInstanceUID

		# SOP Instance UID
		out[-1].SOPInstanceUID = out[-1].SeriesInstanceUID + '.' + str(i)

	return out


def resizeDCM(inDir, outDir=None, xScale=0.5, yScale=0.5):
	"""
	Resize a DICOM image or series
		Saves output to either a new file, new directory, pydicom dataset, or list
	"""
	from scipy.ndimage import zoom

	def resize(ds):
		"""
		Resize a DICOM file
		"""
		ds.decompress()
		sub1 = ds.pixel_array
		sub = zoom(sub1, [yScale, xScale])
		ds.PixelData = sub.tobytes()
		ds.Rows, ds.Columns = sub.shape
		ps = ds.PixelSpacing
		ps = [ps[0] / yScale, ps[1] / xScale]
		ds.PixelSpacing = ps
		return ds

	if type(inDir) == str:
		if os.path.isfile(inDir):
			ds = pd.dcmread(inDir)
		elif os.path.isdir(inDir):
			ds = []
			for root, _dirs, files in os.walk(inDir):
				for f in files:
					try:
						ds.append(pd.dcmread(root + '\\' + f))
					except:
						pass
	else:
		ds = inDir
	if type(ds) == pd.dataset.FileDataset:
		output = resize(ds)
		if outDir != None:
			output.save_as(outDir)
	elif type(ds) == list:
		output = []
		for ds0 in ds:
			output.append(resize(ds0))
		if outDir != None:
			exportDS(output, outDir, False)
	else:
		print('Error: inDir is neither a file, directory, list, nor dataset')
		exit()
	return output


def loadVolumes(inDir, n1mm3=False, windowMode=None):
	"""
	Load a DICOM study located in a directory or list as 3D volume(s)
		Stored as a 3D numpy array
		Set n1mm3 to normalize 3D numpy array to 1 mm3 voxels
		Set defaultWindow to use window volume using default window/level values found in DICOM header of first file in folder
		View these volumes slice by slice using sliceViewer
		View these volumes in 3D using volViewer (may require additional processing beforehand)
	"""
	# TODO: Optimize this whole function with threading and queueing
	ds = {}
	if type(inDir) == list:
		from tempfile import NamedTemporaryFile
		tmp = NamedTemporaryFile().name
		for dsn in inDir:
			if dsn.StudyInstanceUID not in ds:
				ds[dsn.StudyInstanceUID] = {}
			if dsn.SeriesInstanceUID not in ds[dsn.StudyInstanceUID]:
				ds[dsn.StudyInstanceUID][dsn.SeriesInstanceUID] = [dsn]
			if dsn not in ds[dsn.StudyInstanceUID][dsn.SeriesInstanceUID]:
				ds[dsn.StudyInstanceUID][dsn.SeriesInstanceUID].append(dsn)
	else:
		tmp = None
		for root, _dirs, files in os.walk(inDir):
			for dcm in files:
				try:
					dsn = pd.dcmread(root + '\\' + dcm)
					if dsn.StudyInstanceUID not in ds:
						ds[dsn.StudyInstanceUID] = {}
					if dsn.SeriesInstanceUID not in ds[dsn.StudyInstanceUID]:
						ds[dsn.StudyInstanceUID][dsn.SeriesInstanceUID] = [dsn]
					if dsn not in ds[dsn.StudyInstanceUID][
					    dsn.SeriesInstanceUID]:
						ds[dsn.StudyInstanceUID][dsn.SeriesInstanceUID].append(
						    dsn)
				except:
					pass
	volumes = []
	for study in ds:
		for series in ds[study]:
			try:
				if ds[study][series][0].Modality == 'SEG':
					raw = ds[study][series][0].pixel_array
				else:
					if tmp != None:
						ds[study][series][0].save_as(tmp)
						ds[study][series][0] = pd.dcmread(tmp)
					c, r = ds[study][series][0].pixel_array.shape
					n = 0
					for dsn in ds[study][series]:
						if dsn.InstanceNumber > n:
							n = dsn.InstanceNumber
					raw = np.zeros([n, c, r], dtype=np.int16)
					for dsn in ds[study][series]:
						if tmp != None:
							dsn.save_as(tmp)
							dsn = pd.dcmread(tmp)
						raw[dsn.InstanceNumber - 1, :, :] = dsn.pixel_array
				if n1mm3:
					try:
						from warnings import filterwarnings
						filterwarnings('ignore', '.*output shape of zoom.*')
						from scipy.ndimage import zoom
						yScale, xScale = ds[study][series][0].PixelSpacing
						zScale = float(ds[study][series][0].SliceThickness)
						raw = zoom(raw, (zScale, yScale, xScale))
					except:
						print('Unable to scale study/series ' +
						      ds[study][series][0].StudyInstanceUID + '/' +
						      ds[study][series][0].SeriesInstanceUID)
				if windowMode != None:
					if windowMode.lower() == 'default':
						c = int(ds[study][series][0].WindowCenter)
						w = int(ds[study][series][0].WindowWidth)
						raw = window(raw, None, c, w)
					else:
						raw = window(raw, windowMode)
				volumes.append(raw)
			except:
				print('Unable to volumize study/series ' +
				      ds[study][series][0].StudyInstanceUID + '/' +
				      ds[study][series][0].SeriesInstanceUID)
	if tmp != None:
		os.remove(tmp)
	return volumes


def window(img, mode=None, c=None, w=None):
	"""
	Window/level a 3D volume using center and window
		Recommended center and window are often included in the original DICOM file
		Built in modes are bone, abdomen, lung, and head
	"""
	from copy import deepcopy

	if mode != None:
		if mode.lower() == 'bone':
			c = 400
			w = 2000
		elif mode.lower() == 'abdomen':
			c = 55
			w = 426
		elif mode.lower() == 'lung':
			c = -585
			w = 1800
		elif mode.lower() == 'head':
			c = 50
			w = 150
	mx = np.max(img)
	mn = np.min(img)
	img2 = deepcopy(img)
	img2 = img2 - c
	constant1 = (mx - mn) / w
	constant2 = (mx + mn) / 2
	if img2.ndim == 3:
		z, y, x = img2.shape
		out = np.zeros([z, y, x])
		for k in range(0, z):
			for j in range(0, y):
				for i in range(0, x):
					out[k, j, i] = constant1 * img2[k, j, i] + constant2
					if out[k, j, i] <= mn:
						out[k, j, i] = mn
					elif out[k, j, i] >= mx:
						out[k, j, i] = mx
		return out
	elif img2.ndim == 2:
		y, x = img2.shape
		out = np.zeros([y, x])
		for j in range(0, y):
			for i in range(0, x):
				out[j, i] = constant1 * img2[j, i] + constant2
				if out[j, i] <= mn:
					out[j, i] = mn
				elif out[j, i] >= mx:
					out[j, i] = mx
		return out
	else:
		print('Error: img not a 2D or 3D numpy array image')
		return img


def sliceViewer(X):
	"""
	=================================
	sliceViewer - Image Slices Viewer
	=================================

	Scroll through 2D image slices of a 3D array.
	Original code from: https://matplotlib.org/2.1.2/gallery/animation/image_slices_viewer.html
	"""
	import matplotlib.pyplot as plt

	class IndexTracker(object):
		def __init__(self, ax, X):
			self.ax = ax
			self.ax.set_title('use scroll wheel to navigate images')

			self.X = X
			self.slices = X.shape[0]
			self.ind = 0

			self.im = ax.imshow(self.X[self.ind, :, :], cmap='gray')
			self.update()

		def onscroll(self, event):
			if event.button == 'up':
				self.ind = (self.ind + 1) % self.slices
			else:
				self.ind = (self.ind - 1) % self.slices
			self.update()

		def onpress(self, event):
			if event.key == 'pageup':
				self.ind = (self.ind + 10) % self.slices
			elif event.key == 'pagedown':
				self.ind = (self.ind - 10) % self.slices
			self.update()

		def update(self):
			self.im.set_data(self.X[self.ind, :, :])
			self.ax.set_ylabel('slice %s' % self.ind)
			self.im.axes.figure.canvas.draw()

	fig, ax = plt.subplots(1, 1)
	tracker = IndexTracker(ax, X)
	fig.canvas.mpl_connect('scroll_event', tracker.onscroll)
	fig.canvas.mpl_connect('key_press_event', tracker.onpress)
	plt.show()


def volViewer(raw):
	"""
	View a 3D numpy array as a 3D volume
		Using mayavi: https://docs.enthought.com/mayavi/mayavi/installation.html
	"""
	from mayavi import mlab
	mlab.contour3d(raw)
	mlab.show()


###########################################################################################################################
### Miscellaneous #########################################################################################################
###########################################################################################################################


def queryOracleDb(server, username, password, port, service, table, qIn, qOut):
	"""
	Query an Oracle Database
	"""
	import cx_Oracle
	os.environ['PATH'] += ';' + os.path.dirname(
	    os.path.abspath(__file__)) + r'\instantclient'
	conn = cx_Oracle.connect(
	    user=username,
	    password=password,
	    dsn='(DESCRIPTION=(ADDRESS_LIST=(ADDRESS=(PROTOCOL=TCP)(HOST=' +
	    server + ')(PORT=' + str(port) + ')))(CONNECT_DATA=(SERVICE_NAME=' +
	    service + ')))')
	cursor = conn.cursor()
	cursor.execute("SELECT " + qOut + " FROM " + table + " WHERE " + qIn)
	output = cursor.fetchall()
	cursor.close()
	if DEBUG:
		print(output)
	return output


def iisreset(server, username=r'local\administrator', password='synapse'):
	"""
	iisreset a server
	"""
	call('WMIC /USER:' + username + ' /PASSWORD:' + password + ' /node:' +
	     server + ' process call create "cmd.exe /c iisreset.exe"')


def netUse(server,
           folder=r'\d$',
           user=r'local\administrator',
           password='synapse'):
	"""
	Login to a server / remote machine to access it's filesystem
	"""
	call(r'net use \\' + server + folder + ' /USER:' + user + ' ' + password,
	     stdout=DEVNULL,
	     stderr=DEVNULL)