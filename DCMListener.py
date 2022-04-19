"""
DCMListener.py
C-STORE and STOW-RS endpoint

Uses default port 104 for C-STORE
Uses default port 8080 for STOW-RS
Does not save incoming data by default

Can take custom ports for HTTP an C-STORE:
	-p --port	 	| HTTP Port
	-c --c_store	| C-STORE Port 
	-s --save		| Save incoming DICOM and JSON data
"""
import os
import socket
import datetime
import argparse
import pydicom as pd
from socket import getfqdn
from colorama import init, Fore
from requests_toolbelt.multipart import decoder
from http.server import HTTPServer, BaseHTTPRequestHandler
from pynetdicom import AE, evt, build_context, StoragePresentationContexts

# Server Setup
server = socket.getfqdn()
base = os.path.dirname(os.path.abspath(__file__))

# Input argument port parsing
port = 8080
c_port = 104
SAVE_INCOMING = False
parser = argparse.ArgumentParser()
parser.add_argument('-p', '--port', help='HTTP Port', type=int)
parser.add_argument('-c', '--c_store', help='C-STORE Port', type=int)
parser.add_argument('-s',
                    '--save',
                    help='Save incoming DICOM and JSON data',
                    type=str)
args = parser.parse_args()
if args.port != None:
	port = args.port
if args.c_store != None:
	c_port = args.c_store
if args.save != None:
	if args.save.lower() in ('yes', 'true', 't', 'y', '1'):
		SAVE_INCOMING = True
	else:
		SAVE_INCOMING = False


def main():
	init(convert=True)
	print(Fore.YELLOW + str(datetime.datetime.now()) + Fore.GREEN + ' [INF] ' +
	      Fore.WHITE + 'All In One Listener Running')

	# Create folders for saving incoming data
	for folder in ['SCP', 'STOW-RS', 'ScanInvoke', 'Thinklog']:
		if SAVE_INCOMING and not os.path.isdir(base + '\\' + folder):
			os.mkdir(base + '\\' + folder)

	# Turn on C-STORE SCP
	scp = SCP(server, c_port)
	scp.run()

	# Turn on HTTP Server
	print(Fore.YELLOW + str(datetime.datetime.now()) + Fore.GREEN + ' [INF] ' +
	      Fore.WHITE + 'STOW-RS Listener Enabled at ' + Fore.CYAN + 'http://' +
	      server + Fore.BLUE + ':' + str(port) + '/stow-rs')
	if SAVE_INCOMING:
		print(Fore.YELLOW + str(datetime.datetime.now()) + Fore.GREEN +
		      ' [INF] ' + Fore.WHITE + 'Saving of incoming DICOM data ' +
		      Fore.GREEN + 'ENABLED')
	else:
		print(Fore.YELLOW + str(datetime.datetime.now()) + Fore.GREEN +
		      ' [INF] ' + Fore.WHITE + 'Saving of incoming DICOM data ' +
		      Fore.RED + 'DISABLED')
	httpd = HTTPServer((server, port), Handler)
	httpd.serve_forever()


