#!/usr/bin/python
#
#
#
__author__ = 'ccapriotti'

"""
Last modified: 2016-04-12
Author: ccapriotti
Original location: https://github.com/ccapriotti/vmware_VM_image_backup


This is the python version of the ESXi VM image backup program, originally written as a 
bash script.

WORK IN PROGRESS ! WORK IN PROGRESS ! WORK IN PROGRESS ! 

CODE NOT FINISHED ! CODE NOT FINISHED ! CODE NOT FINISHED !


INSTRUCTIONS, DISCLAIMER AND LICENSE.

FAIR PLAY: if you use the code, a significant part of it, or base your new code on
it, mention the author. 

As usual, this software is provided AS IS. Use at your own risk.

With that said, the bash version of the software has been used in production for over two
years without problems. The python version, while identical in functionality, is new code
and must be treated as alpha.

Like the original, it is meant to run on a (Linux) server with access to both, the source 
image and the target destination, available as a mount point on its file system.
From there rsync is used to copy the contents.

A future alternative, using SCP to copy the VM images hosted on ESXi local disks, will be 
explored on OTHER possible versions.


# Triggered by cron, this script will interact with VMWare ESXi hosts
# pausing VMs, and allowing their images to be copied from this host to
# a pre-mounted share.
#

In order to accomplish this ssh communication, hosts must allow for passwordless 
login. On the ESXi side this is typically ROOT passwordless login. 

#
#  This script will use five input paramenters:
#
#  -c=configfile.txt, which is expected to be a text file
#  with the following structure:
#  VM ID, VM name and VM directory per line, comma separated. 
#  This is a file derived from the command vim-cmd vmsvc/getallvms
#  executed on an esxi.
#  Check sample file on on github.
#
#  
#  -s=x
# 
#  expects x to be either 0 or 1. Zero pauses all servers listed on 
#  the configuration file, suspending them  at once, while 1 will
#  suspende them sequentialy, one at the time, just before the backup 
#  command is issued.
#
#   -h=host
#
#   Is the esxi host who will receive the ssh remote commands.
#   This host must be prepared to receive passwordless 
#   commands. IP address or resolvable host name.
#
#   -f=/path_1/on/filesystem
#   
#   FROM this location (source); Original VM image files.
#
#	-t=/path_2/on/filesystem/
#
#	TO -> Target location where files will be saved by rsync.
#	Make sure it ends with a trailing forward slash.
#	rsync creates subfolders in case they do not exist.
#
#  OPTIONALS:
#    
#     -i=prescript.ext
#     -o=postscript.ext
#    
#     for running a pre operation script and a post operation SHELL script
	  executed as /bin/bash [script location]	
#
#	
#  If the VM is powered on, the script calls the "suspend power" command via ssh 
#  on the esxi, and after it returns succesfully, copies the contents of 
#  the VM's folder directly from the source, using rsync -Wav,  
#  to the target defined as a parameter. If the VM power is off or suspended, the copy
   is executed also.
   
   Should there be a problem copying the VM, the systems tries to copy the next image.
   If a problem suspending the VM happens, the backup operation is aborted, all the
   VMs listed on the configuration file are resumed, and the lock file is NOT deleted.
   If there is a problem resuming the VMs, this is logged to the log file.
   
#
#  Log files are created, using the name of the configuration file as
#  part of it, in order to create diferentiated logs per instance. 
#  Multiple instances are allowed, but they do not check if a certain VM is already
   being copied.
#
#  A lock file is created, per instance, under /var/lock/uws_rsy_datastore/
#  using the name of the config file, to avoid double triggering of the backup.
#
#  Check /var/log/uws_rsy_datastore for log files.
#
"""

import sys
import os
import time
import logging
#import csv


delete.lock.file = FALSE

## Saves the current stdout, in case we need to change it. 
old_stdout = sys.stdout

## Exits the software, re-establishing the initial environment. Regards specially
#	stdout
#

def cleanexit(exitcode):
	std.out = old_sdtout
	log_file.close()
	lock_file.close()
	if delete.lock.file and os.path.isfile(LOCKBASE) :
		os.remove(LOCKBASE)
	sys.exit(exitcode)
	

cmdargs = str(sys.argv)

