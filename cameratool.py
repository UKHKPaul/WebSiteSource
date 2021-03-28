### IDEADS to do
###
###
### updated to use gphoto2 for the listing and the file getting due issues with some cameras
### still using ptpcam for camera identification and resetting  - to be fixed in next version



import pexpect
import os
from time import strftime,sleep

from pathlib import Path

from ctypes import *

from uithread import uiThread 

import sys


backgroundColour =0x0008

systemShutdown = False #used to allow buttons to abort any action and exit
rebootNotShutdown 	= False

class cameraCounts(object):
	def __init__(self,extension,count):
		self.extension = extension
		self.count = count

	def __rep__(self):
		return '<%s %s %d>' %(type(self).__name__,self.extension, self.count)

	def incrementCount(self):
		self.count +=1


class cameraItem(object):
	typeCount=0
	fileTypes =[]
	def __init__(self,handlernum,filename,fileSize,folder):
		self.handlerNum   		= handlernum
		self.filename 			= filename
		self.fileSize 			= fileSize
		self.folder				= folder
		self.fileAlreadyExists 	= False
		self.fileType			= filename[-3:]


	def updateTypes(self):
		# See if the filetype already exists

		found = False
		for fileType in cameraItem.fileTypes:
			if(fileType.extension == self.fileType):
				fileType.incrementCount()
				found = True;
		if (found == False):
			newFileType = cameraCounts (self.fileType,1)
			cameraItem.fileTypes.append(newFileType)
			cameraItem.typeCount +=1
			print("new extension '{0}' total types {1}".format(self.fileType,cameraItem.typeCount))

	def validate(self):
		valid = False
		if(self.fileType=='MOV'):
			print ("handler '{0}' filename '{1}' size '{2}'".format(self.handlerNum,self.filename,self.fileSize))
		try:
			if(	(self.filename[8]=='.')	and
				(int(self.fileSize)>0)):
				valid= True
		except :
			#just in case any are out of range errors
			valid = False
		return (valid)


	def __rep__(self):
		return '<%s %s %s>' %(type(self).__name__,self.filename, self.handlerNum)


	@staticmethod
	def resetType():
		cameraItem.typeCount =0
		cameraItem.fileTypes =[]

	@staticmethod
	def getCounts():
		for fileType in cameraItem.fileTypes:
			print("Extension {0} count {1}".format(fileType.extension,fileType.count))




def isNotWhiteSpace (checkCharacter):
	if( (checkCharacter <=" ")):  #should get space, tab and newlines
		return (False)
	else:
		return (True)


def getParam (sourceString,paramNumber):
	foundStart = False
	foundParamCount =0
	startPos =0
	endPos =0
	checkingPos =0

	#print ("Checking {0}".format(sourceString))

	while((foundStart ==False) and (len(sourceString)>checkingPos)):
		if(isNotWhiteSpace(sourceString[checkingPos])):
			foundParamCount +=1
			#print("Parameter {0} starts at {1}".format(foundParamCount,checkingPos))
			if(foundParamCount == paramNumber):
				#found the one we need
				startPos = checkingPos
				foundStart = True
				#print("Found start at {0}".format(startPos))
			else:
				#skip this parameter
				checkingPos +=1
				while((isNotWhiteSpace(sourceString[checkingPos])==True) and (len(sourceString)>checkingPos)): 
					checkingPos +=1

		else:
			#is whitespace so skip to next char
			checkingPos +=1


	if(foundStart):
		checkingPos =startPos+1
		while((isNotWhiteSpace(sourceString[checkingPos])==True) and (len(sourceString)>checkingPos)): 
			checkingPos +=1
		endPos = checkingPos 

		return (sourceString[startPos:endPos])
	else:
		return("")


def cleanline(nextline):
	cleanedLine =""
	for pos in range (0,len(nextline)):
		if(nextline[pos] < ' '):
			cleanedLine +=" "
		else:
			cleanedLine +=nextline[pos]

	return(cleanedLine)