class Handler(BaseHTTPRequestHandler):
	def do_GET(self):
		self.send_response(200)
		self.end_headers()
		self.wfile.write(b'DICOM Listener Running')

	def do_POST(self):
		content_length = int(self.headers['Content-Length'])
		body = self.rfile.read(content_length)

		# STOW-RS
		if self.path.endswith('stow-rs'):
			try:
				print(Fore.YELLOW + str(datetime.datetime.now()) + Fore.GREEN +
				      ' [INF] ' + Fore.WHITE +
				      'Incoming STOW-RS Request from ' + Fore.CYAN +
				      self.headers['Origin'])
			except:
				print(Fore.YELLOW + str(datetime.datetime.now()) + Fore.GREEN +
				      ' [INF] ' + Fore.WHITE +
				      'Incoming STOW-RS Request from ' + Fore.RED +
				      "Unknown Origin" + Fore.WHITE)
			print(Fore.BLUE + str(self.headers).rstrip())
			data = decoder.MultipartDecoder(body, self.headers['Content-Type'])
			for i in range(0, len(data.parts)):
				try:
					ds = pd.dcmread(
					    pd.filebase.DicomBytesIO(data.parts[i].content))
					if SAVE_INCOMING:
						if not os.path.isdir(base + '\\STOW-RS\\' +
						                     ds.StudyInstanceUID):
							os.mkdir(base + '\\STOW-RS\\' +
							         ds.StudyInstanceUID)
						ds.save_as(base + '\\STOW-RS\\' + ds.StudyInstanceUID +
						           '\\' + ds.SOPInstanceUID + '.dcm')
					print(Fore.YELLOW + str(datetime.datetime.now()) +
					      Fore.GREEN + ' [INF] ' + Fore.WHITE +
					      'Received SOP Instance: ' + Fore.CYAN +
					      ds.SOPInstanceUID)
					self.send_response(200)
					self.end_headers()
					self.wfile.write(b'')
				except Exception as e:
					print(Fore.YELLOW + str(datetime.datetime.now()) +
					      Fore.RED + ' [ERR] ' + Fore.WHITE +
					      'DICOM Decode Failed')
					print(e)
					self.send_response(400)
					self.end_headers()
					self.wfile.write(b'')

		# Other
		else:
			print(Fore.YELLOW + str(datetime.datetime.now()) + Fore.RED +
			      ' [ERR] ' + Fore.WHITE + 'Received unknown notification:')


