#!/bin/sh

export PATH=/usr/body/bin:$PATH

#########################################################
#  
#  U P D A T E R   L O C A L   F U N C T I O N  
#  
#########################################################

#------------------------------------------------------------------------------
# get version, model, region information from header file(hdrInf.dat)
# - argument
#   none
# - return
#   0     : OK
#   others: Err
#------------------------------------------------------------------------------
func_get_set_version()
{
	local version_len
	local model_len
	local region_len

	dst_version=`sed -n -e 's/^ver=\([0-9]\{4,\}\)/\1/p' /ramdsk/hdrInf.dat`
	if [ $? -ne 0 ]; then
		echo "UD_SH > get version failer."
		return $errDatVersion
	fi

	dst_model=`sed -n -e 's/^model=\([0-9]\{8,\}\)/\1/p' /ramdsk/hdrInf.dat`
	if [ $? -ne 0 ]; then
		echo "UD_SH > get model failer."
		return $errDatModel
	fi

	dst_region=`sed -n -e 's/^region=\([0-9]\{8,\}\)/\1/p' /ramdsk/hdrInf.dat`
	if [ $? -ne 0 ]; then
		echo "UD_SH > get region failer."
		return $errDatRegion
	fi

	if [ -n "$dst_version" ] && [ -n "$dst_model" ] && [ -n "$dst_region" ] ; then
		version_len=`busybox expr length $dst_version`
		model_len=`busybox expr length $dst_model`
		region_len=`busybox expr length $dst_region`

		echo "UD_SH > version length = $version_len"
		echo "UD_SH > model length = $model_len"
		echo "UD_SH > regison length = $region_len"
	else
		echo "UD_SH > get set version failer."
		return $errInvalidHead
	fi

	if [ $version_len -eq $VERSION_LENGTH ] && [ $model_len -eq $MODEL_LENGTH ] && [ $region_len -eq $REGION_LENGTH ] ; then
		echo "UD_SH > new header = dst_version=$dst_version, dst_model=$dst_model, dst_region=$dst_region"
		return 0
	fi

	# detected header error
	return $errInvalidHead
}

#------------------------------------------------------------------------------
# Record version, model, region information into file
# - argument
#   none
# - return
#   0     : OK
#   others: Err
#------------------------------------------------------------------------------
func_record_set_version()
{
	local L_FileExist=0

	echo "$dst_version" > tmp.dat

	if [ -f /mnt2/updater/dat4 ]; then
		cp /mnt2/updater/dat4 org.dat
		L_FileExist=1
	else
		echo "UD_SH > first time, set dat4"
	fi

	ud_datcnv -e -i tmp.dat -o /mnt2/updater/dat4 -a
	if [ $? -ne 0 ]; then
		echo "UD_SH > ud_datcnv encode failure"
		return $errRecordVersion
	fi

	func_remnt 1 $DEVICE2 $MNT_TARGET2
	if [ $? -ne 0 ] ; then
		echo "UD_SH > failed to re-mount : frsv1"
		return $errFlashReMnt
	fi

	ud_datcnv -d -i /mnt2/updater/dat4 -o tmp2.dat -a
	if [ $? -ne 0 ]; then
		echo "UD_SH > ud_datcnv decode failure"
		return $errRecordVersion
	fi

	cmp tmp.dat tmp2.dat
	if [ $? -ne 0 ]; then
		if [ $L_FileExist -eq 1 ]; then
			cp org.dat /mnt2/updater/dat4
			sync
		fi
		busybox rm -f org.dat tmp.dat tmp2.dat
		return $errRecordVersion
	fi
	echo "UD_SH > record version=$dst_version into /mnt2/updater/dat4"
	busybox rm -f org.dat tmp.dat tmp2.dat

	if [ $eUpMode -eq $eUpModeProd ] || [ $eUpMode -eq $eUpModeDvlp ]; then

		L_FileExist=0

		echo "$dst_model" > tmp.dat
		if [ -f /mnt1/dat2 ]; then
			cp /mnt1/dat2 org.dat
			L_FileExist=1
		else
			echo "UD_SH > first time, set dat2"
		fi
		ud_datcnv -e -i tmp.dat -o /mnt1/dat2 -a
		if [ $? -ne 0 ]; then
			echo "UD_SH > ud_datcnv encode failure"
			return $errRecordModel
		fi

		func_remnt 1 $DEVICE1 $MNT_TARGET1
		if [ $? -ne 0 ] ; then
			echo "UD_SH > failed to re-mount : frsv2"
			return $errFlashReMnt
		fi

		ud_datcnv -d -i /mnt1/dat2 -o tmp2.dat -a
		if [ $? -ne 0 ]; then
			echo "UD_SH > ud_datcnv decode failure"
			return $errRecordModel
		fi

		cmp tmp.dat tmp2.dat
		if [ $? -ne 0 ]; then
			if [ $L_FileExist -eq 1 ]; then
				cp org.dat /mnt1/dat2
				sync
			fi
			busybox rm -f org.dat tmp.dat tmp2.dat
			return $errRecordModel
		fi
		echo "UD_SH > record model=$dst_model into /mnt1/dat2"
		busybox rm -f org.dat tmp.dat tmp2.dat

		L_FileExist=0
		echo "$dst_region" > tmp.dat
		if [ -f /mnt1/dat3 ]; then
			cp /mnt1/dat3 org.dat
			L_FileExist=1
		else
			echo "UD_SH > first time, set dat3"
		fi

		ud_datcnv -e -i tmp.dat -o /mnt1/dat3 -a
		if [ $? -ne 0 ]; then
			echo "UD_SH > ud_datcnv encode failure"
			return $errRecordRegion
		fi

		func_remnt 1 $DEVICE1 $MNT_TARGET1
		if [ $? -ne 0 ] ; then
			echo "UD_SH > failed to re-mount : frsv3"
			return $errFlashReMnt
		fi

		ud_datcnv -d -i /mnt1/dat3 -o tmp2.dat -a
		if [ $? -ne 0 ]; then
			echo "UD_SH > ud_datcnv decode failure"
			return $errRecordRegion
		fi

		cmp tmp.dat tmp2.dat
		if [ $? -ne 0 ]; then
			if [ $L_FileExist -eq 1 ]; then
				cp org.dat /mnt1/dat3
				sync
			fi
			busybox rm -f org.dat tmp.dat tmp2.dat
			return $errRecordRegion
		fi
		echo "UD_SH > record region=$dst_region into /mnt1/dat3"
		busybox rm -f org.dat tmp.dat tmp2.dat
	else
		echo "UD_SH > no record model and region into /mnt1/dat2, dat3"
	fi

	sync

	return 0
}

#------------------------------------------------------------------------------
# Check model, region, version condition for update
# - argument
#   none
# - return
#   0     : OK
#   others: Err
#------------------------------------------------------------------------------
func_check_model_condition()
{
	local src_model
	local src_region

	ud_datcnv -d -i /mnt1/dat2 -o tmp.dat -a
	if [ $? -ne 0 ]; then
		echo "UD_SH > ud_datcnv failure"
		return $errCheckModel
	fi
	src_model=`cat tmp.dat`
	if [ $dst_model -ne $src_model ]; then
		echo "UD_SH > dst_model=$dst_model is not equal to src_model=$src_model"
		return $errCheckModel
	fi
	echo "UD_SH > dst_model=$dst_model is equal to src_model=$src_model"

	busybox rm -f tmp.dat

	ud_datcnv -d -i /mnt1/dat3 -o tmp.dat -a
	if [ $? -ne 0 ]; then
		echo "UD_SH > ud_datcnv failure"
		return $errCheckRegion
	fi
	src_region=`cat tmp.dat`
	if [ $dst_region -ne $src_region ]; then
		echo "UD_SH > dst_region=$dst_region is not equal to src_region=$src_region"
		return $errCheckRegion
	fi
	echo "UD_SH > dst_region=$dst_region is equal to src_region=$src_region"

	busybox rm -f tmp.dat

	return 0
}

#------------------------------------------------------------------------------
# func_save_set_version
#------------------------------------------------------------------------------
# - argument
#   none
# - return
#   0 : normal
#   others
#   errSaveVersion
#   errSaveModel
#   errSaveRegion
#
func_save_set_version()
{
	rm -rf $RAMDSK_PATH/dat

	mkdir -p $RAMDSK_PATH/dat

	# save version
	cp /mnt2/updater/dat4 $RAMDSK_PATH/dat/.
	if [ $? -ne 0 ]; then
		return $errSaveVersion
	fi

	# save model
	cp /mnt1/dat2 $RAMDSK_PATH/dat/.
	if [ $? -ne 0 ]; then
		return $errSaveModel
	fi

	# save region
	cp /mnt1/dat3  $RAMDSK_PATH/dat/.
	if [ $? -ne 0 ]; then
		return $errSaveRegion
	fi

	return 0;
}

#------------------------------------------------------------------------------
# func_restore_set_version
#------------------------------------------------------------------------------
# - argument
#   none
# - return
#   0 : normal
#   others
#   errRestoreVersion
#   errRestoreModel
#   errRestoreRegion
#
func_restore_set_version()
{
	# save version
	cp $RAMDSK_PATH/dat/dat4 /mnt2/updater/.
	if [ $? -ne 0 ]; then
		return $errRestoreVersion
	fi

	sync

	# save model
	cp $RAMDSK_PATH/dat/dat2 /mnt1/.
	if [ $? -ne 0 ]; then
		return $errRestoreModel
	fi

	sync

	# save region
	cp $RAMDSK_PATH/dat/dat3 /mnt1/.
	if [ $? -ne 0 ]; then
		return $errRestoreRegion
	fi

	sync


	rm -rf $RAMDSK_PATH/dat

	return 0;
}

#------------------------------------------------------------------------------
# Re-Mounts partition 1 and 2 and 3
# - argument
#   $1 : mount option switch
#        0 -> without sync option
#        1 -> with sync option
# - return
#    0     : OK
#    others: Err
#------------------------------------------------------------------------------
func_remnt_all()
{
	func_umtall
	if [ $? -ne 0 ]; then
		echo "UD_SH > failed to func_umtall. : frma1"
		return 1
	fi

	func_mntall $1
	if [ $? -ne 0 ]; then
		echo "UD_SH > failed to func_mntall. : frma2"
		return 1
	fi

	if [ $1 -eq 0 ]; then
		echo "UD_SH > remount without sync option - done"
	else
		echo "UD_SH > remount with sync option - done"
	fi

	return 0
}

