#!/bin/bash
#
# Code by Carlos Capriotti
#
# Hi folks.
# If you plan to use this code somehow, play nice and 
# Mention the author.
#
#
# Triggered by cron, this script will interact with VMWare ESXi hosts
# pausing VMs, and allowing their images to be copied from this host to
# a pre-mounted NFS share.
#
#
#  This script will use five input paramenters:
#
#  -c=configfile.txt, which is expected to be a text file
#  with the following structure:
#  VM ID, VM name and VM directory per line, comma separated. 
#  This is a file derived from the command vim-cmd vmsvc/getallvms
#  executed on an esxi.
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
#     for running a pre operation script and a post operation script
#
#
#	This script assumes source and target are local or NFS paths.
#	
#  If the VM is on, the script calls the "suspend power" command via ssh 
#  on the esxi, and after it returns succesfully, copies the contents of 
#  the VM's folder directly from the source, using rsync -Wav,  
#  to the target defined as a parameter.
#
#
#  Log files are created, using the name of the configuration file as
#  part of it, in order to create diferentiated logs per instance. 
#  Multiple instances are allowed, but they do not check if a certain VM is being copied.
#
#  A lock file is created, per instance, under /var/lock/uws_rsy_datastore/
#  using the name of the config file, to avoid double triggering of the backup.
#
#  Check /var/log/uws_rsy_datastore for log files.
#


if [[ $# -eq 0 ]] ; then
    echo
    echo 'Paramers expected:'
    echo 
    echo '-c=config_file.ext expects the complete file path' 
    echo 
    echo '-s=x, defines how the VMs are paused: 0 pausing them all before backup,' 
    echo 'and 1 pausing one at a time, before issuing the backup command'
    echo
    echo '-h=host, the name/address of the esxi host'
    echo
    echo '-f=/path_1/to/folder is the source path'
    echo
    echo '-t=/path_2/to/folder is the local path where files will be saved.'
    echo
    echo 'OPTIONALS:'
    echo
    echo '-i=prescript.ext'
    echo '-o=postscript.ext'
    echo
    echo 'for running a pre operation script and a post operation script'
    echo
    echo 'Check /var/log/uws_rsy_datastore for log files'
    echo
    exit 2
fi


for i in "$@"
do
case $i in
    -c=*)
    CONFIG="${i#*=}"

    ;;
    -s=*)
    SUSPEND="${i#*=}"
    ;;
    
    -h=*)
    ESXI="${i#*=}"
    ;;
    
    -f=*)
    FROMPATH="${i#*=}"
    ;;
    
    -t=*)
    TARGETFOLDER="${i#*=}"
    ;;
    
    -i=*)
    PRESCRIPT="${i#*=}"
    ;;
    
    -o=*)
    POSCRIPT="${i#*=}"
    ;;
    
    *)
            # unknown option
    ;;
esac
done

if [ ! -s $CONFIG ]  || [ ! -f $CONFIG ]  ; then
   echo "BAD PARAMETER -c= : Specified file path is invalid or file does not exist: $CONFIG "
   exit 4
fi

# extract the name of the config file, w/o path or extension
#

LOCKBASE=$(basename "$CONFIG")
extension="${LOCKBASE##*.}"
LOCKBASE="${LOCKBASE%.*}"

if [ ! -d /var/log/uws_rsy_datastore ]; then
   mkdir -p /var/log/uws_rsy_datastore 
fi

LOGFILE="/var/log/uws_rsy_datastore/uws_backup_$LOCKBASE"
LOGFILE+="_$(date '+%Y%m%d%H%M').log"


echo $(date '+%Y.%m.%d.%H:%M:%S')" - "$0 "invoked." >> $LOGFILE


if [ "${TARGETFOLDER:0:1}" != "/" ]    ; then
   echo "BAD PARAMETER: malformed target path: $TARGETFOLDER " >> $LOGFILE
   exit 4
fi

if [ "${TARGETFOLDER:(-1)}" != "/" ]    ; then
   TARGETFOLDER+="/"
fi

if [ "${FROMPATH:0:1}" != "/" ]    ; then
   echo "BAD PARAMETER: malformed source path: $FROMPATH " >> $LOGFILE
   exit 4
fi

if [ "${FROMPATH:(-1)}" != "/" ]    ; then
   FROMPATH+="/" 
fi

source="$FROMPATH"

if [ -z "$ESXI" ]; then
   echo 'Host name/address defined on -h= cannot be empty' >> $LOGFILE
   exit 2
fi