class SCP:
	def __init__(self, server, port):
		self.server = server
		self.port = port
		self.handlers = [
		    (evt.EVT_CONN_OPEN, self.handle_conn_open),
		    (evt.EVT_REQUESTED, self.handle_requested),
		    (evt.EVT_ACCEPTED, self.handle_assoc_accepted),
		    (evt.EVT_ESTABLISHED, self.handle_established),
		    (evt.EVT_C_STORE, self.handle_c_store),
		    (evt.EVT_RELEASED, self.handle_released),
		    (evt.EVT_CONN_CLOSE, self.handle_conn_close),
		    (evt.EVT_REJECTED, self.handle_rejected),
		    (evt.EVT_ABORTED, self.handle_aborted),
		]
		self.ae = AE()
		self.ae.dimse_timeout = None
		self.ae.acse_timeout = None
		self.ae.network_timeout = None
		self.ae.maximum_pdu_size = 0

		### Adding contexts not present in StoragePresentationContexts ###
		# Format is 'SOP Class UID': ['Transfer Syntax UIDs']
		# Almost all SOP Classes are included in the StoragePresentationContexts list, but only four transfer syntaxes are:
		# 	1.2.840.10008.1.2, 1.2.840.10008.1.2.1, 1.2.840.10008.1.2.1.99, 1.2.840.10008.1.2.2
		# Any additional required contexts must be added here:
		self.known_contexts = {
		    '1.2.840.10008.5.1.4.1.1.2':
		    ['1.2.840.10008.1.2.4.70', '1.2.840.10008.1.2.4.90'],
		    '1.2.840.10008.5.1.4.1.1.1': ['1.2.840.10008.1.2.4.70'],
		    '1.2.840.10008.5.1.4.1.1.13.1.3': ['1.2.840.10008.1.2.4.70'],
		    '1.2.840.10008.5.1.4.1.1.13.1.4': ['1.2.840.10008.1.2.4.70'],
		    '1.2.840.10008.5.1.4.1.1.1.2': ['1.2.840.10008.1.2.4.70'],
		    '1.2.840.10008.5.1.4.1.1.6.1': ['1.2.840.10008.1.2.4.70']
		}
		self.contexts = StoragePresentationContexts
		for sop_class in self.known_contexts:
			for transfer_syntax in self.known_contexts[sop_class]:
				self.contexts.append(build_context(sop_class, transfer_syntax))
		self.ae.supported_contexts = self.contexts

	def run(self):
		print(Fore.YELLOW + str(datetime.datetime.now()) + Fore.GREEN +
		      ' [INF] ' + Fore.WHITE + 'C-STORE SCP Enabled at ' + Fore.CYAN +
		      str(server) + Fore.BLUE + ':' + str(self.port))
		try:
			self.ae.start_server((self.server, self.port),
			                     evt_handlers=self.handlers,
			                     block=False)
		except:
			print(Fore.YELLOW + str(datetime.datetime.now()) + Fore.RED +
			      ' [ERR] ' + Fore.WHITE + 'Failed to Start C-STORE SCP')

	# C- STORE HANDLERS
	def handle_c_store(self, event):
		try:
			incomingDS = event.dataset
			incomingDS.file_meta = event.file_meta
			if SAVE_INCOMING:
				if not os.path.isdir(base + '\\SCP\\' +
				                     incomingDS.StudyInstanceUID):
					os.mkdir(base + '\\SCP\\' + incomingDS.StudyInstanceUID)
				incomingDS.save_as(base + '\\SCP\\' +
				                   incomingDS.StudyInstanceUID + '\\' +
				                   incomingDS.SOPInstanceUID + '.dcm')
			print(Fore.YELLOW + str(datetime.datetime.now()) + Fore.GREEN +
			      ' [INF] ' + Fore.WHITE + 'Received SOP Instance: ' +
			      Fore.CYAN + incomingDS.SOPInstanceUID)
			return 0x0000
		except:
			print(Fore.YELLOW + str(datetime.datetime.now()) + Fore.RED +
			      ' [ERR] ' + Fore.WHITE + 'Cannot Read File')
			return 0xC000

	def handle_aborted(self, event):
		print(Fore.YELLOW + str(datetime.datetime.now()) + Fore.RED +
		      ' [ERR] ' + Fore.WHITE + 'Connection Aborted with ' + Fore.CYAN +
		      str(event.assoc.requestor.address) + Fore.BLUE + ':' +
		      str(event.assoc.requestor.port))
		return 0xC000

	def handle_assoc_accepted(self, event):
		print(Fore.YELLOW + str(datetime.datetime.now()) + Fore.GREEN +
		      ' [INF] ' + Fore.WHITE + 'Association Accepted with ' +
		      Fore.CYAN + str(event.assoc.requestor.address) + Fore.BLUE +
		      ':' + str(event.assoc.requestor.port))
		return 0x0000

	def handle_conn_close(self, event):
		print(Fore.YELLOW + str(datetime.datetime.now()) + Fore.GREEN +
		      ' [INF] ' + Fore.WHITE + 'Connection Closed with ' + Fore.CYAN +
		      str(event.assoc.requestor.address) + Fore.BLUE + ':' +
		      str(event.assoc.requestor.port))
		return 0x0000

	def handle_conn_open(self, event):
		print(Fore.YELLOW + str(datetime.datetime.now()) + Fore.GREEN +
		      ' [INF] ' + Fore.WHITE + 'Connection Opened with ' + Fore.CYAN +
		      str(event.assoc.requestor.address) + Fore.BLUE + ':' +
		      str(event.assoc.requestor.port))
		return 0x0000

	def handle_established(self, event):
		print(Fore.YELLOW + str(datetime.datetime.now()) + Fore.GREEN +
		      ' [INF] ' + Fore.WHITE + 'Association Established with ' +
		      Fore.CYAN + str(event.assoc.requestor.address) + Fore.BLUE +
		      ':' + str(event.assoc.requestor.port))
		return 0x0000

	def handle_rejected(self, event):
		print(Fore.YELLOW + str(datetime.datetime.now()) + Fore.RED +
		      ' [INF] ' + Fore.WHITE + 'Association Rejected from ' +
		      Fore.CYAN + str(event.assoc.requestor.address) + Fore.BLUE +
		      ':' + str(event.assoc.requestor.port))
		return 0xC000

	def handle_released(self, event):
		print(Fore.YELLOW + str(datetime.datetime.now()) + Fore.GREEN +
		      ' [INF] ' + Fore.WHITE + 'Association Released with ' +
		      Fore.CYAN + str(event.assoc.requestor.address) + Fore.BLUE +
		      ':' + str(event.assoc.requestor.port))
		return 0x0000

	def handle_requested(self, event):
		print(Fore.YELLOW + str(datetime.datetime.now()) + Fore.GREEN +
		      ' [INF] ' + Fore.WHITE + 'Association Requested from ' +
		      Fore.CYAN + str(event.assoc.requestor.address) + Fore.BLUE +
		      ':' + str(event.assoc.requestor.port))
		return 0x0000


if __name__ == '__main__':
	main()