#------------------------------------------------------------------------------
# Re-Mounts partition
# - argument
#   $1 : mount option switch
#        0 -> without sync option
#        1 -> with sync option
#   $2 : device
#   $3 : directory
# - return
#   0     : OK
#   others: Err
#------------------------------------------------------------------------------
func_remnt()
{
	local L_res

	$CMD_UMOUNT $2
	if [ $? -ne 0 ]; then
		echo "UD_SH > failed to func_umtall. : frma1"
		return 1
	fi

	if [ $1 -eq 0 ]; then
		$CMD_MOUNT $2 $3
		L_res=$?
	else
		$CMD_MOUNT_S $2 $3
		L_res=$?
	fi

	if [ $L_res -ne 0 ]; then
		echo "UD_SH > failed to mounting $2 on $3."
		return 1
	fi

	return 0
}

#------------------------------------------------------------------------------
# Re-Mounts partition 6
# - argument
#   $1 : device
#   $2 : directory
# - return
#   0     : OK
#   others: Err
#------------------------------------------------------------------------------
func_remnt_p6()
{
	$CMD_UMOUNT $1
	if [ $? -ne 0 ]; then
		echo "UD_SH > failed to func_umtall. : frmp6"
		return 1
	fi

	$CMD_MOUNT_BS $1 $2
	if [ $? -ne 0 ]; then
		echo "UD_SH > failed to mounting $1 on $2."
		return 1
	fi

	return 0
}

#------------------------------------------------------------------------------
# Mounts partition 2 and 3 and 5
# - argument
#   $1 : mount option switch
#        0 -> without sync option
#        1 -> with sync option
# - return
#    0     : OK
#    others: Err
#------------------------------------------------------------------------------
func_mntall()
{
	local L_res

	if [ $1 -eq 0 ]; then
		$CMD_MOUNT $DEVICE1 $MNT_TARGET1
		L_res=$?
	else
		$CMD_MOUNT_S $DEVICE1 $MNT_TARGET1
		L_res=$?
	fi

	if [ $L_res -ne 0 ]; then

		echo "UD_SH > failed to mounting $DEVICE1 on $MNT_TARGET1."
		return 1
	fi

	if [ $1 -eq 0 ]; then
		$CMD_MOUNT $DEVICE2 $MNT_TARGET2
		L_res=$?
	else
		$CMD_MOUNT_S $DEVICE2 $MNT_TARGET2
		L_res=$?
	fi

	if [ $L_res -ne 0 ]; then

		echo "UD_SH > failed to mounting $DEVICE2 on $MNT_TARGET2."
		return 1
	fi

	if [ $1 -eq 0 ]; then
		$CMD_MOUNT $DEVICE3 $MNT_TARGET3
		L_res=$?
	else
		$CMD_MOUNT_S $DEVICE3 $MNT_TARGET3
		L_res=$?
	fi

	if [ $L_res -ne 0 ]; then

		echo "UD_SH > failed to mounting $DEVICE3 on $MNT_TARGET3."
		return 1
	fi

	if [ $1 -eq 0 ]; then
		$CMD_MOUNT $DEVICE5 $MNT_TARGET5
		L_res=$?
	else
		$CMD_MOUNT_S $DEVICE5 $MNT_TARGET5
		L_res=$?
	fi

	if [ $L_res -ne 0 ]; then

		echo "UD_SH > failed to mounting $DEVICE5 on $MNT_TARGET5."
		return 1
	fi

	if [ $1 -eq 0 ]; then
		$CMD_MOUNT $DEVICE6 $MNT_TARGET6
		L_res=$?
	else
		$CMD_MOUNT_S $DEVICE6 $MNT_TARGET6
		L_res=$?
	fi

	if [ $L_res -ne 0 ]; then

		echo "UD_SH > failed to mounting $DEVICE6 on $MNT_TARGET6."
		return 1
	fi

	return 0
}

#------------------------------------------------------------------------------
# Unmounts partition 2 and 3 and 5
# - argument
#   none
# - return
#    0     : OK
#    others: Err
#------------------------------------------------------------------------------
func_umtall()
{
	$CMD_UMOUNT $MNT_TARGET1 2>/dev/null
	if [ $? -ne 0 ]; then

		echo "UD_SH > failed to unmounting $DEVICE1 on $MNT_TARGET1."
		return 1
	fi

	$CMD_UMOUNT $MNT_TARGET2 2>/dev/null
	if [ $? -ne 0 ]; then

		echo "UD_SH > failed to unmounting $DEVICE2 on $MNT_TARGET2."
		return 1
	fi

	$CMD_UMOUNT $MNT_TARGET3 2>/dev/null
	if [ $? -ne 0 ]; then

		echo "UD_SH > failed to unmounting $DEVICE3 on $MNT_TARGET3."
		return 1
	fi

	$CMD_UMOUNT $MNT_TARGET5 2>/dev/null
	if [ $? -ne 0 ]; then

		echo "UD_SH > failed to unmounting $DEVICE5 on $MNT_TARGET5."
		return 1
	fi

	$CMD_UMOUNT $MNT_TARGET6 2>/dev/null
	if [ $? -ne 0 ]; then

		echo "UD_SH > failed to unmounting $DEVICE6 on $MNT_TARGET6."
		return 1
	fi

	return 0
}

#------------------------------------------------------------------------------
# termination procedure
#------------------------------------------------------------------------------
# - argument
#   none
# - return
#   none
#   
func_termination()
{
	#--------------------------------------------------
	# if stat exists, check contents and 
	# change mode of updater according to the contents 
	#--------------------------------------------------

	func_recordTime "-------- Updater Finished --------" $RAMDSK_PATH/$TIMEFILE

	if [ -f "$STATFILE_PATH/$PROGRES" ]; then
		for i in `cat $STATFILE_PATH/$PROGRES`
		do
			case $i in
				$MARK_FINI)

				# set updater mode to OFF
				echo "UD_SH > deleting $MODE file"
				busybox rm $STATFILE_PATH/$MODE

				if [ -f $MODE_PATH/$SFWMODE ]; then
					busybox rm $MODE_PATH/$SFWMODE
				fi

				if [ -f $MODE_PATH/$FWMODE ]; then
					busybox rm $MODE_PATH/$FWMODE
				fi

				# make sure of completion of file operation.
				sync

				if [ ! -f "$STATFILE_PATH/omg_prod_dvlp" ] && [ ! -f "$STATFILE_PATH/omg_usr_svc" ]; then
					ud_progress.sh 100
				fi
				;;

				*)
				# do nothing
				echo "UD_SH > failed to update - no operation on status files."
				echo "$eError" > $MNT_TARGET1/$PARTCNFBK
				;;
			esac
		done
	else
		echo "UD_SH > There is no valid -progress- file -> $STATFILE_PATH/$PROGRES."
	fi

	#------------------------------
	# umount Flash
	#------------------------------
	func_umtall

	#------------------------------
	# decide global error variable
	#------------------------------
	if [ $eError -eq $errNoError ]; then

		# It means to end completely normally here. 
		wPhaseNum=$wPhaseTerminate

		ud_led -c 1 -n $LEDNUM

		echo " "
		echo "-------------------------------------------"
		echo "UD_SH > All process were done successfully."
		echo "-------------------------------------------"
		echo " "

		exit 0

	else
		ud_progress.sh err
	fi

	# when you reached here, it means something error has been happened.
	# enter eternal loop 

	echo " "
	echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
	echo "UD_SH > Error $eError has happened!!"
	echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
	echo " "

	if [ $eUpMode -eq $eUpModeProd ] || [ $eUpMode -eq $eUpModeDvlp ]; then

		export eError=$eError
		export LEDNUM=$LEDNUM

		# Blink LED
		sh /usr/body/bin/utility/shell/body_led_ctrl.sh&

	fi

	exit 1
}

#------------------------------------------------------------------------------
# retrieve contents file from MS
#------------------------------------------------------------------------------
# - argument 
#   none
# - returns
#   When contents file is valid, returns the num of file contained in Firmupdata,
#   When error, returns error code. (in this case, the value is greater than errErrOffset)
#
func_get_contents_file()
{
	local L_res

	# make contents infomation file
	ud_msrd -m user -t
	if [ $? -ne 0 ]; then
		echo "UD_SH > failed to read from MS"
		let j=$errErrOffset+21
		return $j
	fi

	# Get no 0 file just for get contents info file
	case $eUpMode in
		$eUpModeUser | $eUpModeSvc)

			ud_datcnv -d -i $DAT1_PATH/$DAT1 -o /ramdsk/key.dat
			L_res=$?

			if [ $L_res -ne 0 ]; then
				echo "UD_SH > failed to ud_datcnv"
				let j=$errErrOffset+21
				return $j
			fi

			ud_msrd -m user -o $CMDtoSH -n 0 -e /ramdsk/key.dat
			L_res=$?

			if [ -f tmp.dat ]; then
				busybox rm -f tmp.dat
			fi
			sync
			;;

		*)
			ud_msrd -m user -o $CMDtoSH -n 0
			L_res=$?
			;;
	esac

	if [ $L_res -ne 0 ]; then
		echo "UD_SH > failed to read from MS"
		let j=$errErrOffset+21
		return $j
	fi

	# check the validity of contents info file and get num of files
	ud_rdmgr -m 0 -c $RAMDSK_PATH/$CntFile

	# Then return it
	return $?
}

#------------------------------------------------------------------------------
# get indicated file from media
#------------------------------------------------------------------------------
# - argument
#   $1: read file type
#   $2: read file number
# - return
#   0: normal
#   1: failed to read from ms
#   2: no existing media
#   3: ud_rdmgr failed
#   4: invalid paramter
#
func_get_file()
{
	# get file to $GotFile
	func_recordTime "Getting $2 th file start." $RAMDSK_PATH/$TIMEFILE

	func_read_file_from_ms $2
	if [ $? -ne 0 ]; then
		echo "UD_SH > failed to read from ms(num:$2) : fgf1"
		return 1
	fi

	func_recordTime "ChkSum start." $RAMDSK_PATH/$TIMEFILE

	# check file validity and progress
	ud_rdmgr -m 1 -c $RAMDSK_PATH/$CntFile -i $RAMDSK_PATH/$GotFile -o $RAMDSK_PATH/$FileName -p $STATFILE_PATH/$PROGRES -n $2

	if [ $? -ne 0 ]; then
		echo "UD_SH > failed to check validity of file.[ret=$?]  : fgf3"
		return 3
	fi

	# do rename
	case $1 in
		$eFileTypeHeader )
			echo "UD_SH > got file name is $GotFile"
			# rename it when necessary
			if [ $GotFile != $HdrFile ]; then
				mv $RAMDSK_PATH/$GotFile $RAMDSK_PATH/$HdrFile
			fi
			;;

		$eFileTypeFirm )
			k=`cat $RAMDSK_PATH/$FileName`
			echo "UD_SH > org file name is $k"
			#rename it when necessary
			if [ $GotFile != $k ]; then
				mv $RAMDSK_PATH/$GotFile $RAMDSK_PATH/$k
			fi
			;;

		* )
			echo "UD_SH > invalid file type  : fgf4"
			return 4
			;;
	esac

	func_recordTime "----> Finished. File name is $k" $RAMDSK_PATH/$TIMEFILE

	# sync must be needed to make sure rename
	sync

	return 0
}

