#!/bin/sh

#„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª
# usb select port
#„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª
USBPORT_PATH=/var/usbport
PORT0='0'
PORT1='1'

help() {
        echo ""
        echo "Usage: usbport.sh [OPTION] [DATA]"
        echo ""
        echo "Options:"
        echo "        -s              set port select"
        echo "        -g              get port select"
        echo "Data:"
        echo "        body            selectPort body"
        echo "        cradle          selectPort cradle"
        echo "        default         default selectPort"
        exit 0
}

case $1 in
    "-s")
        case $2 in
            "body")
                sel=`expr $PORT0`
                ;;
            "cradle")
                sel=`expr $PORT1`
                ;;
            "default")
                rm -f $USBPORT_PATH
                exit 0
                ;;
            *)
                help
                exit 0
                ;;
        esac
        echo $sel > $USBPORT_PATH
        ;;
    "-g")
        if test -e $USBPORT_PATH;then
            fl=$(cut -c1, $USBPORT_PATH)
            case $fl in
                '0' | '1')
                    if [ $# -eq 1 ]; then
                        echo $fl
                    fi
                    exit $fl
                    ;;
                *)
                    if [ $# -eq 1 ]; then
                        echo "ff"
                    fi
                    exit 255
                    ;;
            esac
        
        else
            if [ $# -eq 1 ]; then
                echo "ff"
            fi
            exit 255
        fi
        ;;
    *)
        help
        ;;
esac

exit 0
#„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª„ª