#main camera class for actions
class cameraTool (object):
	filelisting =[]
	folderlist=[]
	cameraAction =""
	manufacturer = ""
	model =""

	def __init__(self,cameraName):
		self.cameraName   = cameraName
		self.cameraGood   = False
		self.cameraAction = "Not Defined"
		self.manufacturer = ""
		self.model =""


	def __rep__(self):
		return '<%s %s>' %(type(self).__name__,self.cameraName)


	def isConnected (self):
		attached = False
		cameraCheckCommand = 'gphoto2 --summary'
		response =pexpect.spawn(cameraCheckCommand)  
		nextLine = str(response.readline(),'UTF-8')
		self.manufacturer = ""
		self.model =""
		while(nextLine!=""):
			param1 = getParam(nextLine,1)
			param2 = getParam(nextLine,2)

			#print("reset line '{0}'".format(nextLine))
			if( param1 == "Manufacturer:"):
				self.manufacturer = param2
			elif( param1 == "Model:"):
				self.model = param2

			if(self.manufacturer !="" and self.model!=""):
				attached = True
				nextLine=""
				self.cameraGood = True
				self.cameraName = "{0}: {1}".format(self.manufacturer,self.model)
			else:
				nextLine = str(response.readline(),'UTF-8')

		if( not attached):
			self.cameraGood = False
		return (attached)


	def resetcamera(self):
		cameraresetcommand = 'gphoto2 --reset'
		response =pexpect.spawn(cameraresetcommand)  
		sleep(1)


	def changeDirectory(self,directory):
		print ("Current dir '{0}'".format(os.getcwd()))
		os.chdir(directory)
		print ("New dir '{0}'".format(os.getcwd()))



	def getFolders(self):
		global cDrivers
		global backgroundColour
		cDrivers.DrawFilledRectangle(0,65,239,90,backgroundColour)		#overwrite background in case it has already done
		statusDisplay("Getting Folder list","This may take some time",0xFFFF)

		cameraItem.resetType()

		self.abort = False
		#self.resetcamera()
		#sleep(1)
		folderlist=[]

		cameralistcommand = "gphoto2 --list-folders"
		listing =pexpect.spawn(cameralistcommand, timeout=240)    	# 4 minute timeout.  this could be very slow sometimes 
		nextline = str(listing.readline(),'UTF-8')
		nextline =cleanline(nextline)
		self.folderlist=[]
		#print ("Raw line  '{0}'".format(nextline))

		global systemShutdown
		while((nextline!="") and (not systemShutdown )):
			# for Fuji T4 cameras with dual slots, they are named something like:
			#	'/store_10000001/SLOT 1/DCIM/112_FUJI'

			if ("in folder" in nextline) and not ("camera drivers" in nextline):		#ignore the 1st case where it spits out long line with camera driver info
				#it's a line that has a folder name
				startPos =nextline.find(r"'")+1
				endPos = nextline.find(r"'",startPos)
				folderName = nextline[startPos:endPos]

				
				#print ("** found ' at {0} to {1}".format(startPos,endPos))
				print ("** folder is '{0}'".format(folderName))

				statusDisplay("Folder:", folderName,0xFFFF)
				self.folderlist.append(folderName)

			nextline = str(listing.readline(),'UTF-8')
			nextline =cleanline(nextline)

		#cDrivers.DrawFilledRectangle(0,65,239,90,backgroundColour)

		if (systemShutdown ==True):
			statusDisplay("User Aborted","",0xFFFF)	# clear any status 
			cDrivers.ScreenUpdate()
		else:
			if(self.abort == False):     
				print("found {0} folders".format(len(self.folderlist)))
				msgString = "{0:d} Folders".format(len(self.folderlist))
				clearLine(65)
				cDrivers.displayString(120,65,msgString,0xFFFF,backgroundColour,1)
				statusDisplay("","",0xFFFF)	# clear any status display

				cameraItem.getCounts()
				cDrivers.ScreenUpdate()
			else:
				statusDisplay("Error getting folderlist","",0xF800)
				self.cameraGood = False

		return (not (self.abort))
		

	def getlisting(self):

		global cDrivers
		global backgroundColour
		global systemShutdown

		cameraItem.resetType()

		self.abort = False