if [ -z "$CONFIG" ]; then
   echo 'Configuration file name cannot be empty.' >> $LOGFILE
   echo 'Make sure to use the option -c=config_file.ext' >> $LOGFILE
   exit 2
fi

if [ ! -d /var/lock/uws_rsy_datastore ]; then
   mkdir -p /var/lock/uws_rsy_datastore 
fi

if [ -z "$SUSPEND" ]; then
   echo 'SUSPEND parameter requires a value to be set.' >> $LOGFILE
   echo 'Make sure you use the option -s=0 or -s=1' >> $LOGFILE
   echo
   exit 8
fi


if [ ! $SUSPEND -eq 0 ] && [ ! $SUSPEND -eq 1 ]; then
   echo 'Suspend parameter -s= expects values 0 or 1.' >> $LOGFILE
   echo
   exit 10
fi


if [ -f /var/lock/uws_rsy_datastore/$LOCKBASE.lock ]; then
   echo $(date '+%Y.%m.%d.%H:%M:%S') " - ERROR. Lock file present for backup set $CONFIG"  >> $LOGFILE
   exit 6
else
   touch /var/lock/uws_rsy_datastore/$LOCKBASE.lock
fi

if [ -f "$PRESCRIPT" ]; then
   /bin/bash $PRESCRIPT 
else
   echo $(date '+%Y.%m.%d.%H:%M:%S') " - pre script invalid or empty: $PRESCRIPT"  >> $LOGFILE   
fi

clear


# loads contents of the configuration file into memory
# ignoring lines preceeded by "#"

int=0
while IFS=, read vmid vmname dir  
do
   vmid="${vmid#"${vmid%%[![:space:]]*}"}"
   if [[ "${vmid:0:1}" != "#" ]] && [ ! -z $vmid ] ; then
      vmcode[$int]=$vmid
      local[$int]=$dir
      vname[$int]=$vmname
      ((int++))
   fi
   # echo $int $vmid $dir $vmname ${vmcode[$int]} ${local[$int]} ${vname[$int]}
done < $CONFIG

#for ((int=0; int<${#vmcode[@]}; int++))
#do
#   echo $int  ${vmcode[$int]} ${local[$int]} ${vname[$int]}
#done

##
#
#   Reads power state of VMs into memory
#
#

