"""
AIDataRandomize.py - Easy DICOM study and AI result randomization
Anonymizes both the original DICOM study and the AI results to match, accounting for all UUIDs
AI results being DICOM modalities which reference the original images and contain overlays, such as SEG, PR, SR, and SC
"""
import os
import random
import names
import argparse
import pydicom as pd
from tempfile import mkdtemp
from copy import deepcopy


def main():
	# Argument parsing
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument(
	    '-n',
	    '--input',
	    help=
	    'Input study folder to be anonymized/randomized.',
	    type=str)
	parser.add_argument(
	    '-o',
	    '--output',
	    help=
	    'Output study folder. If not given, data will be saved to a temporary directory.',
	    type=str)
	parser.add_argument(
	    '-f',
	    '--fail',
	    help=
	    'Boolean to determine if presentation states and structured reports should be converted to scan failed messages',
	    type=str)
	args = parser.parse_args()
	sDir = args.input
	expDir = args.output

	# Defining input folders
	inDir = sDir + '\\input'
	outDir = sDir + '\\output'

	# Output save folder if only input is defined
	if expDir in (None, ''):
		expDir = mkdtemp()
		print('Randomized results will be saved to: ' + expDir)

	# Failed results mode for presentation states and structured reports
	FAILED_RESULTS = False
	if args.fail != None:
		if args.fail.lower() in ('yes', 'true', 't', 'y', '1'):
			FAILED_RESULTS = True
		else:
			FAILED_RESULTS = False

	# Anonymize study and get info needed to anonymize output
	oStudy = []
	for dcm in os.listdir(inDir):
		ds = pd.dcmread(inDir + '\\' + dcm)
		oStudy.append(ds)
	aStudy = renameDCM(oStudy)

	# Get UID mapping information
	uidmap = {}
	for i in range(len(oStudy)):
		if oStudy[i].StudyInstanceUID not in uidmap:
			uidmap[oStudy[i].StudyInstanceUID] = aStudy[i].StudyInstanceUID
		if oStudy[i].SeriesInstanceUID not in uidmap:
			uidmap[oStudy[i].SeriesInstanceUID] = aStudy[i].SeriesInstanceUID
		uidmap[oStudy[i].SOPInstanceUID] = aStudy[i].SOPInstanceUID

	# Check for prior study in input
	pStudy = []
	aStudy2 = []
	pDate = aStudy[0].StudyDate
	for ds in aStudy:
		if ds.StudyDate < pDate:
			pDate = ds.StudyDate
	for ds in aStudy:
		if ds.StudyDate == pDate:
			pStudy.append(ds)
		else:
			aStudy2.append(ds)
	if aStudy2 != []:
		ds = aStudy2[0]
	else:
		ds = aStudy[0]

	# Setup output directory and save randomized input study
	os.mkdir(expDir + '\\input')
	os.mkdir(expDir + '\\output')
	exportDS(aStudy, expDir + '\\input', False)

	# Anonymize output
	oRes = []
	for folder in os.listdir(outDir):
		if os.path.isdir(outDir + '\\' + folder):
			for dcm in os.listdir(outDir + '\\' + folder):
				if '.json' not in dcm:
					oRes.append(pd.dcmread(outDir + '\\' + folder + '\\' +
					                       dcm))
	res = updateRes(oRes, ds, uidmap, FAILED_RESULTS)

	# Setup result modality folders and export randomized results
	resByModality = {}
	for ds in res:
		if ds.Modality not in resByModality:
			resByModality[ds.Modality] = []
		resByModality[ds.Modality].append(ds)
	for modality in resByModality:
		os.mkdir(expDir + '\\output\\' + modality)
		exportDS(resByModality[modality], expDir + '\\output\\' + modality)


###########################################################################################################################


