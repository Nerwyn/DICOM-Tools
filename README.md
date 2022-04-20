# DICOM Tools

Collection of DICOM tools written in Python

Were written for a previous job which required a lot of manipulation of DICOM data. All company specific information has been removed to make these tools generic release.

## DCMLibrary

Collection of Python functions for DICOM data manipulation. Includes implementations of QIDO, WADO, STOW, and C-STORE using pydicom and pynetdicom. Also has some DICOM data viewing, manipulating, and anonymizing functions.

## AIDataRandomize

Tool used to anonymize a study and it's AI results. AI results being DICOM files which contain references to the original study, such as SEG, PR, SR, and SC. Folder structure should be as follows:

```
inDir
|───input
|	original DICOM images (CT, CR, DX, MR, etc)
|───output
	|───SEG
	|	SEG modality results
	|───PR
	|	PR modality results
	|───SR
	|	SR modality results
	|───SC
	|	SC modality results

```

## DCMListener

A simple DICOM receiver server for both STOW-RS and C-STORE. Uses default ports 8080 for STOW-RS and 104 for C-STORE. Note that if you are using less common storage presentation contexts, you must modify the code and add them to the list at line 165, otherwise the C-STORE listener will throw an error.