#		self.resetcamera()
#		sleep(1)

		self.filecount =0
		self.filelisting =[]
		self.dup=0


		for folderToCheck in self.folderlist:
			self.getSingleFolderListing(folderToCheck)

		cDrivers.DrawFilledRectangle(0,65,239,90,backgroundColour)

		if (systemShutdown ==True):
			statusDisplay("User Aborted","",0xFFFF)	# clear any status 
			cDrivers.ScreenUpdate()
		else:
			if(self.abort == False):     
				print("found {0} unique files  (and {1} duplicates)".format(self.filecount,self.dup))
				msgString = "{0:d} Unique Files".format(self.filecount)
				clearLine(65)
				cDrivers.displayString(120,65,msgString,0xFFFF,backgroundColour,1)
				statusDisplay("","",0xFFFF)	# clear any status display

				cameraItem.getCounts()
				cDrivers.ScreenUpdate()
			else:
				statusDisplay("Error getting filelist","",0xF800)
				self.cameraGood = False


	def getSingleFolderListing(self,checkFolder):

		global cDrivers
		global backgroundColour
		global systemShutdown
		cDrivers.DrawFilledRectangle(0,65,239,90,backgroundColour)		#overwrite background in case it has already done
		statusDisplay("Getting Listing",checkFolder,0xFFFF)

		cameralistcommand = "gphoto2 --list-files --no-recurse --folder='{0}'".format(checkFolder)						#'ptpcam -L'
		listing =pexpect.spawn(cameralistcommand, timeout=60)    
		nextline = str(listing.readline(),'UTF-8')
		startCount = self.filecount

		
		while((nextline!="") and (self.filecount <30000) and (systemShutdown == False)):
			if (len(nextline)>1):
				idCode 		= getParam(nextline,1)
				filename 	= getParam(nextline,2)
				filesize 	= getParam(nextline,4)

			# handlernum,filename,fileSize):
				newFile = cameraItem(idCode[1:],filename,filesize,checkFolder)
				if (self.exists(filename)):
					self.dup +=1
				else:   
					#print ("filename '{0}' is ID {1}".format (filename,idCode[1:]))
					if(newFile.validate()):
						#print("Valid")
						self.filelisting.append(newFile)
						self.filecount +=1
						newFile.updateTypes()
					#else:
					#	print("line did not validate   '{0}'".format(nextline))
				if((self.filecount + self.dup) %10 ==0):  #screen update every 10 files (including duplicated)
					self.doUiUpdate()	

					msgString = " {0:5d} ".format(self.filecount + self.dup)

					statusDisplay("Files on camera:", msgString,0xFFFF)

			nextline = str(listing.readline(),'UTF-8')

		print("Found {0} new files in folder {1}".format(self.filecount-startCount,checkFolder))


	def checkExistingFiles(self):
		global cDrivers
		global backgroundColour
		statusDisplay("Checking existing files:","",0xFFFF)

		self.unbackedUpFiles =0

		count =10

		for cameraFile in self.filelisting:
			fullName = destinationPath + r'/'+cameraFile.filename
			if(count >0):
				print("checking '{0}'".format(fullName))
				count = count -1
			else:
				count = 0
			if (Path(fullName).exists()):
				#print("File {0} already exists".format(fullName))
				cameraFile.fileAlreadyExists =True
			else:
				self.unbackedUpFiles +=1

		msgString = "{0} Files to Backup".format(self.unbackedUpFiles)
		clearLine(65)
		cDrivers.displayString(120,65,msgString,0xFFFF,backgroundColour,1)
		statusDisplay("","",0xFFFF)	# clear any status display
		
	def getfiles(self):
		if (self.cameraGood):
			for fileindex in range (0,self.filecount):
				self.getfile(self.filelisting[fileindex].handlerNum,self.filelisting[fileindex].filename)

	def exists(self,newname):
		duplicate = False
		for fileindex in range (0,self.filecount):
			if(self.filelisting[fileindex].filename==newname):
				duplicate = True
				fileindex =self.filecount
		return duplicate

	def checkdups(self):
		dup=0
		if (self.abort == True):
			print ("unable to get any files")
		else:
			for fileindex in range (0,(self.filecount-1)):
				for fileindex2 in range ((fileindex+1),self.filecount):
					if(self.filelisting[fileindex].filename==self.filelisting[fileindex2].filename):
						print("dup {0} <> {1}".format(fileindex,fileindex2))
						dup +=1
			print("total dups = {0}".format(dup)) 

	def getfile(self,handlernum,filename,filesize,checkFolder):
		self.resetcamera()
		getfile_command = "gphoto2 --get-file={0} --no-recurse --folder='{1}'".format(handlernum,checkFolder)		#'ptpcam -g ' + str(handlernum)

		displayString = "{0}".format(filename)
		statusDisplay("Copying File:",displayString,0xFFFF)

		#print ("sending command **  {0}  **".format(getfile_command))

		if(self.cameraGood):
			retry =3
			okay = False
			while ((okay==False) and (retry >0)):
				self.doUiUpdate()
				fileget = pexpect.spawn(getfile_command)
				nextline = str(fileget.readline(),'UTF-8')
				nextline = cleanline(nextline)
				#print("response <---'{0}--->'".format(nextline))

				while(nextline!=""):
					compareline = "Saving file as {0}".format(filename)
                    #print ("'{0}'".format(str(nextline[0:36])))
                    #print ("'{0}'".format(compareline))
					if(compareline in nextline):
						print("Saved Okay")
						okay = True
					elif(" file exists!" in nextline):
						print("File already exists - ignoring")
						okay = True
					elif("ERROR" in nextline):
						print("******************")
						print("ERROR reported from gphoto2")
						okay = False
						while(nextline!=""):
							print(nextline)
							nextline = str(fileget.readline(),'UTF-8')
					#else:
					#	print("no match '{0}'".format(nextline))
					nextline = str(fileget.readline(),'UTF-8')
				if(not okay):
					#print("ERROR copying file '{0}'".format(filename))
					retry -=1
					#print("waiting")
					#sleep(1)
					#something went wrong in the copy
					#can't assume file was okay, so try to delete any reference of it.
					fullName = destinationPath + r'/'+filename
					if( Path(fullName).exists()):
						try:
							print("attempting to delete the file '{0}'".format(fullName))
							os.remove(fullName)
						except:
							print("unable to delete file, may not exist")
					self.resetcamera()
					
					
            
			if(okay==True):
				print("copied file okay '{0}' size from PTP is {1}".format(filename,filesize))
				self.unbackedUpFiles -=1
			else:
				print("Unable to recover")
				self.abort = True
				self.cameraGood = False
		


	def stillOkay(self):
		return (self.cameraGood)



	def prepareToGetFiles(self):
		self.getIndex = 0

	def getNextFile(self):
		Done = False
		while (Done == False):
			#anything left to get
			if (self.getIndex >= len(self.filelisting)):
				Done = True	
			if (self.filelisting[self.getIndex].fileAlreadyExists):
				self.getIndex +=1
			else:
				Done = True

		if (self.getIndex < len(self.filelisting)):
			#still got a file to get

			msgString = "{0} Files to Backup".format(self.unbackedUpFiles)
			clearLine(65)
			cDrivers.displayString(120,65,msgString,0xFFFF,backgroundColour,1)

			self.getfile(	self.filelisting[self.getIndex].handlerNum,
							self.filelisting[self.getIndex].filename,
							self.filelisting[self.getIndex].fileSize,
							self.filelisting[self.getIndex].folder)

			if(self.abort==False):
				self.getIndex+=1

		


	def gotAllFile(self):

		if(self.getIndex >len(self.filelisting)):	#dummy case to just get one file
			return (True)
		else:
			return (False)

	def doUiUpdate(self):
		newAction = uiThread.getTitleOfAction()
		global systemShutdown
		global rebootNotShutdown

		if(newAction != self.cameraAction):
			clearLine(155)
			if (newAction !=""):
				msgString = "CMD: {0} ?".format(newAction)
				# New Action that needs to be displayed
				cDrivers.displayString (120,155,msgString,0xFFE0,0x001F,1)	
			cDrivers.ScreenUpdate()
			self.cameraAction = newAction

		else:
			if(newAction == "Shutdown"):	#already showing the shutdown command
				#check if it is confirmed
				if(uiThread.isConfirmed (newAction)):
					print ("Shutdown requested")
					clearLine(155)
					cDrivers.displayString (120,155,"Shutdown Requested",0xF800,0x001F,1)	
					cDrivers.ScreenUpdate()
					systemShutdown = True
			if(newAction == "Reboot"):	#already showing the reboot command
				#check if it is confirmed
				if(uiThread.isConfirmed (newAction)):
					print ("Reboot requested")
					clearLine(155)
					cDrivers.displayString (120,155,"Reboot Requested",0xF800,0x001F,1)	
					cDrivers.ScreenUpdate()
					systemShutdown = True
					rebootNotShutdown 	= True