def updateRes(res, ds, uidmap, FAILED_RESULTS):
	"""
	Update an AI result file, including referenced study, series, and SOP instance UIDs
		res		List of result DICOM instances to be updated
		ds		Reference DICOM instance from original study
		uidmap	Dictionary mapping original and anonymized UIDs
	"""
	for n in range(len(res)):
		res[n].PatientName = ds.PatientName
		res[n].PatientID = ds.PatientID
		res[n].AccessionNumber = ds.AccessionNumber
		res[n].StudyInstanceUID = uidmap[res[n].StudyInstanceUID]
		if res[n].SeriesInstanceUID not in uidmap:
			SeriesInstanceUID = res[n].StudyInstanceUID + '.' + str(
			    random.randint(1, 99999))
			uidmap[res[n].SeriesInstanceUID] = SeriesInstanceUID
			res[n].SeriesInstanceUID = SeriesInstanceUID
		else:
			res[n].SeriesInstanceUID = uidmap[res[n].SeriesInstanceUID]
		SOPInstanceUID = res[n].SeriesInstanceUID + '.' + str(n)
		uidmap[res[n].SOPInstanceUID] = SOPInstanceUID
		res[n].SOPInstanceUID = SOPInstanceUID
		res[n].StudyID = ds.StudyID

	### Updating Referenced Study/Series/SOP Instance UIDs ###
	ReferencedStudySequence = pd.tag.Tag(0x8, 0x1110)
	ReferencedSeriesSequence = pd.tag.Tag(0x8, 0x1115)
	ReferencedImageSequence = pd.tag.Tag(0x8, 0x1140)
	ReferencedInstanceSequence = pd.tag.Tag(0x8, 0x114a)
	SourceImageSequence = pd.tag.Tag(0x8, 0x2112)
	RelatedSeriesSequence = pd.tag.Tag(0x8, 0x1250)
	SoftcopyVOILUTSequence = pd.tag.Tag(0x28, 0x3110)
	GraphicAnnotationSequence = pd.tag.Tag(0x70, 0x1)
	DisplayedAreaSelectionSequence = pd.tag.Tag(0x70, 0x5A)
	GraphicObjectSequence = pd.tag.Tag(0x70, 0x9)
	PerFrameFunctionalGroupsSequence = pd.tag.Tag(0x5200, 0x9230)
	CurrentRequestedProcedureEvidenceSequence = pd.tag.Tag(0x40, 0xA375)
	ContentSequence = pd.tag.Tag(0x40, 0xA730)
	ReferencedSOPSequence = pd.tag.Tag(0x8, 0x1199)
	for n in range(len(res)):
		# Referenced Study Sequence
		if ReferencedStudySequence in res[n]:
			for i in range(len(res[n][0x8, 0x1110].value)):
				res[n][0x8, 0x1110][i][0x8, 0x1155].value = uidmap[res[n][
				    0x8, 0x1110][i][0x8, 0x1155].value]
			print('Updated Referenced Study Sequence')

		# Referenced Series Sequence
		if ReferencedSeriesSequence in res[n]:
			for i in range(len(res[n][0x8, 0x1115].value)):
				if ReferencedImageSequence in res[n][0x8, 0x1115][i]:
					for j in range(
					    len(res[n][0x8, 0x1115][i][0x8, 0x1140].value)):
						res[n][0x8, 0x1115][i][0x8, 0x1140][j][
						    0x8, 0x1155].value = uidmap[res[n][0x8, 0x1115][i][
						        0x8, 0x1140][j][0x8, 0x1155].value]
				if ReferencedInstanceSequence in res[n][0x8, 0x1115][i]:
					for j in range(
					    len(res[n][0x8, 0x1115][i][0x8, 0x114a].value)):
						res[n][0x8, 0x1115][i][0x8, 0x114a][j][
						    0x8, 0x1155].value = uidmap[res[n][0x8, 0x1115][i][
						        0x8, 0x114a][j][0x8, 0x1155].value]
				res[n][0x8, 0x1115][i][0x20, 0xE].value = uidmap[res[n][
				    0x8, 0x1115][i][0x20, 0xE].value]
			print('Updated Referenced Series Sequence')

		# Source Image Sequence
		if SourceImageSequence in res[n]:
			for i in range(len(res[n][0x8, 0x2112].value)):
				res[n][0x8, 0x2112][i][0x8, 0x1155].value = uidmap[res[n][
				    0x8, 0x2112][i][0x8, 0x1155].value]
			print('Updated Source Image Sequence')

		# Related Series Sequence
		if RelatedSeriesSequence in res[n]:
			for i in range(len(res[n][0x8, 0x1250].value)):
				res[n][0x8, 0x1250][i][0x20, 0xD].value = uidmap[res[n][
				    0x8, 0x1250][i][0x20, 0xD].value]
				res[n][0x8, 0x1250][i][0x20, 0xE].value = uidmap[res[n][
				    0x8, 0x1250][i][0x20, 0xE].value]
			print('Updated Related Series Sequence')

		# Softcopy VOI LUT Sequence
		if SoftcopyVOILUTSequence in res[n]:
			for i in range(len(res[n][0x28, 0x3110].value)):
				if ReferencedImageSequence in res[n][0x28, 0x3110][i]:
					for j in range(
					    len(res[n][0x28, 0x3110][i][0x8, 0x1140].value)):
						res[n][0x28, 0x3110][i][0x8, 0x1140][j][
						    0x8, 0x1155].value = uidmap[res[n][
						        0x28, 0x3110][i][0x8, 0x1140][j][0x8,
						                                         0x1155].value]
					print('Updated Softcopy VOI LUT Sequence')

		# Graphic Annotation Sequence
		if GraphicAnnotationSequence in res[n]:
			for i in range(len(res[n][0x70, 0x1].value)):
				for j in range(len(res[n][0x70, 0x1][i][0x8, 0x1140].value)):
					res[n][0x70,
					       0x1][i][0x8, 0x1140][j][0x8, 0x1155].value = uidmap[
					           res[n][0x70, 0x1][i][0x8,
					                                0x1140][j][0x8,
					                                           0x1155].value]
				print('Updated Graphic Annotation Sequence')
				if FAILED_RESULTS:
					for j in range(len(res[n][0x70, 0x1][i][0x70, 0x8].value)):
						res[n][0x70, 0x1][i][0x70, 0x8][j][
						    0x70, 0x6].value = 'Failed to scan the study'
					if ReferencedImageSequence in res[n][0x70, 0x1][i]:
						del res[n][0x70, 0x1][i][0x8, 0x1140]
					if GraphicObjectSequence in res[n][0x70, 0x1][i]:
						del res[n][0x70, 0x1][i][0x70, 0x9]
					print('Updated Unformatted Text Value to Failed')

		# Displayed Area Selection Sequence
		if DisplayedAreaSelectionSequence in res[n]:
			for i in range(len(res[n][0x70, 0x5A].value)):
				if ReferencedImageSequence in res[n][0x70, 0x5A][i]:
					for j in range(
					    len(res[n][0x70, 0x5A][i][0x8, 0x1140].value)):
						res[n][0x70, 0x5A][i][0x8, 0x1140][j][
						    0x8, 0x1155].value = uidmap[res[n][0x70, 0x5A][i][
						        0x8, 0x1140][j][0x8, 0x1155].value]
					print('Updated Display Area Selection Sequence')

		# Per Frame Functional Groups Sequence
		if PerFrameFunctionalGroupsSequence in res[n]:
			for i in range(len(res[n][0x5200, 0x9230].value)):
				for j in range(
				    len(res[n][0x5200, 0x9230][i][0x8, 0x9124].value)):
					for k in range(
					    len(res[n][0x5200,
					               0x9230][i][0x8, 0x9124][j][0x8,
					                                          0x2112].value)):
						res[n][0x5200, 0x9230][i][0x8, 0x9124][j][
						    0x8, 0x2112][k][0x8, 0x1155].value = uidmap[res[n][
						        0x5200,
						        0x9230][i][0x8,
						                   0x9124][j][0x8,
						                              0x2112][k][0x8,
						                                         0x1155].value]
			print('Updated Per Frame Functional Groups Sequence')

		# Current Requested Procedure Evidence Sequence
		if CurrentRequestedProcedureEvidenceSequence in res[n]:
			for i in range(len(res[n][0x40, 0xA375].value)):
				res[n][0x40, 0xA375][i][0x20, 0xD].value = uidmap[res[n][
				    0x40, 0xA375][i][0x20, 0xD].value]
				for j in range(len(res[n][0x40, 0xA375][i][0x8,
				                                           0x1115].value)):
					res[n][0x40, 0xA375][i][0x8, 0x1115][j][
					    0x20, 0xE].value = uidmap[res[n][0x40, 0xA375][i][
					        0x8, 0x1115][j][0x20, 0xE].value]
					for k in range(
					    len(res[n][0x40, 0xA375][i][0x8,
					                                0x1115][j][0x8,
					                                           0x1199].value)):
						res[n][0x40, 0xA375][i][0x8, 0x1115][j][
						    0x8, 0x1199][k][0x8, 0x1155].value = uidmap[res[n][
						        0x40,
						        0xA375][i][0x8,
						                   0x1115][j][0x8,
						                              0x1199][k][0x8,
						                                         0x1155].value]
			print('Updated Current Requested Procedure Evidence Sequence')

		# Content Sequence
		if ContentSequence in res[n]:
			for i in range(len(res[n][0x40, 0xA730].value)):
				if ContentSequence in res[n][0x40, 0xA730][i]:
					for j in range(
					    len(res[n][0x40, 0xA730][i][0x40, 0xA730].value)):
						if ReferencedSOPSequence in res[n][0x40, 0xA730][i][
						    0x40, 0xA730][j]:
							for k in range(
							    len(res[n][0x40, 0xA730][i][0x40, 0xA730][j][
							        0x8, 0x1199].value)):
								res[n][0x40, 0xA730][i][0x40, 0xA730][j][
								    0x8,
								    0x1199][k][0x8, 0x1155].value = uidmap[
								        res[n][0x40, 0xA730][i][0x40, 0xA730]
								        [j][0x8, 0x1199][k][0x8, 0x1155].value]
							print('Updated Content Sequence')
				if FAILED_RESULTS:
					if res[n][0x40, 0xA730][i][0x40, 0xA043][0][
					    0x8, 0x104].value == 'Summary of Detections':
						res[n][0x40,
						       0xA730][i][0x40,
						                  0xA168][0][0x8,
						                             0x100].value = '111224'
						res[n][0x40,
						       0xA730][i][0x40,
						                  0xA168][0][0x8,
						                             0x104].value = 'Failed'
						print('Updated Code Sequence to Failed')

	return res


def renameDCM(inDir, patientName=None):
	"""
	Change the Patient Name, IDs, and dates of a DICOM file, directory of DICOM files, pydicom dataset, or list of datasets
		Returns output as a list
	"""
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
		try:
			modality = ds[0].Modality
		except:
			modality = None
		try:
			gender = ds[0].PatientSex
		except:
			gender = None

		if gender == 'F' or modality == 'MG':
			patientName = names.get_last_name() + '^' + names.get_first_name(
			    'female')
		elif gender == 'M':
			patientName = names.get_last_name() + '^' + names.get_first_name(
			    'male')
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


def exportDS(ds, outDir=None, openDir=True):
	"""
	Export a list if pydicom datasets to a folder, naming each file by modality
		Creates and returns a temporary directory to save to if not given one
		Opens directory folder in file explorer by default
	"""
	if outDir == None:
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


if __name__ == '__main__':
	main()