if len(sys.argv) == 0:
    print
    print 'Paramers expected:'
    print 
    print '-c=config_file.ext expects the complete file path' 
    print 
    print '-s=x, defines how the VMs are paused: 0 pausing them all before backup,' 
    print 'and 1 pausing one at a time, before issuing the backup command'
    print
    print '-h=host, the name/address of the esxi host'
    print
    print '-f=/path_1/to/folder is the source path'
    print
    print '-t=/path_2/to/folder is the local path where files will be saved.'
    print
    print 'OPTIONALS:'
    print
    print '-i=prescript.ext'
    print '-o=postscript.ext'
    print
    print 'for running a pre operation script and a post operation script'
    print
    print 'Check /var/log/uws_rsy_datastore for log files'
    print
    cleanexit(2)



for i in xrange(len(sys.argv)):
	arg.content=str(sys.argv[i])[3:len(str(sys.argv[i])) +1]
	arg.option=str(sys.argv[i])[0:3]
	if arg.option == "-c=" :
		CONFIG=arg.content
		if arg.content.len() == 0 or not os.path.isfile(CONFIG):
			print "BAD PARAMETER -c= : Specified file path is invalid or file does not exist: " + CONFIG
			cleanexit(4)
	elif arg.option == "-h=":
		ESXI=arg.content
	elif arg.option == "-f=":
		FROMPATH=arg.content
	elif arg.option == "-t=":
		TARGETFOLDER=arg.content
	elif arg.option == "-i=":
		PRESCRIPT=arg.content
	elif arg.option == "-o=":
		POSCRIPT=arg.content


# extract the name of the config file, w/o path or extension
#

LOCKBASE=os.path.basename(CONFIG).rsplit(".",1)[0]

if not os.path.exists("/var/log/uws_rsy_datastore") :		# if uws_rsy_datastore does not exist
	if not os.makedirs("/var/log/uws_rsy_datastore"):		# if creating uws_rsy_datastore fails
		LOGFILE="/var/log/uws_rsy_datastore/uws_backup." + LOCKBASE+ "_"  + time.strftime("%Y%m%d%H%M") + ".log"
	else :													# if creating uws_rsy_datastore is OK
		LOGFILE="/var/log/uws_rsy_datastore/uws_backup/"+LOCKBASE+"_"+ time.strftime("%Y%m%d%H%M") + ".log"	   
elif not os.path.isdir("/var/log/uws_rsy_datastore") :			# if by accident uws_rsy_datastore is a file
	LOGFILE="/var/log/uws_rsy_datastore/uws_backup." + LOCKBASE + "_" + time.strftime("%Y%m%d%H%M") + ".log"
	print "Warining !!! /var/log/uws_rsy_datastore if not a directory ! Cannot save log files ! Will continue anyway. Check /var/log for strange entries"
else :														# if all is normal
	LOGFILE="/var/log/uws_rsy_datastore/uws_backup/" + LOCKBASE +  "_"+ time.strftime("%Y%m%d%H%M") + ".log"




##  To be implemented - alternative command line option permitting to
#	choose from output directly to syslog, screen or redirect sdtout to a custom file.
##	Refer and adapt the following code	
"""
old_stdout = sys.stdout

log_file = open("message.log","w")

sys.stdout = log_file

print "this will be written to message.log"

sys.stdout = old_stdout

log_file.close()

"""

log_file = open("LOGFILE","w")
sys.stdout = log_file

##Registers when the script was called
#
print time.strftime("%Y.%m.%d.%H:%M:%S") + " - " + sys.argv[0] + " invoked." 


## Sanity check on input parameters
#
#

if TARGETFOLDER[0:1] != "/" :
   print "BAD PARAMETER: malformed target path: " + TARGETFOLDER 
   cleanexit(4)

if TARGETFOLDER[:-1] != "/":
   TARGETFOLDER = TARGETFOLDE + "/"

if FROMPATH[0:1] != "/" :
   print "BAD PARAMETER: malformed source path: " + FROMPATH 
   cleanexit( 4)

if FROMPATH[:-1] != "/":
   FROMPATH = FROMPATH + "/" 

source = FROMPATH

if len(ESXI) == 0 :
   print 'Host name/address defined on -h= cannot be empty' 
   cleanexit(2)

if len(CONFIG) == 0 :
   print 'Configuration file name cannot be empty.' 
   print 'Make sure to use the option -c=config_file.ext' 
   cleanexit(2)