def getPossibleStorage():

	possibleDrives=[]
	command = "lsblk"

		
	#print ("sending command **  {0}  **".format(command))
	respose = pexpect.spawn(command)

	nextLine = str(respose.readline(),'UTF-8')

	while(nextLine!=""):
		#print("response '{0}'".format(nextLine))
		drivePath = getParam(nextLine,1)
		if("─sd" in drivePath):
			#worth checking
			startPos = drivePath.find("sd")
			#print("found at {0}".format(startPos))
			drivePath = drivePath[startPos:]
			drivePath = r"/dev/"+drivePath
			possibleDrives.append(drivePath)
			#print("found {0}".format(drivePath))
		
		nextLine = str(respose.readline(),'UTF-8')

	return(possibleDrives)


usbDevicePath=""

def  regularCheck():
	global usbmounted
	global usbDevicePath
	#print("checking for USB")
	if(not usbmounted):
		#first step is to find all the possible drives on the system
		drivesToCheck = getPossibleStorage()
		if(len(drivesToCheck)>0):
			print("Drives to check")
			for drive in drivesToCheck:
				if(not usbmounted):
					try:
						print("checking drive {0}".format(drive))
						#print ("USB Inserted - mounting")
						statusDisplay("New USB Detected","",0xFFE0)
						#mount, unmount, remount should help recover from and invalid disconnects (i.e. removed uncleanly)
						mountCommand 	= "sudo mount -o uid=pi,gid=pi {0} /mnt/usb".format(drive)
						unMountCommand  = "sudo umount {0}".format(drive)
						#print("mount   = {0}".format(mountCommand))
						#print("unmount = {0}".format(unMountCommand))
						os.system(mountCommand)
						sleep(0.5)
						os.system(unMountCommand)
						sleep(0.5)
						os.system(mountCommand)
						sleep(0.5)
						#print ("USB mounted at {0}".format(drive))

						if (Path(destinationPath).exists()):
							print ("Drive {0} has valid storage folder".format(drive))
							usbDevicePath = drive
							usbmounted= True
						else:  #not valid so unmount
							os.system(unMountCommand)
							sleep(0.5)
						
					except:
						print("unable to mount {0} possible unknown (bitlocker type) format".format(drive))
				else:
					#already mounted a valid case so ignore any other tests
					print("Ignore checking {0}".format(drive))

	else:	# it is already mounted
		if (usbDevicePath !="") and (not Path(usbDevicePath).exists()):
			print ("Error USB ejected without clean removal")
			#statusDisplay("USB was removed","",0xF800)
			os.chdir(r'/home/pi')
			usbmounted = False
			os.system("sudo umount {0}".format(usbDevicePath))
			usbDevicePath =""
			sleep(1)
			print ("USB unmounted")