for ((int=0; int<${#vmcode[@]}; int++))
do
   vmid=${vmcode[$int]}
   pwr_read=$(ssh root@$ESXI "vim-cmd vmsvc/power.getstate $vmid")
   vmpwrstate[$int]=${pwr_read:(-2)}
   #echo ${vname[$int]} ${vmpwrstate[$int]} ${vmcode[$int]}
done   


if [ $int -eq 0 ]; then
   echo $(date '+%Y.%m.%d.%H:%M:%S')' - no VMs to process. Check configuration file.' >> $LOGFILE
   rm -f /var/lock/uws_rsy_datastore/$LOCKBASE.lock
   exit 0
fi
   

## 
#
#   If batch-suspend was defined (-s=0 used), then suspend all VMs.
#   If problems found, try to resume all VMs and exit, keeping the lock file.
#
#


if [ $SUSPEND -eq 0 ]; then
   echo  $(date '+%Y.%m.%d.%H:%M:%S')' - Batch suspending servers.' >> $LOGFILE
   for ((int=0; int<${#vmcode[@]}; int++))
   do
      vmid=${vmcode[$int]}
      dir=${local[$int]}
      vmname=${vname[$int]}
      echo  $(date '+%Y.%m.%d.%H:%M:%S')' - Suspending' ${vname[$int]} $vmid   >> $LOGFILE
      if [ ${vmpwrstate[$int]} = "on" ]; then
         suspend_reult=1
         ssh root@$ESXI "vim-cmd vmsvc/power.suspend $vmid" 
         suspend_result=$?
         if [ ! $suspend_result -eq 0 ]; then
            echo $(date '+%Y.%m.%d.%H:%M:%S')' - VM' ${vname[$int]} 'failed to be suspended. Aborting operation.'  >> $LOGFILE
	        for ((int=0; int<${#vmcode[@]}; int++))
	        do
	           echo  $(date '+%Y.%m.%d.%H:%M:%S')' - Resuming' ${vname[$int]} $vmid   >> $LOGFILE
	           ssh root@$ESXI "vim-cmd vmsvc/power.on $vmid" 
               if [ ! $? -eq 0 ] ; then
                  echo  $(date '+%Y.%m.%d.%H:%M:%S')' - ERROR resuming VM' ${vname[$int]} $vmid '- $?'  >> $LOGFILE
	           fi
	        done
	        exit 255
	     fi
      else
         echo  $(date '+%Y.%m.%d.%H:%M:%S')' - Already suspended -' ${vname[$int]} $vmid   >> $LOGFILE
      fi
   done
fi	     


## start copying files. Pauses VMs if -s=1 was defined on command line


for ((int=0; int<${#vmcode[@]}; int++))
do 
   dir=${local[$int]}
   vmid=${vmcode[$int]}
   echo " " >> $LOGFILE
   echo $(date '+%Y.%m.%d.%H:%M:%S')' - Starting to process      ' ${vname[$int]} '  ---------->>>'  >> $LOGFILE
   #powerstate=0
   suspend_result=0
   #pwr_read=$(ssh root@$ESXI "vim-cmd vmsvc/power.getstate $vmid")
   #pwr_read=${pwr_read:(-2)}


   if [ $SUSPEND -eq 1 ] ; then 
      if [ ${vmpwrstate[$int]} = "on" ]  ; then
         #powerstate=1
         echo  $(date '+%Y.%m.%d.%H:%M:%S')' - Suspending '  ${vname[$int]} $vmid   >> $LOGFILE
         ssh root@$ESXI "vim-cmd vmsvc/power.suspend $vmid" 
         suspend_result=$?
      fi
   fi

   if [ $suspend_result -eq 0 ] ; then
      echo $(date '+%Y.%m.%d.%H:%M:%S')' - VM' ${vname[$int]} 'suspended. Starting copy.'  >> $LOGFILE
      #rsync -Wav --exclude=*.log --exclude=*.vswp --exclude=".*" --exclude=*.vmss --exclude=*.hlog "$source$dir" "$TARGETFOLDER" 
      rsync -Wav  "$source$dir" "$TARGETFOLDER"  >> $LOGFILE
      if [ ! $? -eq 0 ] ; then
         echo  $(date '+%Y.%m.%d.%H:%M:%S')' ERROR copying VM files - ' $?  >> $LOGFILE
      else
         echo $(date '+%Y.%m.%d.%H:%M:%S')' - Backup finished. ' ${vname[$int]} $vmid.  >> $LOGFILE
      fi

      if [ $SUSPEND -eq 1 ] && [ ${vmpwrstate[$int]} = "on" ] ; then
         echo $(date '+%Y.%m.%d.%H:%M:%S')' - Resuming VM ' ${vname[$int]} $vmid.  >> $LOGFILE
         ssh root@$ESXI "vim-cmd vmsvc/power.on $vmid" 
         if [ ! $? -eq 0 ] ; then
            echo  $(date '+%Y.%m.%d.%H:%M:%S')' - ERROR resuming VM ' ${vname[$int]} $vmid ' - $?'  >> $LOGFILE
         fi
      fi
      
      echo  $(date '+%Y.%m.%d.%H:%M:%S')' - End processing files for ' ${vname[$int]} $vmid '----------<<<'  >> $LOGFILE
   else
      echo  $(date '+%Y.%m.%d.%H:%M:%S')' - Backup could not be done. ERROR suspending power on VM ' ${vname[$int]} $vmid  >> $LOGFILE
   fi
done


### 
#  If all VMs were batch-suspended, 
#  we resume them all now.
#

OPRESULT=0

if [ $SUSPEND -eq 0 ] ; then
   OPRESULT=${#vmcode[@]}
   for ((int=0; int<${#vmcode[@]}; int++))
   do 
      vmid=${vmcode[$int]}
      dir=${local[$int]}
      vmname=${vname[$int]}
      if [ ${vmpwrstate[$int]} = "on" ] ; then
         echo $(date '+%Y.%m.%d.%H:%M:%S')' - Resuming VM ' ${vname[$int]} $vmid.  >> $LOGFILE
         ssh root@$ESXI "vim-cmd vmsvc/power.on $vmid" 
         if [ ! $? -eq 0 ] ; then
            echo  $(date '+%Y.%m.%d.%H:%M:%S')' - ERROR resuming VM ' ${vname[$int]} $vmid ' - $?'  >> $LOGFILE
         else
	    ((OPRESULT--))
         fi
      else
	  ((OPRESULT--))
      fi
   done
fi

if [ $OPRESULT -eq 0 ] || [ $SUSPEND -eq 1 ] ; then
   rm -f /var/lock/uws_rsy_datastore/$LOCKBASE.lock
   if [ -f "$POSCRIPT" ]; then
      /bin/bash $POSCRIPT
   else
      echo $(date '+%Y.%m.%d.%H:%M:%S') " - post script invalid or empty: $POSCRIPT"  >> $LOGFILE
   fi
   exit 0
fi

exit 255