if len(SUSPEND) == 0 :
   print 'SUSPEND parameter requires a value to be set.' 
   print 'Make sure you use the option -s=0 or -s=1' 
   print
   cleanexit(8)

if SUSPEND != 0 and SUSPEND != 1 :
   print 'Suspend parameter -s= expects values 0 or 1.' 
   print
   cleanexit(10)


## Real work starts here
#	so we initialize the lock file
#


if not os.path.exists("/var/lock/uws_rsy_datastore"):		# if folder does not exist
	if not os.makedirs("/var/lock/uws_rsy_datastore"):		# if creating it fails
		print time.strftime("%Y.%m.%d.%H:%M:%S") + " - ERROR. cannot create lock folder /var/lock/uws_rsy_datastore. Exiting."
		cleanexit(6)
		
LOCKBASE = "/var/lock/uws_rsy_datastore/" + LOCKBASE + ".lock"
if os.path.isfile(LOCKBASE) : 
   print time.strftime("%Y.%m.%d.%H:%M:%S") + " - ERROR. Lock file present for backup set " + CONFIG
   cleanexit(6)
else :
   lock_file = open(LOCKBASE,"w")
   
## Run Pre script if file exists - calls shell

if os.path.isfile(PRESCRIPT) :
   subprocess.call(PRESCRIPT, shell=True)
else :
   print time.strftime("%Y.%m.%d.%H:%M:%S") + " - WARNING: pre script invalid or empty: " + PRESCRIPT + ". Processing will continue anyway."


# loads contents of the configuration file into a 2D matrix
# ignoring lines preceeded by "#"
# contents will be:
# [vm code, folder name, vm name, power status]


curent.line = ""
vm.individual=[]
vmdata2d=[]
config.file = open(CONFIG,r)


for current.line in config.file:
	current.line = current.line.rstrip()
	current.line = current.line.lstrip()
	if len(current.line) > 0 and current.line[0:1] != "#" :
		vm.individual.append() = current.line.strip(",")
		vm.individual.append() = "un"						## assigns UN to the power status, for "UNknown"
		vmdata2d.append() = vm.individual 
		#assigns values to dictionary
		
config.file.close()

int = 0
for curent.vm in vmdata2d :
	vmid=curent.vm[0]
	# pwr_read =os.system("/bin/bash/ssh", " root@$ESXI  vim-cmd vmsvc/power.getstate " + vmid)
	pwr_read = subprocess.call("ssh root@" + ESXI + " \'vim-cmd vmsvc/power.getstate " + vmid + " \`", shell=True)
	pwr_read = pwr_read.lower()
	vmdata2d[int][3] = pwr_read[0:2]
	#print ${vname[$int]} ${vmpwrstate[$int]} ${vmcode[$int]}
	int = int + 1

if int == 0 : 
   print time.strftime("%Y.%m.%d.%H:%M:%S") + " - no VMs to process. Check configuration file."
   #rm -f /var/lock/uws_rsy_datastore/$LOCKBASE.lock
   delete.lock.file = TRUE
   cleanexit( 0)

## 
#
#   If batch-suspend was defined (-s=0 used), then suspend all VMs.
#   If problems found, try to resume all VMs and cleanexit(), keeping the lock file.
#
#



int = 0
if SUSPEND == 0 :
   print time.strftime("%Y.%m.%d.%H:%M:%S") + " - Batch suspending servers."
   for curent.vm in vmdata2d :
      vmid=curent.vm[0]
      dir=curent.vm[1]
      vmname=curent.vm[2]
      pwstat = curent.vm[3]
      print time.strftime("%Y.%m.%d.%H:%M:%S") + " - Suspending " + vmname + vmid   
      if pwstat == "on" :
		suspend_reult=subprocess.call("ssh root@" + ESXI + " \'vim-cmd vmsvc/power.suspend  " + vmid + " \'", shell=True)
		# ssh root@$ESXI "vim-cmd vmsvc/power.suspend $vmid" 
		if suspend_result != 0 :				## if suspend VM fails, abort operation.
			print time.strftime("%Y.%m.%d.%H:%M:%S") + " - VM " + vmdata2d[int][2] + " failed to be suspended. Aborting operation."
			int = 0 
	        for vmid in vmdata2d :
	            vmid=vmdata2d[int][0]
	    	    print time.strftime("%Y.%m.%d.%H:%M:%S") + " - Resuming " + vmdata2d[int][2] + vmid   
			    resume_state = subprocess.call("ssh root@" + ESXI + " \'vim-cmd vmsvc/power.on " + vmid + " \`", shell=True)
        	    if resume_state != 0 :
                    print time.strftime("%Y.%m.%d.%H:%M:%S") + " - ERROR " resume_state + "resuming VM " + vmdata2d[int][2] + vmid  
	    	cleanexit( 255)
      else :
         print time.strftime("%Y.%m.%d.%H:%M:%S") + " - Already suspended - " + vmdata2d[int][2] + vmid



