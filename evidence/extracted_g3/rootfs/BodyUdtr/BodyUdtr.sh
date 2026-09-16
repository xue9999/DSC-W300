#!/bin/sh

export PATH=/usr/body/bin/utility/command:/usr/body/bin/utility/shell:/usr/body/bin/utility/tool:$PATH
export LD_LIBRARY_PATH=/usr/body/lib:$LD_LIBRARY_PATH

LEDNUM=3

MODE_PATH="/mnt2/updater"

FWMODE="mode1"
SFWMODE="mode2"

INIT_PROD="prod"
INIT_DVLP="dvlp"

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
# Main
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
#  mount partition no 2
#------------------------------------------------------------------------------
busybox mount -t vfat -o posix_attr /dev/nflasha2 /mnt2

if [ $? -eq 0 ];then
	echo "mount /mnt2 success..."
else
	echo "mount /mnt2 failer..."
	exit 1
fi

#------------------------------------------------------------------------------
# get updater mode
#------------------------------------------------------------------------------
func_getmode
eUpMode=$?
echo "Get Updater Mode=$eUpMode"

busybox umount /mnt2

if [ $? -eq 0 ];then
	echo " umount /mnt2 success..."
else
	echo " umount /mnt2 failer..."
	exit 1
fi

cd /usr/body/bin/utility/shell

#------------------------------------------------
# Preparation for running body
#------------------------------------------------
cp ./body_preparation.sh /ramdsk
cd /ramdsk

sh ./body_preparation.sh

if [ $? -eq 0 ]; then

	echo "body_preparation.sh success..."

	cd /usr/body/bin/utility/shell

	#------------------------------------------------
	# Execute UdtrMain.sh
	#------------------------------------------------
	sh ./UdtrMain.sh

	if [ $? -eq 0 ]; then
	    echo "UdtrMain.sh success..."

		#------------------------------------------------
		# Power off
		#------------------------------------------------
	    echo "Now Updater Mode=$eUpMode"

		if [ $eUpMode -eq $eUpModeProd ] || [ $eUpMode -eq $eUpModeDvlp ]; then
			usleep 500000
			ud_pwrOff -p
		else
			

			busybox mount -t vfat -o posix_attr /dev/nflasha2 /mnt2

			if [ $? -eq 0 ];then
        			echo "mount /mnt2 success..."
			else
        			echo "mount /mnt2 failer..."
        			exit 1
			fi

			if [ -f "$MODE_PATH/omg_usr_svc" ]; then

				busybox umount /mnt2

				if [ $? -eq 0 ];then
        				echo " umount /mnt2 success..."
				else
        				echo " umount /mnt2 failer..."
        				exit 1
				fi

				usleep 500000
				ud_pwrOff -p
			else
				busybox umount /mnt2

				if [ $? -eq 0 ];then
        				echo " umount /mnt2 success..."
				else
        				echo " umount /mnt2 failer..."
        				exit 1
				fi

				ud_pwrOff -w &
				ud_pwrOff -o
			fi
		fi
	else
	    echo "UdtrMain.sh failure..."

		ud_pwrOff -w &
		ud_pwrOff -o
	fi
else
	echo "body_preparation.sh failure..."

	# Blink LED
	ud_led -b 190 -n $LEDNUM &

	# enter eternal loop
	while [ 1 ]
	do
		ash --login
	done
	exit 1
fi