def drawUSB( status):

	xpos = 45
	ypos = 185

	global cDrivers

	if (status ==0):  #not available
		colour = 0xF800   #Red
	elif (status ==2):	#unknown
		colour = 0x0FFE0   #Yellow
	else:			# should be 1 = Good
		colour = 0x07E0   #green
	cDrivers.DrawLineWideAA(xpos,ypos,xpos+40,ypos,colour,4)
	cDrivers.DrawLineWideAA(xpos,ypos,xpos,ypos+25,colour,4)
	cDrivers.DrawLineWideAA(xpos+40,ypos,xpos+40,ypos+25,colour,4)
	cDrivers.DrawLineWideAA(xpos,ypos+25,xpos+40,ypos+25,colour,4)

	cDrivers.DrawLineWideAA(xpos+40,ypos+5,xpos+55,ypos+5,colour,4)
	cDrivers.DrawLineWideAA(xpos+55,ypos+5,xpos+55,ypos+20,colour,4)
	cDrivers.DrawLineWideAA(xpos+40,ypos+20,xpos+55,ypos+20,colour,4)

def drawCamera( status):

	xpos = 140
	ypos = 185

	global cDrivers

	if (status ==0):  #not available
		colour = 0xF800   #Red
	else:
		colour = 0x07E0   #green
	cDrivers.DrawLineWideAA(xpos   ,ypos+5,   xpos+50,ypos+5,   colour,4)
	cDrivers.DrawLineWideAA(xpos   ,ypos+5,   xpos,   ypos+25,colour,4)
	cDrivers.DrawLineWideAA(xpos+50,ypos+5,   xpos+50,ypos+25,colour,4)
	cDrivers.DrawLineWideAA(xpos   ,ypos+25,  xpos+50,ypos+25,colour,4)

	cDrivers.DrawLineWideAA(xpos+20,ypos+5   ,xpos+25,ypos ,colour,4)
	cDrivers.DrawLineWideAA(xpos+25,ypos,     xpos+35,ypos ,colour,4)
	cDrivers.DrawLineWideAA(xpos+35,ypos,     xpos+40,ypos+5,colour,4)

	cDrivers.DrawLineWideAA(xpos+30,ypos+5   ,xpos+20,ypos+10 ,colour,4)
	cDrivers.DrawLineWideAA(xpos+20,ypos+10  ,xpos+20,ypos+20, colour,4)
	cDrivers.DrawLineWideAA(xpos+20,ypos+20  ,xpos+30,ypos+25, colour,4)
	cDrivers.DrawLineWideAA(xpos+30,ypos+5   ,xpos+40,ypos+10 ,colour,4)
	cDrivers.DrawLineWideAA(xpos+40,ypos+10  ,xpos+40,ypos+20, colour,4)
	cDrivers.DrawLineWideAA(xpos+40,ypos+20  ,xpos+30,ypos+25, colour,4)


