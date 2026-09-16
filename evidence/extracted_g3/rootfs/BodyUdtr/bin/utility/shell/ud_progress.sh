#!/bin/busybox sh
SCRIPT_PATH="/usr/body/bin/ass/script"

	case $1 in
		100 )
		cat $SCRIPT_PATH/updater_script_finished > /dev/ud_fifo
		;;
		0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10)
		cat $SCRIPT_PATH/updater_script1 > /dev/ud_fifo
		;;
		1* )
		cat $SCRIPT_PATH/updater_script1 > /dev/ud_fifo
		;;
		2* )
		cat $SCRIPT_PATH/updater_script2 > /dev/ud_fifo
		;;
		3* )
		cat $SCRIPT_PATH/updater_script2 > /dev/ud_fifo
		;;
		4* )
		cat $SCRIPT_PATH/updater_script3 > /dev/ud_fifo
		;;
		5* )
		cat $SCRIPT_PATH/updater_script3 > /dev/ud_fifo
		;;
		6* )
		cat $SCRIPT_PATH/updater_script4 > /dev/ud_fifo
		;;
		7* )
		cat $SCRIPT_PATH/updater_script4 > /dev/ud_fifo
		;;
		8* )
		cat $SCRIPT_PATH/updater_script5 > /dev/ud_fifo
		;;
		9* )
		cat $SCRIPT_PATH/updater_script6 > /dev/ud_fifo
		;;
		err )
		cat $SCRIPT_PATH/updater_script_error > /dev/ud_fifo
		;;
		exit )
		echo exit > /dev/ud_fifo
		;;
		* )
		;;
	esac

