#!/bin/sh
#------------------------------------------------------------------------------
# insmod drivers
#------------------------------------------------------------------------------
insmod /usr/body/lib/ipcm.ko
insmod /usr/body/lib/ipcm_pl320.ko
insmod /usr/body/lib/ipcm_dev.ko
#-------------------------------------------------------------------------------
insmod /usr/body/lib/cxd4108fb.ko
#-------------------------------------------------------------------------------
insmod /usr/body/lib/cxd4108kbd.ko
#-------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# define
#------------------------------------------------------------------------------
DAT1_PATH="/mnt1"
MODE_PATH="/mnt2/updater"
RAMDSK_PATH="/ramdsk"

FWMODE="mode1"
SFWMODE="mode2"
CMDtoSH="c2s.dat"
HdrFile="hdrInf.dat"
GotFile="trans.dat"
CntFile="cntent.dat"
FileName="filename.nam"
DAT1="dat1"

INIT_PROD="prod"
INIT_DVLP="dvlp"

MODEL_LENGTH=8

eUpModeUser=0
eUpModeSvc=1
eUpModeProd=2
eUpModeDvlp=3
eUpMode=$eUpModeUser

#------------------------------------------------------------------------------
# function
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# get updater mode
#------------------------------------------------------------------------------
# - argument
#   none
# - return
#   0: user
#   1: service
#   2: prod
#   3: develop
#
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
# get header file
#------------------------------------------------------------------------------
# - argument
#   none
# - return
#   0: normal
#   1: error
#
func_get_header()
{
	local L_res

	# goto ram disk path for data read out
	cd /$RAMDSK_PATH

	# file read
	case $eUpMode in
		$eUpModeUser | $eUpModeSvc)

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
		echo "UD_SH > failed to read from MS : frfm1"
		return 1
	fi

	# copy file name
	GotFile=`cat $RAMDSK_PATH/$CMDtoSH`

	# extract file name
	GotFile=`busybox basename $GotFile`

	# then clean the file
	echo "" > $RAMDSK_PATH/$CMDtoSH

	# rename it when necessary
	if [ $GotFile != $HdrFile ]; then
		mv $RAMDSK_PATH/$GotFile $RAMDSK_PATH/$HdrFile
	fi

	return 0
}

#------------------------------------------------------------------------------
# decode key file
#------------------------------------------------------------------------------
# - argument
#   none
# - return
#   0: normal
#   1: error
#
func_decode_key()
{
	if [ $eUpMode -eq $eUpModeUser ] || [ $eUpMode -eq $eUpModeSvc ]; then
		ud_datcnv -d -i $DAT1_PATH/$DAT1 -o /ramdsk/key.dat
		if [ $? -ne 0 ]; then
			return 1
		fi
	fi

	return 0
}

#------------------------------------------------------------------------------
# get model infomation
#------------------------------------------------------------------------------
# - argument
#   none
# - return
#   0: normal
#   1: error
#
func_get_model()
{
	local model_len
	local dst_model
	local src_model

	if [ $eUpMode -eq $eUpModeProd ] || [ $eUpMode -eq $eUpModeDvlp ]; then
		if [ ! -f "/mnt1/dat2"  ]; then
			echo "UD_SH > initial product updater"
			return 0
		fi
	fi

	dst_model=`sed -n -e 's/^model=\([0-9]\{8,\}\)/\1/p' /ramdsk/hdrInf.dat`
	if [ $? -ne 0 ]; then
		echo "UD_SH > get model failer."
		return 1
	fi

	if [ -n "$dst_model" ] ; then
		model_len=`busybox expr length $dst_model`
	else
		echo "UD_SH > get model failer."
		return 1
	fi

	if [ $model_len -ne $MODEL_LENGTH ] ; then
		return 1
	fi

	ud_datcnv -d -i /mnt1/dat2 -o tmp.dat -a
	if [ $? -ne 0 ]; then
		busybox rm -f tmp.dat
		echo "UD_SH > ud_datcnv failure"
		return 1
	fi

	src_model=`cat tmp.dat`
	if [ $dst_model -ne $src_model ]; then
		busybox rm -f tmp.dat
		echo "UD_SH > dst_model=$dst_model is not equal to src_model=$src_model"
		return 1
	fi

	busybox rm -f tmp.dat

	return 0
}

#------------------------------------------------------------------------------
# Main
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# 1. mount partition no 1
#------------------------------------------------------------------------------
busybox mount -t vfat -o posix_attr /dev/nflasha1 /mnt1

if [ $? -eq 0 ];then
	echo "mount /mnt1 success..."
else
	echo "mount /mnt1 failer..."
	exit 1
fi

#------------------------------------------------------------------------------
# 2. mount partition no 2
#------------------------------------------------------------------------------
busybox mount -t vfat -o posix_attr /dev/nflasha2 /mnt2

if [ $? -eq 0 ];then
	echo "mount /mnt2 success..."
else
	echo "mount /mnt2 failer..."
	exit 1
fi

#------------------------------------------------------------------------------
# 3. create work file
#------------------------------------------------------------------------------
touch $RAMDSK_PATH/$CMDtoSH
echo "" > $RAMDSK_PATH/$CMDtoSH

#------------------------------------------------------------------------------
# 4. get updater mode
#------------------------------------------------------------------------------
func_getmode
eUpMode=$?

#------------------------------------------------------------------------------
# 5. decode key file
#------------------------------------------------------------------------------
func_decode_key
if [ $? -eq 0 ];then
	echo "decode key success..."
else
	echo "decode key failer..."
	exit 1
fi

#------------------------------------------------------------------------------
# 6. get header file
#------------------------------------------------------------------------------
func_get_header
if [ $? -eq 0 ];then
	echo "get header success..."
else
	echo "get header failer..."
	exit 1
fi

#------------------------------------------------------------------------------
# 7. get model info
#------------------------------------------------------------------------------
func_get_model
if [ $? -eq 0 ];then
	echo "get model success..."
else
	echo "get model failer..."
	exit 1
fi

ud_basicUtil -p "/usr/body/bin/config/brew_cnf.bin 0x200fd800"

ud_basicUtil -f "0x213a2000 0x3fff"	#Asys.bin
ud_basicUtil -f "0x213ac800 0x3fff"	#Asys2.bak
ud_basicUtil -f "0x2139f800 0x27ff"	#Areg.bin
ud_basicUtil -f "0x213aa000 0x27ff"	#Areg2.bak

ud_basicUtil -f "0x213a6000 0x3fff"	#Ausr.bin
ud_basicUtil -f "0x213b0800 0x3fff"	#Ausr2.bak

ud_avldr -f /ramdsk/av_udtr.bin

ud_avldr -i /usr/body/bin/ass/img/updating

if [ -f "/mnt2/updater/PAL" ] ; then
	echo "ud_avldr mode PAL."
	ud_avldr -m 'p'
else 
	echo "ud_avldr mode NTSC."
	ud_avldr -m 'n'
fi


ud_graphic -n 7 &

rm -f /ramdsk/av_udtr.bin

busybox umount /mnt1

if [ $? -eq 0 ];then
	echo " umount /mnt1 success..."
else
	echo " umount /mnt1 failer..."
	exit 1
fi

busybox umount /mnt2

if [ $? -eq 0 ];then
	echo " umount /mnt2 success..."
else
	echo " umount /mnt2 failer..."
	exit 1
fi

exit 0