## start copying files. Pauses VMs if -s=1 was defined on command line

int = 0
for curent.vm in vmdata2d :
	vmid=curent.vm[0]
	dir=curent.vm[1]
	vmname=curent.vm[2]
	vmpwrstate=curent.vm[3]
   print " " 
   print time.strftime("%Y.%m.%d.%H:%M:%S") + " - Starting to process      " + vmname + "  ---------->>>"  
   suspend_result=0

   if SUSPEND == 1 and vmpwrstate == "on" :
         #powerstate=1
         print time.strftime("%Y.%m.%d.%H:%M:%S") + " - Suspending " + vmname + " " + vmid   
         suspend_result=subprocess.call("ssh root@" + ESXI + " \'vim-cmd vmsvc/power.suspend  " + vmid + " \'", shell=True) 

   if suspend_result == 0 :
      print time.strftime("%Y.%m.%d.%H:%M:%S") + " - VM " + vmname + " suspended. Starting copy." 
      #rsync -Wav --exclude=*.log --exclude=*.vswp --exclude=".*" --exclude=*.vmss --exclude=*.hlog "$source$dir" "$TARGETFOLDER" 
      copy.result = subprocess.call("rsync -Wav " + source + dir + TARGETFOLDER, shell=True)  
      if copy.result !=  0 :
         print time.strftime("%Y.%m.%d.%H:%M:%S") + " ERROR " + copy.result + " copying VM files for " + vmname
      else:
         print time.strftime("%Y.%m.%d.%H:%M:%S") + " - Backup finished. " + vmname + " " +vmid  

      if SUSPEND == 1 and vmpwrstate == "on" :
         print time.strftime("%Y.%m.%d.%H:%M:%S") + " - Resuming VM " + vmname + " " +vmid   
         resume.result = subprocess.call("ssh root@" + ESXI + " \'vim-cmd vmsvc/power.on " + " " + vmid + "\'"
         if resume.result !=  0 :
            print time.strftime("%Y.%m.%d.%H:%M:%S") + " - ERROR " + resume.result + " resuming VM " + vmname + " " +vmid  
         
      print time.strftime("%Y.%m.%d.%H:%M:%S") + " - End processing files for " + vmname + " " +vmid + " ----------<<<"
   else:
      print time.strftime("%Y.%m.%d.%H:%M:%S") + " - Backup could not be done. ERROR suspending power on VM " + vmname + " " +vmid  


### 
#  If all VMs were batch-suspended, 
#  we resume them all now.
#

OPRESULT = 0
if SUSPEND == 0 :
   for curent.vm in vmdata2d : 
    	vmid=curent.vm[0]
	    dir=curent.vm[1]
		vmname=curent.vm[2]
      	if curent.vm[3] = "on" :
        	print time.strftime("%Y.%m.%d.%H:%M:%S") + " - Resuming VM " + vmname + " " +vmid  
         	#ssh root@$ESXI "vim-cmd vmsvc/power.on $vmid" 
         	resume.result = subprocess.call("ssh root@" + ESXI + " \'vim-cmd vmsvc/power.on " + " " + vmid + "\'", shell=True)
         	if resume.result != 0 :
            	print time.strftime("%Y.%m.%d.%H:%M:%S") + " - ERROR " + resume.result + "resuming VM " + vmname + " " +vmid 
            	OPRESULT = OPRESULT +1 
		else:
	    	OPRESULT = OPRESULT +1 
      

if OPRESULT == 0  and SUSPEND == 1 :
	delete.lock.file = TRUE
   

if os.path.isfile(POSCRIPT) :
   subprocess.call(POSCRIPT, shell=True)
else:
   print time.strftime("%Y.%m.%d.%H:%M:%S") + " - WARNING: post script invalid or empty: " + POSCRIPT + ". Processing will continue anyway."
   cleanexit(0)


cleanexit(255)