def drawTempSymbol( status):

	xpos = 120
	ypos = 185

	global cDrivers

	if (status ==1):  # OverTemp
		colour = 0xF800   	# Red
	elif (status ==2):	# getting warm
		colour = 0xFFE0 	# Yellow
	else:
		colour = 0x07E0   	# green
	cDrivers.DrawLineWideAA(xpos-2   ,ypos,   xpos+2,ypos ,   colour,4)
	cDrivers.DrawLineWideAA(xpos-2   ,ypos,   xpos-2, ypos+17,colour,4)
	cDrivers.DrawLineWideAA(xpos+2   ,ypos,   xpos+2, ypos+17,colour,4)
	
	cDrivers.DrawLineWideAA(xpos-2,ypos+17   ,xpos-6,ypos+17 ,colour,4)
	cDrivers.DrawLineWideAA(xpos-6,ypos+17   ,xpos-6,ypos+25, colour,4)
	cDrivers.DrawLineWideAA(xpos-6,ypos+25   ,xpos+6,ypos+25, colour,4)
	cDrivers.DrawLineWideAA(xpos+6,ypos+25   ,xpos+6,ypos+17 ,colour,4)
	cDrivers.DrawLineWideAA(xpos+6,ypos+17   ,xpos+2,ypos+17, colour,4)




def temperature_of_raspberry_pi():
	cpu_temp = os.popen("vcgencmd measure_temp").readline()
	cpu_temp=cpu_temp.replace("temp=", "")
	cpu_temp=cpu_temp.replace("'C\n", "")

	cpu_tempFloat = float(cpu_temp)

	return cpu_tempFloat


			