#------------------------------------------------------------------------------
# write firmware data and verify
#------------------------------------------------------------------------------
# - argument
#   none
# - return
#   0: normal
#   1: abnormal
#
func_data_write_verify()
{
	local filename=`cat $RAMDSK_PATH/$FileName`
	local ret=0

	case $filename in

		*backup.tar | *factory.tar )

			func_copy_to_p2 $filename
			ret=$?
			if [ $ret -ne 0 ]; then
				return $ret
			fi
			;;

		*linuxset*.tar )

			func_copy_to_p3 $filename
			ret=$?
			if [ $ret -ne 0 ]; then
				return $ret
			fi
			;;

		*av.bin | *sa.bin)

			func_copy_to_p5 $filename
			ret=$?
			if [ $ret -ne 0 ]; then
				return $ret
			fi
			;;

		*bin.tar | *lib.tar | *fskapp*.tar | *fskrel*.tar | *fskfnt.tar)

			func_copy_to_p6 $filename
			ret=$?
			if [ $ret -ne 0 ]; then
				return $ret
			fi
			;;

		omg* )
			omega_firm_flg=1
			;;
	esac

	return $errNoError
}

#------------------------------------------------------------------------------
# initialization partition  
#------------------------------------------------------------------------------
# - argument
#   $1: file name
# - return
#   0: normal
#   1: abnormal
#
func_init_partition()
{
	ERROR_FLAG=0
	local i=$1
	local ret=0

	case $i in
		*loader.tar)

			#------------------------------------------------------------------------------
			# . Save Adjust Data
			#------------------------------------------------------------------------------
			if [ -f "$MNT_TARGET2/$P2_FACTORY_PATH/Areg.bin" ]; then

				mkdir -p $RAMDSK_PATH$SAVEADJ_DIRPATH

				echo "[UD_SH] ER_PHASE: Copy Adjust file data"

				busybox cp -a $MNT_TARGET2/$P2_FACTORY_PATH/*reg*.* $RAMDSK_PATH$SAVEADJ_DIRPATH

				if [ $? -ne 0 ]; then
					echo "[UD_SH] ER_PHASE: failed to copy factory data."
					return $errLDWRCPADJ
				fi
	
				wAdjustDataSave=1
			else
				echo "[UD_SH] ER_PHASE: NOT Adjust data P2/factory dir:"
			fi

			if [ -f "$MNT_TARGET2/$P2_FACTORY_PATH/.hasp" ]; then

				echo "[UD_SH] ER_PHASE: Copy hasp file data"

				busybox cp -a $MNT_TARGET2/$P2_FACTORY_PATH/.hasp $RAMDSK_PATH

				if [ $? -ne 0 ]; then
					echo "[UD_SH] ER_PHASE: failed to copy hasp data."
					return $errLDWRCPHASP
				fi
				
				whaspDataSave=1
			else
				echo "[UD_SH] ER_PHASE: NOT hasp data P2/factory dir"
			fi

			echo "[UD_SH] ER_PHASE: The Loader2 and the Loader3 are updated."

			func_copy_loader $i
			ret=$?
			if [ $ret -ne 0 ]; then
				echo "[UD_SH] ER_PHASE: Failed to func_copy_loader."
				return $ret
			fi
		;;

		*to_def.txt)

			echo "[UD_SH] to_test execute."

			to_test_comp

			if [ $? -ne 0 ] ;then
				return $errTOTEST
			fi

		;;

		*partinf.tbl)

			if [ $wCurFileNum -ne $PART_INIT_FILENUM ]; then
				if [ $wCurFileNum -ne $NR_PART_INIT_FILENUM ]; then
					ERROR_FLAG=1
					return $errDatIniPartFileOrder
				fi
			fi

			if [ -f /mnt2/updater/PAL ]; then
				wVideoOut=$wPAL
			else
				wVideoOut=$wNTSC
			fi

			# When all firmware is renewed, with user mode and
			# service mode, set version is retained. 
			if [ $wUpdateType -eq $wUpdateTypeFull ] ;then
				if [ $eUpMode -eq $eUpModeUser ] || [ $eUpMode -eq $eUpModeSvc ]; then
					func_save_set_version
					ret=$?
					if [ $? -ne 0 ]; then
						ERROR_FLAG=1
						return $ret
					fi
				fi
			fi

			# Umount Flash
			func_umtall

			# initialization 
			edisx -f /$RAMDSK_PATH/$i
			if [ $? -ne 0 ]; then
				ERROR_FLAG=1
				return $errEdisx
			fi

			# and then foramt
			func_make_filesystem_on_part
			ret=$?
			if [ $ret -ne 0 ]; then
				ERROR_FLAG=1
				return $ret
			fi

			# mount Flash again with sync
			func_mntall 1
			if [ $? -ne 0 ]; then
				ERROR_FLAG=1
				return $errFlashMnt
			fi

			# Then enable updater because of mode file was cleared.
			func_set_init_file

			if [ $wVideoOut -eq $wPAL ]; then
				touch /mnt2/updater/PAL
				sync
			fi

			# When all firmware is renewed, with user mode and service mode, 
			# after the partition drawing up you write set version 
			# which is retained and reset.
			if [ $wUpdateType -eq $wUpdateTypeFull ] ;then
				if [ $eUpMode -eq $eUpModeUser ] || [ $eUpMode -eq $eUpModeSvc ]; then
					func_restore_set_version
					ret=$?
					if [ $? -ne 0 ]; then
						ERROR_FLAG=1
						return $ret
					fi
				fi
			fi

			func_mark_progres $MARK_BUSY

			chk_exec_mode_flag
			if [ $? -ne 0 ] ;then
				rm -rf $RAMDSK_PATH$MODEFILE_DIRPATH
				echo ""
				echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
				echo "[UD_SH] failed to chk_exec_mode_flag()"
				echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
				echo ""
				return $errMakeModeFile
			fi
			rm -rf $RAMDSK_PATH$MODEFILE_DIRPATH

			# copy backup of partition setting file
			busybox cp $RAMDSK_PATH/$PARTCNF $MNT_TARGET1/$PARTCNFBK
			sync

			#------------------------------------------------------------------------------
			# . Rewrite Adjust Data 
			#------------------------------------------------------------------------------
			if [ $wAdjustDataSave -eq 1 ]; then

				echo "[UD_SH] ER_PHASE: Rewrite Adjust data "

				mkdir -p $MNT_TARGET2$P2_FACTORY_PATH

				busybox cp -a $RAMDSK_PATH$SAVEADJ_DIRPATH/*reg*.* $MNT_TARGET2$P2_FACTORY_PATH

				if [ $? -ne 0 ]; then
					echo "[UD_SH] ER_PHASE: failed to copy adjust data."
					return $errLDREWRCPADJ
				fi

				rm -rf $RAMDSK_PATH$SAVEADJ_DIRPATH

				wAdjustDataSave=0
			else
				echo "[UD_SH] ER_PHASE: No Rewrite Adjust data!! "
			fi

			if [ $whaspDataSave -eq 1 ]; then

				echo "[UD_SH] ER_PHASE: Rewrite hasp data "

				if [ ! -d "$MNT_TARGET2/$P2_FACTORY_PATH" ] ; then

					mkdir -p $MNT_TARGET2$P2_FACTORY_PATH
				fi
				
				busybox cp -a $RAMDSK_PATH/.hasp $MNT_TARGET2$P2_FACTORY_PATH

				if [ $? -ne 0 ]; then
					echo "[UD_SH] ER_PHASE: failed to copy hasp data."
					return $errLDREWRCPHASP
				fi

				rm -rf $RAMDSK_PATH/.hasp

				whaspDataSave=0
			else
				echo "[UD_SH] ER_PHASE: No Rewrite hasp data!! "
			fi

			# mount Flash again without sync
			func_remnt_all 0
			if [ $? -ne 0 ]; then
				return $errFlashReMnt
			fi
		;;

		*updater.tar | *updater2.tar)

			echo "[UD_SH] ER_PHASE: The Updater are updated."

			func_copy_updater $i
			ret=$?
			if [ $ret -ne 0 ]; then
				echo "[UD_SH] ER_PHASE: Failed to func_copy_updater()"
				return $ret
			fi

			let wudcpycnt=$wudcpycnt+1

			if [ $wudcpycnt -eq 2 ]; then

				echo "[UD_SH] ER_PHASE: The MBR of the flag is set.($wudcpycnt)"

				func_set_mbr_flag $i
				if [ $? -ne 0 ]; then
					echo "[UD_SH] ER_PHASE: Failed to func_set_mbr_flag()"
					return $errPFORMAT2
				fi

				wudcpycnt=0
			fi
			;;

		*)
			# do nothing
		;;
	esac

	return 0
}

#------------------------------------------------------------------------------
# Partition2 dsc dir make process 
#------------------------------------------------------------------------------
# - argument
#   none
# - return
#   none
#
func_p2_dsc_makedir()
{
	if [ ! -d $DSC_PATH ]; then

		mkdir -p $DSC_PATH

		sync

		echo "UD_SH > make  dir -> $DSC_PATH : fp2md1"

	else

		curDir=`pwd`
		echo "UD_SH > Current dir : $curDir"

		cd $DSC_PATH

		busybox rm -rf *

		sync

		echo "UD_SH > $DSC_PATH in file All Remove.: fp2md2"

		cd $curDir

	fi
}

#------------------------------------------------------------------------------
# To trick for next boot, updater/serser will wake up 
#------------------------------------------------------------------------------
# - argument
#   none
# - return
#   none
#
func_set_init_file()
{
	# will wake up updater!
	mkdir -p $STATFILE_PATH
	touch $STATFILE_PATH/$MODE

	case $eUpMode in
		$eUpModeProd )
			touch $STATFILE_PATH/$FWMODE
			echo "$INIT_PROD" > "$STATFILE_PATH/$FWMODE"
			;;

		$eUpModeDvlp )
			touch $STATFILE_PATH/$FWMODE
			echo "$INIT_DVLP" > "$STATFILE_PATH/$FWMODE"
			;;
		$eUpModeUser )
			touch $MNT_TARGET2/$SUSPEND
			;;
		*)
			;;
	esac

	if [ $eUpMode -eq $eUpModeProd ] || [ $eUpMode -eq $eUpModeDvlp ]; then
		# will wake up module1!
		mkdir -p $SEN_PATH
		touch $SEN_PATH/$SMODE
		echo "$INIT_SEN" > "$SEN_PATH/$SMODE"
	else
		rm -rf $SEN_PATH
	fi

	# make sure of completion of file operation.
	sync
}

#------------------------------------------------------------------------------
# Modefile write success check
#------------------------------------------------------------------------------
# - argument
#   none
# - return
#   0: normal
#   1: abnormal
# 
chk_exec_mode_flag()
{
	mkdir -p $RAMDSK_PATH$MODEFILE_DIRPATH

	touch $RAMDSK_PATH$MODEFILE_DIRPATH/$FWMODE
	echo "$INIT_PROD" > "$RAMDSK_PATH$MODEFILE_DIRPATH/$FWMODE"

	if [ ! -f $STATFILE_PATH/$MODE ]; then
		return 1
	fi

	case $eUpMode in
		$eUpModeUser )

			cmp $STATFILE_PATH/$FWMODE $RAMDSK_PATH$MODEFILE_DIRPATH/$FWMODE

			if [ $? -eq 0 ] ; then
				return 1
			fi	

			;;

		$eUpModeProd | $eUpModeDvlp )

			touch $RAMDSK_PATH$MODEFILE_DIRPATH/$SMODE
			echo "$INIT_SEN" > "$RAMDSK_PATH$MODEFILE_DIRPATH/$SMODE"

			cmp $SEN_PATH/$SMODE $RAMDSK_PATH$MODEFILE_DIRPATH/$SMODE

			if [ $? -ne 0 ] ; then
				return 1
			fi

			cmp $STATFILE_PATH/$FWMODE $RAMDSK_PATH$MODEFILE_DIRPATH/$FWMODE

			if [ $? -ne 0 ] ; then

				echo "$INIT_DVLP" > "$RAMDSK_PATH$MODEFILE_DIRPATH/$FWMODE"

				cmp $STATFILE_PATH/$FWMODE $RAMDSK_PATH$MODEFILE_DIRPATH/$FWMODE

				if [ $? -ne 0 ] ; then
					return 1
				fi	
			fi
			;;

		*)
			return 1
			;;
	esac

	echo "[UD_SH] chk_exec_mode_flag all OK"

	return 0
}

#------------------------------------------------------------------------------
# read file from MS
#------------------------------------------------------------------------------
# - argument
#   $1: file number
# - return
#   0: normal
#   1: abnormal
# 
func_read_file_from_ms()
{
	local L_res

	# goto ram disk path for data read out
	cd /$RAMDSK_PATH

	# file read
	case $eUpMode in
		$eUpModeUser | $eUpModeSvc)

			ud_msrd -m user -o $CMDtoSH -n $1 -e /ramdsk/key.dat
			L_res=$?

			if [ -f tmp.dat ]; then
				busybox rm -f tmp.dat
			fi
			sync
			;;

		*)
			ud_msrd -m user -o $CMDtoSH -n $1
			L_res=$?
			;;
	esac

	if [ $L_res -ne 0 ]; then
		echo "UD_SH > failed to read from MS : frfm1"
		return 1
	fi

	# copy file name
	GotFile=`cat $RAMDSK_PATH/$CMDtoSH`

	# extract file name
	GotFile=`busybox basename $GotFile`

	# then clean the file
	echo "" > $RAMDSK_PATH/$CMDtoSH

	return 0
}

#------------------------------------------------------------------------------
# make file system(formated by uvfat) on partition
#------------------------------------------------------------------------------
# - argument
#   none
# - return
#   0: normal
#  !0: abnormal
#      errFlashFmtP1
#      errFlashFmtP2
#      errFlashFmtP3
#      errFlashFmtP5
#      errFlashFmtP6
func_make_filesystem_on_part()
{
	if [ $wUpdateType -eq $wUpdateTypeFull ] ;then

		echo "[UD_SH] ER_PHASE: LOADER AND UPDATA FILE "

		mkdosfs -F 12 -s 32 $DEVICE1
		if [ $? -ne 0 ] ;then
			echo "[UD_SH] ER_PHASE: failed to make uvfat FS on $DEVICE1 : mfop1"
			return $errFlashFmtP1
		fi
		echo "[UD_SH] ER_PHASE: formated by uvfat FS on $DEVICE1"

		mkdosfs -F 12 -s 32 $DEVICE2
		if [ $? -ne 0 ] ;then
			echo "[UD_SH] ER_PHASE: failed to make uvfat FS on $DEVICE2 : mfop2"
			return $errFlashFmtP2
		fi
		echo "[UD_SH] ER_PHASE: formated by uvfat FS on $DEVICE2"
	fi

	mkdosfs -F 12 -s 32 $DEVICE3
	if [ $? -ne 0 ] ;then
		echo "[UD_SH] ER_PHASE: failed to make uvfat FS on $DEVICE3 : mfop3"
		return $errFlashFmtP3
	fi
	echo "[UD_SH] ER_PHASE: formated by uvfat FS on $DEVICE3"

	mkdosfs -F 12 -s 32 $DEVICE5
	if [ $? -ne 0 ] ;then
		echo "[UD_SH] ER_PHASE: failed to make uvfat FS on $DEVICE5 : mfop4"
		return $errFlashFmtP5
	fi
	echo "[UD_SH] ER_PHASE: formated by uvfat FS on $DEVICE5"

#	mkdosfs -F 12 -s 8 $DEVICE6
	mkdosfs -F 16 -s 8 $DEVICE6
	if [ $? -ne 0 ] ;then
		echo "[UD_SH] ER_PHASE: failed to make uvfat FS on $DEVICE6 : mfop5"
		return $errFlashFmtP6
	fi

	echo "[UD_SH] ER_PHASE: formated by uvfat FS on $DEVICE6"

	return 0
}

#------------------------------------------------------------------------------
# record progress status into $STATFILE_PATH/$PROGRES
#------------------------------------------------------------------------------
# - argument
#   $1: 1st - the string to write into $PROGRES file
# - return
#   none
#
func_mark_progres()
{
	if [ ! -f "$STATFILE_PATH/$PROGRES" ]; then
		echo "UD_SH > try to make $STATFILE_PATH/$PROGRES file"
		touch $STATFILE_PATH/$PROGRES
	fi

	echo "UD_SH > try to mark $1 on $STATFILE_PATH/$PROGRES"
	echo "$1" > $STATFILE_PATH/$PROGRES

	# make it sure to update the contents
	sync

	echo "UD_SH > Contents of $STATFILE_PATH/$PROGRES is..."
	cat $STATFILE_PATH/$PROGRES
}

#------------------------------------------------------------------------------
# copy one file to NAND flash where it is copied to $2/boot/
#------------------------------------------------------------------------------
# - argument
#   $1: file name to copy
#   $2: target dir
#   $3: device
# - return
#   0: normal
#   others: error
#
copy_file_to_nflash()
{
	local ret=0

	case $1 in
		*vmlinux | *initrd.img | rootfs.img)

			DEST_ROOT=$2$BOOT_TARGET

			if [ ! -d $DEST_ROOT ]; then
				mkdir -p $2$BOOT_TARGET 2>/dev/null
			else
				if [ -f "$DEST_ROOT/$1" ] ; then
					# Change mode and owner before Updater overwrite/erase files
					chown root $DEST_ROOT/$1
					chmod 755 $DEST_ROOT/$1
					busybox rm $DEST_ROOT/$1 2>/dev/null
				fi
			fi
			;;
		*)
			DEST_ROOT=$2
			if [ -f "$DEST_ROOT/$1" ] ; then
				# Change mode and owner before Updater overwrite/erase files
				chown root $DEST_ROOT/$1
				chmod 755 $DEST_ROOT/$1
			fi
			;;
	esac

	func_recordTime "copy_file_to_nflash - FlashCpy - $SOURCE_ROOT/$1 started." $RAMDSK_PATH/$TIMEFILE

	busybox cp -a $SOURCE_ROOT/$1 $DEST_ROOT/
	if [ $? -ne 0 ] ; then
		echo "UD_SH > failed to re-mount : cftn3"
		ERROR_FLAG=1

		case $3 in
		$DEVICE3 )
			ret=$errFirmUpP3
			;;
		$DEVICE5 )
			ret=$errFirmUpP5
			;;
		*)
			ret=$errInvalidFile
			;;
		esac

		return $ret
	fi

	func_remnt 0 $3 $2
	if [ $? -ne 0 ] ; then
		echo "UD_SH > failed to re-mount : cftn3"
		ERROR_FLAG=1

		case $3 in
		$DEVICE3 )
			ret=$errRemntP3
			;;
		$DEVICE5 )
			ret=$errRemntP5
			;;
		*)
			ret=$errInvalidFile
			;;
		esac

		return $ret
	fi

	func_recordTime "copy_file_to_nflash - Compare  - $SOURCE_ROOT/$1 started." $RAMDSK_PATH/$TIMEFILE

	if [ -f "$SOURCE_ROOT/$1" ] ; then
		if [ -f "$DEST_ROOT/$1" ] ; then
			cmp $SOURCE_ROOT/$1 $DEST_ROOT/$1
		else
			compares_file_in_targetdir $SOURCE_ROOT/$1 $DEST_ROOT/$1
		fi
	else
		compares_file_in_targetdir $SOURCE_ROOT/$1 $DEST_ROOT/$1
	fi

	if [ $? -eq 0 ]; then
		echo "UD_SH > OK, compare $SOURCE_ROOT/$1 with $DEST_ROOT/$1"
		ERROR_FLAG=0
	else
		echo "UD_SH > failed to compare $SOURCE_ROOT/$1 with $DEST_ROOT/$1 : cftn1"
		ERROR_FLAG=1

		case $3 in
		$DEVICE3 )
			ret=$errVerifyP3
			;;
		$DEVICE5 )
			ret=$errVerifyP5
			;;
		*)
			ret=$errInvalidFile
			;;
		esac

		return $ret
	fi

	func_recordTime "  -----> finished." $RAMDSK_PATH/$TIMEFILE

	busybox rm $SOURCE_ROOT/$1 2>/dev/null

	return 0
}

#------------------------------------------------------------------------------
# calculate file number
#------------------------------------------------------------------------------
# - argument
#   $1: current directory name
# - return 
#   number: file number
#
dir_file_counter()
{
	local fct=0

	for lfile in `ls -1 $1`
	do
		if [ "$lfile" != "" ]; then
			let fct=$fct+1
		fi
	done

	return $fct
}

#------------------------------------------------------------------------------
# check archive file size(block size)
#------------------------------------------------------------------------------
# - argument
#   $1: file name
# - return 
#   0: less than expected size($MaxsizeTar: 8192) 
#   1: over size
#
check_archive_maxsize()
{
	local archiveFile=$1

	set `ls -s1 $archiveFile`
	local kszFile=$1

	echo "UD_SH > file size = $kszFile[KB]"

	if [ $MaxsizeTar -gt $kszFile ] ; then
		echo "UD_SH > all copy , normal tar xf"
		return 0
	else
		echo "UD_SH > over size, a copy , tar xf --file"
		return 1
	fi
}

#------------------------------------------------------------------------------
# choose file and copy file into one-nand flash(/dev/nflasha3:/mnt3)
#------------------------------------------------------------------------------
# - argument
#   none
# - return 
#   0: normal
#   others: error
#
parse_copy_current()
{
	local ret=0

	for cfile in `ls -1`
	do
		case $cfile in
			vmlinux* | *initrd.img | rootfs.img)
				copy_file_to_nflash $cfile $MNT_TARGET3 $DEVICE3
				ret=$?
				if [ $ret -ne 0 ] ; then
					echo "UD_SH > failed to copy, image file is $i : pcc1"
					ERROR_FLAG=1
					return $ret
					break
				fi

				;;
			*)
				;;
		esac
	done

	return 0
}

#------------------------------------------------------------------------------
# dispatch routine to extract tar archive , copy to under directory
#------------------------------------------------------------------------------
# - argument
#   $1: archive file name
# - return
#   0: normal
#   others: error
#
copy_micon1_usr_p6()
{
	local lopath=""
	local copybase_dir=""
	local source_dir=""
	local target_dir=""
	local fname=$1
	local l_erase_dir_Flag
	local L_res


	if [ $eUpMode -eq $eUpModeUser ] || [ $eUpMode -eq $eUpModeSvc ]; then
		func_remnt_p6 $DEVICE6 $MNT_TARGET6
		L_res=$?
	else	
		func_remnt 0 $DEVICE6 $MNT_TARGET6
		L_res=$?
	fi

	if [ $L_res -ne 0 ] ; then
		echo "UD_SH > failed to re-mount: cm1up6"
		ERROR_FLAG=1
		return $errRemntP6
	fi


	case "$1" in
		*fskapp*.tar)
			lopath=$P6_FSK_APP
			tar tf "$1" > dirlist.txt
			;;	
		*fskfnt.tar)
			lopath=$P6_FSK_FONT
			;;	
		*fskrel*.tar)
			lopath=$P6_FSK_BIN_REL
			tar tf "$1" > dirlist.txt
			;;	
		*bin.tar)
			lopath=$P6_BIN
			;;
		*lib.tar)
			lopath=$P6_LIB
			;;
		*)	
			return $errInvalidFileP6
			;;
	esac

	if [ "$lopath" != "" ] ; then
		target_dir="$MNT_TARGET6/$lopath"
		source_dir=${lopath#local/}
	else
		busybox rm $fname
		return $errInvalidFileP6
	fi

	file_count=0
	dir_file_counter $source_dir
	file_count=$?
	if [ $file_count -gt 0 ] ; then

		# erase dirctory when exists
		case "$1" in
			*fskrel*.tar | *fskapp*.tar)
				if [ $wFskrelDetect -eq 0 ]; then
					echo "UD_SH > 1st detection of $1 - enabling delete dir flag"
					wFskrelDetect=1
					l_erase_dir_Flag=1
				else
					echo "UD_SH > $1 already detected - disabling delete dir flag"
					l_erase_dir_Flag=0
				fi
				;;

			*)
				l_erase_dir_Flag=1
				;;
		esac

		if [ -d "$target_dir" ] && [ $l_erase_dir_Flag -eq 1 ]; then
			# Change mode and owner before Updater overwrite/erase files
			chown -R root $target_dir
			chmod -R 755 $target_dir
			busybox rm -r $target_dir 2>/dev/null
		fi

		# delete tail dir letter
		copybase_dir=`$DirName $target_dir`

		if [ ! -d $copybase_dir ] ; then
			mkdir -p $copybase_dir
		fi

		func_recordTime "copy_micon1_usr_p6 - FlashCpy - $source_dir started." $RAMDSK_PATH/$TIMEFILE

		busybox cp -a $source_dir $copybase_dir
		if [ $? -ne 0 ] ; then
			ERROR_FLAG=1
			return $errFirmUpP6
		fi

		func_remnt 0 $DEVICE6 $MNT_TARGET6
		if [ $? -ne 0 ] ; then
			echo "UD_SH > failed to re-mount : chup64"
			ERROR_FLAG=1
			return $errRemntP6
		fi

		# Delete *.tar file here for preserving heap from tempfs.
		busybox rm $fname

		func_recordTime "copy_micon1_usr_p6 - between $source_dir and $target_dir diff started." $RAMDSK_PATH/$TIMEFILE

		# Then compare - use "cmp" when file size is large to preserve heap...
		case "$1" in
			*fskrel*.tar | *fskapp*.tar)
				echo "UD_SH > verify with cmp"

				for dir in `cat dirlist.txt` ; do

					if [ -d ./$dir ] ; then
						compares_file_in_targetdir "./$dir" "/mnt6/$dir"
						ret=$?
						if [ $ret -ne 0 ]; then
							return $errVerifyP6
							break
						fi
					fi
				done
				;;

			*)
				echo "UD_SH > verify with diff"
				compares_file_in_targetdir $source_dir $target_dir
				if [ $? -ne 0 ] ; then
					echo "UD_SH > verify failure $source_dir"
					ERROR_FLAG=1
					return $errVerifyP6
				fi
				;;
		esac

		busybox rm -r $source_dir 2>/dev/null

	else
		echo "UD_SH > not copy(file count:$file_count), nothing source file in $source_dir"
		busybox rm $fname
	fi

	func_recordTime "  -----> finished." $RAMDSK_PATH/$TIMEFILE

	return 0
}

#------------------------------------------------------------------------------
#	compares_file_in_targetdir()
#	compares files in source , target directory	
#	args :	$1 , source directory
#			$2 , target directory	
#
#	2005.11.24	new by kotori
#------------------------------------------------------------------------------
compares_file_in_targetdir()
{
	local	checkOK=0
	local	scdir=$1
	local	tgdir=$2

	ERROR_FLAG=0

	for i in `ls -1 $scdir`
	do

		####	check symbolic link
		if [ -h "$scdir/$i" ] ; then
			continue
		fi
		if [ -d "$scdir/$i" ] ; then
			continue
		fi

		for j in `ls -1 $tgdir`
		do
			if [ "$i" = "$j" ]; then
				cmp $scdir/$i $tgdir/$j
				if [ $? -eq 0 ];then
					ERROR_FLAG=0
					checkOK=1
					break
				else
					echo "UD_SH > failed to copy - unmach file $scdir/$i $tgdir/$j : cfit1"
					ERROR_FLAG=1
					return 1
				fi
			fi
		done

		if [ $checkOK -eq 0 ] ; then
			echo "UD_SH > failed to copy - $scdir/$i not be copyed to $tgdir/$j : cfit2"
			ERROR_FLAG=1
			return 1
		fi

	done

	return 0
}

#------------------------------------------------------------------------------
# copy factory.tar, backup.tar, and F/Ws to partition 2
#------------------------------------------------------------------------------
# - argument
#   $1: directory name
# - return
#   0: normal
#   others: error
#
copy_under_dir_file_to_p2()
{
	ERROR_FLAG=0
	local source_dir=""
	local target_dir=""

	case $1 in
		*factory*)
			source_dir=$P2_FACTORY
			;;
		*backup*)
			source_dir=$P2_BACKUP
			;;
		*)
			echo "UD_SH > $1 is unknown file name"
			ERROR_FLAG=1
			return $errInvalidFileP2
			;;
	esac

	target_dir=$2/$source_dir

	if [ -d "$target_dir" ] ; then
		# Change mode before Updater overwrite/erase files
		chown -R root $target_dir
		chmod -R 755 $target_dir
	fi

	func_recordTime "copy_underDir_file_to_p2 - FlashCpy - $sourceDir started." $RAMDSK_PATH/$TIMEFILE

	case $source_dir in
		*backup)
			echo "UD_SH > backup.tar process"

			if [ -d "$MNT_TARGET2/$P2_BACKUP" ] ; then
				busybox cp -a $source_dir/* $target_dir
			else
				busybox cp -a $source_dir $target_dir
			fi

			if [ $? -ne 0 ] ; then
				ERROR_FLAG=1
				return $errFirmUpP2;
			fi
			;;

		*factory)
			echo "UD_SH > factory.tar process"

			if [ -d "$MNT_TARGET2/$P2_FACTORY" ] ; then

				if [ -f "$MNT_TARGET2/$P2_FACTORY/Areg.bin" ] ; then

					echo "UD_SH > Areg.bin found."

					rm $source_dir/Areg.bin
					rm $source_dir/Areg2.bak
					rm $source_dir/Hreg.bin
					rm $source_dir/Hreg2.bak

				fi

				if [ -f "$MNT_TARGET2/$P2_FACTORY/.hasp" ] ; then

					echo "UD_SH > haspfile found."
					rm $source_dir/.hasp

				else
					echo "UD_SH > haspfile Not found."

					busybox cp -a $source_dir/.hasp $target_dir

					if [ $? -ne 0 ] ; then
						ERROR_FLAG=1
						return $errFirmUpP2;
					fi

				fi

				busybox cp -a $source_dir/*.* $target_dir

				if [ $? -ne 0 ] ; then
					ERROR_FLAG=1
					return $errFirmUpP2;
				fi

			else

				busybox cp -a $source_dir $target_dir

				if [ $? -ne 0 ] ; then
					ERROR_FLAG=1
					return $errFirmUpP2;
				fi

			fi
			;;
		*)
		ERROR_FLAG=1
		return $errInvalidFileP2
		;;
	esac

	func_remnt 0 $DEVICE2 $MNT_TARGET2

	if [ $? -ne 0 ] ; then
		echo "UD_SH > failed to re-mount : cudftp22"
		ERROR_FLAG=1
		return $errRemntP2
	fi

	func_recordTime "copy_underDir_file_to_p2 - diff started." $RAMDSK_PATH/$TIMEFILE

	compares_file_in_targetdir $source_dir $target_dir

	if [ $? -eq 0 ];then
		ERROR_FLAG=0
		echo "UD_SH > OK , all copy diff $source_dir/ $target_dir/"
	else
		ERROR_FLAG=1
		echo "UD_SH > failed to copy - unmach file $source_Dir $target_Dir : cudftp21"
		return $errVerifyP2
	fi

	busybox rm -r $source_dir 2>/dev/null

	busybox rm $1

	return 0
}

#------------------------------------------------------------------------------
# copy file into partition 2
#------------------------------------------------------------------------------
# - argument
#   $1: file name
# - return
#   0: normal
#   others: error
#
func_copy_to_p2()
{
	ERROR_FLAG=0
	local i=$1
	local ret=0

	check_archive_maxsize $i
	if [ $? -eq 0 ] ;then

		tar -xf $i
		if [ $? -eq 0 ] ;then
			copy_under_dir_file_to_p2 $i $MNT_TARGET2
			ret=$?
			if [ $ret -ne 0 ] ; then
				echo "UD_SH > failed to copy, archive file is $i : fctp22"
				ERROR_FLAG=1
				return $ret
			fi
		else
			echo "UD_SH > failed to extract, archive file is $i : fctp23"
			ERROR_FLAG=1
			return $errTarCmdP2
		fi

	else
		echo "UD_SH > failed to copy, archive file $i is OVER SIZE: fctp24"
		ERROR_FLAG=1
		busybox rm $i
		return $errMaxTarFileSizeP2
	fi

	return 0
}

#------------------------------------------------------------------------------
# copy file into partition 3
#------------------------------------------------------------------------------
# - argument
#   $1: file name
# - return
#   0: normal
#   others: error
#
func_copy_to_p3()
{
	ERROR_FLAG=0
	local i=$1

	check_archive_maxsize $i
	if [ $? -eq 0 ] ;then

		tar -xf $i
		if [ $? -eq 0 ] ;then
			parse_copy_current
			return $?
		else
			echo "UD_SH > failed to extract, may be broken archive $i : fctp31"
			ERROR_FLAG=1
			busybox rm $i
			return $errTarCmdP3
		fi

	else

		echo "UD_SH > failed to copy, archive file $i is OVER SIZE: fctp32"
		ERROR_FLAG=1
		busybox rm $i
		return $errMaxTarFileSizeP3
	fi

	return 0
}

#------------------------------------------------------------------------------
# copy file into partition 5
#------------------------------------------------------------------------------
# - argument
#   $1: file name
# - return
#   0: normal
#   others: error
#
func_copy_to_p5()
{
	ERROR_FLAG=0
	local i=$1
	local ret=0

	copy_file_to_nflash $i $MNT_TARGET5 $DEVICE5
	ret=$?
	if [ $ret -ne 0 ] ; then
		echo "UD_SH > failed to copy, binary file is $i : fctp51"
		ERROR_FLAG=1
		return $ret
	fi

###	set owner and permission : 060516 takeo-t
	chown root $MNT_TARGET5/$i
	chmod 755 $MNT_TARGET5/$i

	return 0
}

#------------------------------------------------------------------------------
# copy file into partition 6
#------------------------------------------------------------------------------
# - argument
#   $1: file name
# - return
#   0: normal
#   others: error
#
func_copy_to_p6()
{
	ERROR_FLAG=0
	local i=$1

	check_archive_maxsize $i
	if [ $? -eq 0 ] ;then

		tar -xf $i
		if [ $? -eq 0 ] ;then
			copy_micon1_usr_p6 $i
			return $?
		else
			echo "UD_SH > failed to extract, may be broken archive $i : fctp61"
			ERROR_FLAG=1
			busybox rm $i
			return $errTarCmdP6
		fi
	else

		echo "UD_SH > failed to copy, archive file $i is OVER SIZE: fctp62"
		ERROR_FLAG=1
		busybox rm $i
		return $errMaxTarFileSizeP6
	fi

	return 0
}

#------------------------------------------------------------------------------
# func_getmode
#------------------------------------------------------------------------------
func_getmode()
{
	if [ -f $MODE_PATH/$SFWMODE ]; then

		return $eUpModeSvc
	else

		if [ -f $MODE_PATH/$FWMODE ]; then

			k=`cat $MODE_PATH/$FWMODE`

			case $k in
				$INIT_PROD)
					return $eUpModeProd
					;;

				$INIT_DVLP)
					return $eUpModeDvlp
					;;

				*)
					return $eUpModeUser
					;;
			esac
		else

			return $eUpModeUser
		fi
	fi
}


#------------------------------------------------------------------------------
# The Loader2 and the Loader3 are updated
#------------------------------------------------------------------------------
# - argument
#   $1: file name
# - return
#   0: success
#   others: error
#
func_copy_loader()
{
	check_archive_maxsize $1
	if [ $? -ne 0 ] ;then
		echo "[UD_SH] ER_PHASE: failed to place archive file into $1 is over size"
		return $errMaxTarFileSizeP1
	fi

	tar -xvf $1

	if [ $? -eq 0 ] ;then

		echo "[UD_SH] ER_PHASE: extracted archive file($1)"

		# check md5sum value
		busybox md5sum -c -s ./$ChkMd5Name

		if [ $? -eq 0 ]; then

			echo "[UD_SH] ER_PHASE: MD5 sum OK ($1)"

			for i in `ls -1 $RAMDSK_PATH/*.bin`
			do
				case $i in
				*Loader2*)
					Loader2_Name=$i
					;;
				*Loader3*)
					Loader3_Name=$i
					;;
				*)
					;;
				esac
			done

			pformat "$Loader2_Name" "$Loader3_Name"

			if [ $? -eq 0 ] ;then
				echo "[UD_SH] ER_PHASE: OK, formated one-nand flash"
			else
				echo "[UD_SH] ER_PHASE: failed to pformat for one-nand flash"
				return $errPFORMAT
			fi

			rm $ChkMd5Name

		else
			echo "[UD_SH] ER_PHASE: failed to readfile ($1) - MD5 SUM Err"
			return $errMd5Sum
		fi

	else
		echo "[UD_SH] ER_PHASE: failed to extract archive file($1)"
		return $errTarCmdP1
	fi

	rm $1

	return 0
}

#------------------------------------------------------------------------------
# to test compare
#------------------------------------------------------------------------------
# - argument
#   none
# - return
#   0: success
#   1: failure
#   
to_test_comp()
{
	to_test 10 2 > $RAMDSK_PATH/to_test_log.txt

	if [ $? -ne 0 ]; then
		echo "[UD_SH] failed to to_test"
		echo ""
		echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
		echo "[UD_SH] failed to to_test                        "
		echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
		echo ""
		return 1
	fi

	cat $RAMDSK_PATH/to_test_log.txt | sed -e "/^initial.*$/d" > $RAMDSK_PATH/to_test_log1.txt
	cat $RAMDSK_PATH/to_test_log1.txt | sed -e "/^acquired.*$/d" > $RAMDSK_PATH/to_test_log2.txt
	cmp $RAMDSK_PATH/to_test_log2.txt $RAMDSK_PATH/$TO_TEST_DEFINE_FILE

	if [ $? -eq 0 ]; then
		echo "[UD_SH] OK; to_test compare $TARGET_PATH/$TO_TEST_DEFINE_FILE to $RAMDSK_PATH/to_test_log.txt"
	else
		echo "[UD_SH] failed to to_test compare $TARGET_PATH/$TO_TEST_DEFINE_FILE to $RAMDSK_PATH/to_test_log.txt"
		echo ""
		echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
		echo "[UD_SH] failed to to_test compare                "
		echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
		echo ""
		return 1
	fi

	return 0
}

#------------------------------------------------------------------------------
# The Updater are updated
#------------------------------------------------------------------------------
# - argument
#   none
# - return
#   0: success
#   others: error
#   
func_copy_updater()
{
	local curDir=`pwd`
	local ret=0

	case $1 in
		*updater.tar)
			ChkUdMd5Name="chksum.md5"
			;;
		*updater2.tar)
			ChkUdMd5Name="dat1sum.md5"
			;;
		*)
			return 1
			;;
	esac

	check_archive_maxsize $1

	if [ $? -eq 0 ] ;then

		tar -xvf $1

		if [ $? -eq 0 ] ;then

			echo "[UD_SH] ER_PHASE: MD5 sum chk1 ($ChkUdMd5Name)"

			busybox md5sum -c -s ./$ChkUdMd5Name

			if [ $? -ne 0 ] ;then
				return $errMd5Sum
			fi

			echo "[UD_SH] ER_PHASE: MD5 sum OK ($1)"

			func_copy_dir_file_to_p1

			ret=$?

			if [ $ret -eq 0 ] ;then

				func_remnt 0 $DEVICE1 $MNT_TARGET1

				if [ $? -ne 0 ]; then
					return $errRemntP1
				else

					# check md5sum value
					cd $COPY_TARGET

					echo "[UD_SH] ER_PHASE: MD5 sum chk2 ($curDir/$ChkUdMd5Name)"

					busybox md5sum -c -s $curDir/$ChkUdMd5Name

					if [ $? -eq 0 ]; then
						echo "[UD_SH] ER_PHASE: MD5 sum OK (NAND)"
					else
						echo "[UD_SH] ER_PHASE: failed to readfile (NAND) - MD5 SUM Err"
						return $errMd5Sum
					fi
				fi
				cd $curDir
			else
				return $ret
			fi

		else
			echo "[UD_SH] ER_PHASE: failed to extract archive file, $1 was broken"
			rm $1
			return $errTarCmdP1
		fi
	else
		echo "[UD_SH] ER_PHASE: failed to place archive file into $DEVICE1, $tar_file_name is over size"
		return $errMaxTarFileSizeP1
	fi

	return 0
}

#------------------------------------------------------------------------------
# The file is copied in the directory subordinate of the flash of the P1
#------------------------------------------------------------------------------
# - argument
#   none
# - return
#   0: success
#   others: error
#   
func_copy_dir_file_to_p1()
{
	local ret=0

	for cfile in `ls -1`
	do
		case $cfile in
		vmlinux* | *initrd.img | *dat1)
			func_copy_to_p1_flash $cfile $MNT_TARGET1
			ret=$?
			if [ $ret -eq 0 ] ;then
				echo "[UD_SH] ER_PHASE: copied $cfile to one-nand flash"
			else
				echo "[UD_SH] ER_PHASE: failed to copy $cfile to one-nand flash"
				return $ret
			fi
			;;
		*)
			;;
		esac
	done

	return 0
}

#------------------------------------------------------------------------------
# The file is copied in the One NAND Flash of the Partition 1
#------------------------------------------------------------------------------
# - argument
#   $1: file name
# - return
#   0: success
#   others: error
#   
func_copy_to_p1_flash()
{
	case $1 in
	*vmlinux | *initrd.img )
		COPY_TARGET=$2$BOOT_TARGET
		if [ ! -d $COPY_TARGET ]; then
			mkdir -p $2$BOOT_TARGET 2>/dev/null
		else
			if [ -f "$COPY_TARGET/$1" ] ; then
				rm $COPY_TARGET/$1 2>/dev/null
			fi
		fi
		;;
	*)
		chown -R root $1
		COPY_TARGET=$2
		;;
	esac

	cp -a $RAMDSK_PATH/$1 $COPY_TARGET/

	if [ $? -ne 0 ]; then
		echo "[UD_SH] ER_PHASE: failed to copy $1 to $COPY_TARGET"
		return $errFirmUpP1
	fi

	sync

	#verify
	busybox cmp $RAMDSK_PATH/$1 $COPY_TARGET/$1
	if [ $? -ne 0 ]; then
		echo "[UD_SH] ER_PHASE: failed to verify $RAMDSK_PATH/$1 $COPY_TARGET/$1"
		return $errVerifyP1
	fi

	rm $RAMDSK_PATH/$1 2>/dev/null

	return 0
}


#------------------------------------------------------------------------------
# The flag is set to MBR
#------------------------------------------------------------------------------
# - argument
#   none
# - return
#   0: success
#   1: failure
#   
#	20071205 pformat2 comment out 
#

func_set_mbr_flag()
{
	local ret

#	pformat2 "$Loader2_Name" "$Loader3_Name"

#	if [ $? -eq 0 ] ;then
#		echo "[UD_SH] ER_PHASE: OK, pformat2"
#		ret=0
#	else
#		echo "[UD_SH] ER_PHASE: failed pformat2"
#		ret=1
#	fi

	ret=0

	rm $Loader2_Name
	rm $Loader3_Name

	return $ret
}

#------------------------------------------------------------------------------
# Omega FirmUpFile Make Process
#------------------------------------------------------------------------------
# - argument
#   none
# - return
#   0: success
#   others: error
#   
func_make_omega_firmup_modefile()
{
	case $eUpMode in
		$eUpModeProd | $eUpModeDvlp )
			if [ ! -f "$MODE_PATH/omg_prod_dvlp" ]; then

				touch $MODE_PATH/omg_prod_dvlp
				if [ ! -f "$MODE_PATH/omg_prod_dvlp" ]; then
					eError=$errOmgmodefile
					func_termination
				fi
				echo "[UD_SH][MK_OMG_FILE_PROC] omg_prod_dvlp file make success!!"
			
			fi
			
			if [ -f "$MODE_PATH/omg_usr_svc" ]; then
				rm -f $MODE_PATH/omg_usr_svc
				echo "[UD_SH][MK_OMG_FILE_PROC] omg_usr_svc file erase!!"
			fi
			
			if [ -f "$SEN_PATH/SMODE" ]; then
				rm -rf $SEN_PATH
				echo "[UD_SH][MK_OMG_FILE_PROC] sen mode file erase!!"
			fi
			;;
			
		$eUpModeUser | $eUpModeSvc )
			if [ -f "$MODE_PATH/omg_prod_dvlp" ]; then
				rm -f $MODE_PATH/omg_prod_dvlp
				echo "[UD_SH][MK_OMG_FILE_PROC] omg_prod_dvlp file erase!!"
			fi

			if [ ! -f "$MODE_PATH/omg_usr_svc" ]; then

				touch $MODE_PATH/omg_usr_svc
				if [ ! -f "$MODE_PATH/omg_usr_svc" ]; then
					eError=$errOmgmodefile
					func_termination
				fi
				echo "[UD_SH][MK_OMG_FILE_PROC] omg_usr_svc file make success!!"
			fi
			;;
	esac

	omega_firm_flg=0
}

#------------------------------------------------------------------------------
# Omega FirmUpFile Check Process
#------------------------------------------------------------------------------
# - argument
#   none
# - return
#   0: success
#   others: error
#   
func_check_omega_firmup_modefile()
{
	if [ -f "$MODE_PATH/omg_prod_dvlp" ]; then
		if [ $eUpMode -eq $eUpModeUser ] || [ $eUpMode -eq $eUpModeSvc ]; then
			rm -f $MODE_PATH/omg_prod_dvlp
			echo "[UD_SH][CHK_OMG_FILE_PROC] omg_prod_dvlp file erase!!"
		fi
	fi

	if [ -f "$MODE_PATH/omg_usr_svc" ]; then
		if [ $eUpMode -eq $eUpModeProd ] || [ $eUpMode -eq $eUpModeDvlp ]; then
			rm -f $MODE_PATH/omg_usr_svc
			echo "[UD_SH][CHK_OMG_FILE_PROC] omg_usr_svc file erase!!"
		fi
	fi
}

#------------------------------------------------------------------------------
# func_recordTime
#------------------------------------------------------------------------------
# arg $1 : Comment
# arg $2 : Time monitor file
func_recordTime()
{
	echo | date '+time:%Hh:%Mm:%Ss' >> $2
	echo -en "----------------> $1 \n" >> $2
}

#########################################################
#
#  U P D A T E R   P A R A M E T E R   D E F. 
#
#########################################################


#-------------------------------------------
# Updater Version
#-------------------------------------------
UdtrVer="00.40.00"

#-------------------------------------------
# mount target 
#-------------------------------------------
MNT_TARGET="/mnt"
MNT_TARGET1="/mnt1"
MNT_TARGET2="/mnt2"
MNT_TARGET3="/mnt3"
MNT_TARGET5="/mnt5"
MNT_TARGET6="/mnt6"

#-------------------------------------------
# one-nand device path
#-------------------------------------------
DEVICE1="/dev/nflasha1"
DEVICE2="/dev/nflasha2"
DEVICE3="/dev/nflasha3"
DEVICE5="/dev/nflasha5"
DEVICE6="/dev/nflasha6"

#-------------------------------------------
# Path definition
#-------------------------------------------
BOOT_TARGET="/boot"
STATFILE_PATH="/mnt2/updater"
SEN_PATH="/mnt2/sen"
DSC_PATH="/mnt2/dsc"
RAMDSK_PATH="/ramdsk"
SOURCE_ROOT="$RAMDSK_PATH"
MODE_PATH="/mnt2/updater"
DAT1_PATH="/mnt1"

SAVEADJ_DIRPATH="/saveadjust"
MODEFILE_DIRPATH="/mfile"
P2_FACTORY_PATH="/factory"

#-------------------------------------------
# Partition 2
#-------------------------------------------
P2_FACTORY="factory"
P2_BACKUP="backup"
P2_UPDATER="updater"
P2_MODULE1="sen"

#-------------------------------------------
# Partition 6
#-------------------------------------------
P6_BIN="bin"
P6_LIB="lib"
P6_FSK_APP="dsc/app"
P6_FSK_BIN_REL="dsc/fsk"
P6_FSK_BIN_DBG="dsc/fsk"
P6_FSK_FONT="dsc/fonts"

#-------------------------------------------
# command macro
#-------------------------------------------
CMD_MOUNT="busybox mount -t vfat -o posix_attr"
CMD_MOUNT_S="busybox mount -t vfat -o posix_attr -o sync"
CMD_MOUNT_BS="busybox mount -t vfat -o posix_attr -o batch_sync"
CMD_UMOUNT="busybox umount"

#-------------------------------------------
# file name 
#-------------------------------------------
SMODE="smode"
MODE="mode"
FWMODE="mode1"
SFWMODE="mode2"
CMDtoSH="c2s.dat"
PROGRES="progress"
PARTCNF="partinf.tbl"
DAT1="dat1"
PARTCNFBK="dat5"
MS_FILE_LIST="ms_file_list.txt"
TO_TEST_DEFINE_FILE="to_def.txt"
SUSPEND="suspend"

# file read from MS
GotFile="trans.dat"

# file carries Original Name of GotFile -> Reference "file list"
FileName="filename.nam"

# contents inf file
# - MUST be same to contents file name definition in "DecodeFirm.c" for MS read out
CntFile="cntent.dat"

# Header inf file
HdrFile="hdrInf.dat"

# time monitor
TIMEFILE="timemntr.txt"

# Loader/Updater.tar/md5 filename
ChkMd5Name="chksum.md5"
Loader2_Name="Loader2.bin"
Loader3_Name="Loader3.bin"

LOADER_TARFILENAME="loader.tar"
UPDATER_TARFILENAME="updater.tar"


#-------------------------------------------
# other definition
#-------------------------------------------
MARK_BUSY="busy"
MARK_FINI="finish"
INIT_SEN="UU"
INIT_PROD="prod"
INIT_DVLP="dvlp"

# using Power LED
LEDNUM=3

# Partition init must be done BEFORE file operation
LOADER_TARFILENUM=1
PART_INIT_FILENUM=4
NR_PART_INIT_FILENUM=1
UPDATER_TARFILENUM=5


# MAX tar-archive
MaxsizeTar=16384
DirName="busybox dirname"

# Phase number
wPhaseNum=0
wPhaseTerminate=9

#-------------------------------------------
# Enum Definition
#-------------------------------------------
# fixed error value
errNoError=00

errDatCntnt=1
errDatHead=2
errInvalidHead=3

errDatVersion=4
errDatModel=5
errDatRegion=6

errCheckVersion=7
errCheckModel=8
errCheckRegion=9

errRecordVersion=10
errRecordModel=11
errRecordRegion=12

errSaveVersion=13
errSaveModel=14
errSaveRegion=15

errRestoreVersion=16
errRestoreModel=17
errRestoreRegion=18

errPFORMAT=19
errPFORMAT2=20

errTOTEST=21
errLDWRCPADJ=22
errLDWRCPHASP=23
errLDREWRCPADJ=24
errLDREWRCPHASP=25

errFlashMnt=26
errFlashUmt=27
errFlashReMnt=28

errFirmUpFile=29
errDatIniPartFileOrder=30
errPartInit=38
errEdisx=39
errMakeModeFile=40
errMd5Sum=41
errLedCtrl=42

errFlashFmtP1=43
errMaxTarFileSizeP1=44
errTarCmdP1=45
errFirmUpP1=46
errRemntP1=47
errVerifyP1=48

errFlashFmtP2=49
errMaxTarFileSizeP2=50

#-- omega mode file error ---
errOmgmodefile=51

errTarCmdP2=58
errFirmUpP2=59
errRemntP2=60
errVerifyP2=65
errInvalidFileP2=66

errFlashFmtP3=67
errMaxTarFileSizeP3=68
errTarCmdP3=69
errFirmUpP3=70
errRemntP3=76
errVerifyP3=77

errFlashFmtP5=78
errFirmUpP5=79
errRemntP5=80
errVerifyP5=81

errFlashFmtP6=82
errMaxTarFileSizeP6=83
errTarCmdP6=84
errFirmUpP6=85
errRemntP6=86
errVerifyP6=87
errInvalidFileP6=88
errInvalidFile=89

# Error result offset
errErrOffset=200

# Updater mode type definition
eUpModeUser=0
eUpModeSvc=1
eUpModeProd=2
eUpModeDvlp=3

#-------------------------------------------
# transfer file type definition
#-------------------------------------------
eFileTypeCont=0
eFileTypeHeader=1
eFileTypeFirm=2

#-------------------------------------------
# Global valiable init
#-------------------------------------------
# global error variable
eError=$errNoError

# Updater mode body init
# export eUpMode=eUpModeUser <- if you want to use this valiable as "Enviroment valiable" in child process, add "export"
eUpMode=$eUpModeUser

# fskrel catch flag
wFskrelDetect=0

#-------------------------------------------
# Number of file contained in firmware data
#-------------------------------------------
wNumFiles=0

#-------------------------------------------
# File number in progress
#-------------------------------------------
wCurFileNum=0

#-------------------------------------------
# Update file number
#-------------------------------------------
wUpdateFileStartNum=0
wMaxUpdateNumFiles=0
UPDATE_APP_FILE_START_NUM=4
UPDATE_FUL_FILE_START_NUM=8

#-------------------------------------------
# set-version information variables
#-------------------------------------------
dst_version=0
dst_model=0
dst_region=0

VERSION_LENGTH=4
MODEL_LENGTH=8
REGION_LENGTH=8

#-------------------------------------------
# AdjustDataSave flag
#-------------------------------------------
wAdjustDataSave=0
whaspDataSave=0
wudcpycnt=0

wUpdateType=0
wUpdateTypeApp=1
wUpdateTypeFull=2

wVideoOut=0
wNTSC=0
wPAL=1

#-------------------------------------------
# Omegafirm  flag
#-------------------------------------------
omega_firm_flg=0

#########################################################
#  
#  U P D A T E R   M A I N   P R O C D U R E  S T A R T
#  
#########################################################

#------------------------------------------------------------------------------
# 0. Initialize
#------------------------------------------------------------------------------
echo "UD_SH > $wPhaseNum. Initialize."

# Display Version Info
echo "== BodyUpdater Version ==============================="
echo "UD_SH > UdtrMain : $UdtrVer"
echo "======================================================"

#------------------------------------------------------------------------------
# start progress process
#------------------------------------------------------------------------------
ud_progress.sh 0

#------------------------------------------------------------------------------
# mkfsdos is executed because of trouble with the WON vis-a-vis P5 and P6.
#------------------------------------------------------------------------------
$CMD_MOUNT $DEVICE5 $MNT_TARGET5

if [ $? -ne 0 ]; then

	echo "UD_SH > failed to mounting $DEVICE5 on $MNT_TARGET5"

	mkdosfs -F 12 -s 32 $DEVICE5
	if [ $? -ne 0 ] ;then
		echo "[UD_SH] failed to make uvfat FS on $DEVICE5"
		eError=$errFlashFmtP5
		func_termination
	fi
fi

$CMD_MOUNT $DEVICE6 $MNT_TARGET6

if [ $? -ne 0 ]; then
	echo "UD_SH > failed to mounting $DEVICE6 on $MNT_TARGET6"

#	mkdosfs -F 12 -s 8 $DEVICE6
#	mkdosfs -F 16 -s 8 $DEVICE6
        mkdosfs -s 8 $DEVICE6
	if [ $? -ne 0 ] ;then
		echo "[UD_SH] failed to make uvfat FS on $DEVICE6"
		eError=$errFlashFmtP6
		func_termination
	fi
fi

$CMD_UMOUNT $MNT_TARGET5 2>/dev/null
$CMD_UMOUNT $MNT_TARGET6 2>/dev/null

#------------------------------------------------------------------------------
# Mount FlashPROM
#------------------------------------------------------------------------------
func_mntall 1 
if [ $? -ne 0 ]; then
	eError=$errFlashMnt
	func_termination
fi

#------------------------------------------------------------------------------
# The fact that early processing ends and enters into the main 
# processing of the fur wear is written to the progress file.
#------------------------------------------------------------------------------
func_mark_progres $MARK_BUSY

#------------------------------------------------------------------------------
# turn on LED (LED number is fixed to 3)
#------------------------------------------------------------------------------
ud_led -c 1 -n $LEDNUM
if [ $? -ne 0 ]; then
	echo "UD_SH > failed to turn on LED[ret=$?]"
	eError=$errLedCtrl
	func_termination
fi

#------------------------------------------------------------------------------
# create files for data transfer and initialize them
#------------------------------------------------------------------------------
echo "UD_SH > create files for data transfer and initialize them"
touch $RAMDSK_PATH/$FileName
touch $RAMDSK_PATH/$CMDtoSH
touch $RAMDSK_PATH/$TIMEFILE
echo -en "time:xxH:xxM:xxS \n----------------> comment \n" > $RAMDSK_PATH/$TIMEFILE
echo "" > $RAMDSK_PATH/$FileName
echo "" > $RAMDSK_PATH/$CMDtoSH
sync

#------------------------------------------------------------------------------
# 1. choose update mode
#------------------------------------------------------------------------------
let wPhaseNum=$wPhaseNum+1
echo "UD_SH > $wPhaseNum. choose update mode"
func_getmode
eUpMode=$?
echo "UD_SH > Updater Mode is $eUpMode"

#------------------------------------------------------------------------------
# 2. contents file phase
#------------------------------------------------------------------------------
let wPhaseNum=$wPhaseNum+1
echo "UD_SH > $wPhaseNum. contents file phase"

cd /$RAMDSK_PATH

func_get_contents_file

wNumFiles=$?

if [ $wNumFiles -gt $errErrOffset ]; then
	echo "UD_SH > Invalid contents file info"
	eError=$errDatCntnt
	func_termination
fi

echo "UD_SH > number of file contained in firmware is $wNumFiles"

#------------------------------------------------------------------------------
# 3. get header information file
#------------------------------------------------------------------------------
let wPhaseNum=$wPhaseNum+1
echo "UD_SH > $wPhaseNum. get header information file"

func_get_file $eFileTypeHeader $wCurFileNum
if [ $? -ne 0 ]; then
	echo "UD_SH > failed to get header information file from that"
	eError=$errDatHead
	func_termination
fi

#------------------------------------------------------------------------------
# 4. check model and region matching when it's User/Service mode
#------------------------------------------------------------------------------
let wPhaseNum=$wPhaseNum+1
echo "UD_SH > $wPhaseNum. check model and region matching when it's User/Service mode"

let wCurFileNum=$wCurFileNum+1

func_get_set_version
eError=$?
if [ $eError -ne 0 ] ; then
	echo "UD_SH > failed to get set-version"
	func_termination
fi

if [ $eUpMode -eq $eUpModeUser ] || [ $eUpMode -eq $eUpModeSvc ]; then
	echo "UD_SH > check model, region and version information."
	func_check_model_condition
	eError=$?
	if [ $eError -ne 0 ]; then
		echo "UD_SH > failed to update no enough condition [ret=$eError]"
		func_termination
	fi
fi

#------------------------------------------------------------------------------
# 5. initalize partition
#------------------------------------------------------------------------------
let wPhaseNum=$wPhaseNum+1
echo "UD_SH > $wPhaseNum. initalize partition"

func_get_file $eFileTypeFirm $wCurFileNum
if [ $? -ne 0 ]; then
	echo "UD_SH > failed to get header information file"
	eError=$errFirmUpFile
	func_termination
fi

if [ $GotFile = $PARTCNF ]; then
	wUpdateType=$wUpdateTypeApp
	wUpdateFileStartNum=$UPDATE_APP_FILE_START_NUM
	echo "UD_SH > Update firmware type application"
else
	wUpdateType=$wUpdateTypeFull
	wUpdateFileStartNum=$UPDATE_FUL_FILE_START_NUM
	echo "UD_SH > Update firmware type full"
fi

while [ $wCurFileNum -lt $wUpdateFileStartNum ]
do
	func_init_partition $GotFile
	wTmp=$?
	if [ $wTmp -ne 0 ] ; then
		eError=$wTmp
		func_termination
	fi

	k=`cat $RAMDSK_PATH/$FileName`
	busybox rm $RAMDSK_PATH/$k 2>/dev/null

	if [ $wUpdateType -eq $wUpdateTypeApp ] ; then
		break
	else
		if [ $wCurFileNum -eq 1 ] ; then
			let wCurFileNum=4
		else
			let wCurFileNum=$wCurFileNum+1
		fi
	fi

	func_get_file $eFileTypeFirm $wCurFileNum

	if [ $? -ne 0 ] ; then
		echo "UD_SH > failed to get header information file"
		eError=$errPartInit
		func_termination
	fi

done

# If there is a DSC folder in the partition no 2, 
# the file of the subordinate is deleted. 
# In addition, if there is no DSC folder, it draws up. 
func_p2_dsc_makedir

#------------------------------------------------------------------------------
# 6. get firmware file and write
#------------------------------------------------------------------------------
let wPhaseNum=$wPhaseNum+1
echo "UD_SH > $wPhaseNum. get firmware file and write"

wCurFileNum=$wUpdateFileStartNum

let wMaxUpdateNumFiles=$wNumFiles-1

while [ $wCurFileNum -lt $wNumFiles ]
do
	#-------------------------------
	# get file
	#-------------------------------
	echo "UD_SH > get firmware file($wCurFileNum/$wMaxUpdateNumFiles)"
	func_get_file $eFileTypeFirm $wCurFileNum
	if [ $? -ne 0 ]; then
		echo "UD_SH > failed to read firmware data file "
		eError=$errFirmUpFile
		func_termination
	fi

	#---------------------------------
	# write and compare firmware data 
	#---------------------------------
	func_data_write_verify
	fdwv_res=$?
	if [ $fdwv_res -ne 0 ] ; then
		echo "UD_SH > failed to write/verify firmware"
		eError=$fdwv_res
		func_termination
	fi

	#---------------------------------
	# display progress
	#---------------------------------
	if [ -f "$STATFILE_PATH/$PROGRES" ] ; then
		update_progress=`cat $STATFILE_PATH/$PROGRES`
		ud_progress.sh $update_progress
		echo "UD_SH > Update Progress ... $update_progress%"
	fi

	#-------------------------------
	# remove readout file
	#-------------------------------
	k=`cat $RAMDSK_PATH/$FileName`
	busybox rm $RAMDSK_PATH/$k 2>/dev/null

	#-------------------------------
	# increment file number
	#-------------------------------
	let wCurFileNum=$wCurFileNum+1

done

# make /etc folder
mkdir -p $MNT_TARGET2/etc
sync

#------------------------------------------------------------------------------
# 7. termination phase(data transfer phase was successfully)
#------------------------------------------------------------------------------
let wPhaseNum=$wPhaseNum+1
echo "UD_SH > $wPhaseNum. termination phase"

# then numerical information in header, do follow
func_record_set_version
eError=$?
if [ $eError -ne 0 ]; then
	echo "UD_SH > failed to record set-version [ret=$eError]"
	func_termination
fi

if [ $omega_firm_flg -eq 1 ]; then
	func_make_omega_firmup_modefile
else
	func_check_omega_firmup_modefile
fi

func_mark_progres $MARK_FINI
func_termination
