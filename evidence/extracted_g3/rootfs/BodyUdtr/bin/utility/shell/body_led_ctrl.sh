#!/bin/sh


echo "==========================================="
echo "body_led_ctrl.sh start"
echo "==========================================="
echo ""

while [ 1 ];
do
	# The counter is initialized.
	count=1

	# Until it becomes the frequency where the counter is appointed it repeats.
	while [ $count -le $eError ];
	do
		# LED of the port which corresponds it lights up.
		ud_led -c 1 -n $LEDNUM

		# 500ms it sleeps
		usleep 500000

		# LED of the port which corresponds it goes out.
		ud_led -c 0 -n $LEDNUM

		# 100ms it sleeps
		usleep 100000

		# The counter the increment is done.
		count=`busybox expr $count + 1`

	done

	# The time process which is appointed is stopped up to the next LED control.
	sleep 5

done