def statusDisplay(string1,string2,colour):
	global cDrivers

	StatusBackground = 0x0100
	fontHeight = cDrivers.GetDisplayFontHeight()


	oneLineOnly = False
	if (string2 ==""):
		oneLineOnly = True

	ytop    = 120 - fontHeight -4
	ybottom = 120 + fontHeight+4

	cDrivers.DrawFilledRectangle(0,ytop,239,ybottom,StatusBackground)

	if(oneLineOnly):
		cDrivers.displayString(120,120-(int(fontHeight/2)), string1,colour,StatusBackground,1)
	else:
		cDrivers.displayString(120,120-fontHeight,   string1,colour,StatusBackground,1)
		cDrivers.displayString(120,120,              string2,colour,StatusBackground,1)

	cDrivers.ScreenUpdate()

def clearLine (lineTop):
	global cDrivers
	fontHeight = cDrivers.GetDisplayFontHeight()
	ybottom = lineTop + fontHeight

	cDrivers.DrawFilledRectangle(0,lineTop,239,ybottom,backgroundColour)



global cDrivers
global usbmounted

newCameraConnection = cameraTool("Unknown")
cameraAttached = False
gotListing = False
idleCount =0

yBottom =179
destinationPath = r'/mnt/usb/camerabackup'


cDrivers = CDLL(r"/home/pi/cameratool/linux_spi_c2py.so")

usbmounted = False
directorySet = False
gotFolderListing = False
directoryChecked= False
checkedExisting = False
storageOkay = False


if (cDrivers.initSPIHardware()):
	# then send the commands to configure the display
	cDrivers.initCircularDisp()

	# setup the two Input pins 
	cDrivers.setPinForInput(26)			# wired to pin 37
	cDrivers.setPinForInput(16)			# wired to pin 36

	# clear the screen with a full screen solid colour
	cDrivers.clearScreenDirect(backgroundColour)    # this is dark Blue


	uiThread.setupUiMonitor(cDrivers)	# start the button monitoring system

	try:
		#print("starting")
		cDrivers.displayString(120,15,"Camera Backup",0xFFFF,backgroundColour,1)
		cDrivers.displayString(120,220,"V2.2",0xFFFF,backgroundColour,1)
		
		clearLine(40)
		cDrivers.displayString(120,40,"Camera Unknown",0xF800,backgroundColour,1)
		drawCamera(0)
		newCameraConnection.doUiUpdate()
		newCameraConnection.resetcamera()

		#print("before main while")
		while (systemShutdown == False):
			#print("before regular check")
			regularCheck()
			#print("before ui update")
			newCameraConnection.doUiUpdate()

			temperature = temperature_of_raspberry_pi()
			if(temperature >70):		#set to 70 as warning point (where fans should be at max)
				drawTempSymbol (1)
			elif (temperature>60):
				drawTempSymbol (2)
			else:
				drawTempSymbol (0)

			#print("before checking USB")
			if (usbmounted == False):
				drawUSB(0)   # 0 = red BAD
				directorySet = False
				directoryChecked = False
				cDrivers.ScreenUpdate()	
				storageOkay = False				
			else:
				if (directoryChecked==False):
					try:
						drawUSB(2) # 2 = Yellow = Unknown
						cDrivers.ScreenUpdate()	
						directoryChecked = True
						statusDisplay("Checking USB Drive","",0xFFFF)
						if (directorySet == False):
							print("Changing directory")
							newCameraConnection.changeDirectory		(destinationPath)
							print ("Directory set")
							directorySet = True
							drawUSB(1)	# 1 = green good
							statusDisplay("","",0xFFFF)
							cDrivers.ScreenUpdate()	
							storageOkay = True
					except:
						statusDisplay("Missing camerabackup folder","Unable to use drive",0xF800)
						print ("no camerabackup folder on USB")
						directoryChecked = True
						storageOkay = False	

						

			if(cameraAttached==False):	# camera not currently connected
				#print("before checking camera")
				if(newCameraConnection.isConnected()):	# it  is now connected so start the process
					cDrivers.DrawFilledRectangle(0,65,239,yBottom,backgroundColour)
					clearLine(40)
					title = "{0}".format(newCameraConnection.cameraName)
					cDrivers.displayString(120,40,title,0x07E0,backgroundColour,1)
					drawCamera(1)
					cDrivers.ScreenUpdate()
					print("camera Connected")
					cameraAttached = True
					gotFolderListing = False
					gotListing = False
					gotFiles = False
					idleCount =0
					newCameraConnection.resetcamera()

			else:	# it is already connected
				#print("camera already attached")
				if(newCameraConnection.isConnected()==False):	#has been disconnected 
					cDrivers.DrawFilledRectangle(0,65,239,yBottom,backgroundColour)
					clearLine(40)
					cDrivers.displayString(120,40,"Camera Disconnected",0xF800,backgroundColour,1)
					drawCamera(0)
					cDrivers.ScreenUpdate()
					cameraAttached = False
					
				else:		# still attached
					if(not gotFolderListing):
						print("Getting folder listing")
						if(newCameraConnection.getFolders()):
							gotFolderListing = True
						else:
							print("Error getting folder list")
							### probably good to do some clean up when can work out what to clean

					elif( not gotListing ):
						print("getting listing")
						newCameraConnection.getlisting()
						if(newCameraConnection.stillOkay()) :
							print("Got Listing Okay")
							gotListing = True
							gotFiles = False
							checkedExisting = False

							newCameraConnection.prepareToGetFiles()
						else:
							print("Error getting file list")
					else:
						#print("Got listing checking if able to copy")
						if((gotFiles == False) and (usbmounted) and (storageOkay)):
							if (checkedExisting == False):
								newCameraConnection.checkExistingFiles()
								checkedExisting = True

							if (newCameraConnection.unbackedUpFiles>0):
								newCameraConnection.getNextFile()
								if(newCameraConnection.gotAllFile()==True):
									gotFiles = True
							else:
								clearLine(65)
								statusDisplay("All Files Backed Up","",0x07E0)

								gotFiles = True
						else:
							#dummy case really, just for consistency
							sleep(1)

							#print("idle")
							idleCount +=1
							if((usbmounted) and (storageOkay==False)):
								statusDisplay("Missing camerabackup folder","Unable to use drive",0xF800)
							#print("invalid USB")
					

			#sleep(0.05)


	except KeyboardInterrupt:
		print(" - user aborted -")
		print("exiting")

	uiThread.endThread()

#try to unmount cleanly
os.chdir(r'/home/pi')
if (usbDevicePath!=""):
	os.system(r'sudo umount '+usbDevicePath)

if (systemShutdown == True):
	if(rebootNotShutdown == True):
		#print ("Do system Shutdown - DISABLED")
		cDrivers.clearScreenDirect(0x2940)    # dark Yellow  Background
		cDrivers.displayString (120,50, "Reboot Requested",0xFFFF,0xFFFF,1)	
		cDrivers.displayString (120,110,"DO NOT",0xFFFF,0xFFFF,1)	
		cDrivers.displayString (120,140,"REMOVE POWER",0xFFFF,0xFFFF,1)	
		cDrivers.ScreenUpdate()
		os.system(r'sudo reboot now')
		sys.exit(0)

	else:
		#print ("Do system Shutdown - DISABLED")
		cDrivers.clearScreenDirect(0xF800)    # Red Background
		cDrivers.displayString (120,50, "Shutdown Requested",0xFFFF,0xFFFF,1)	
		cDrivers.displayString (120,110,"Wait for 5 seconds",0xFFFF,0xFFFF,1)	
		cDrivers.displayString (120,140,"after screen goes blank",0xFFFF,0xFFFF,1)	
		cDrivers.displayString (120,170,"before removing power",0xFFFF,0xFFFF,1)	
		cDrivers.ScreenUpdate()
		os.system(r'sudo shutdown now')
		sys.exit(0)

