#!/bin/sh
# TB710FU: root = partition 2 of an NBD disk exported by the Mac (nbd-server in docker,
# export "steamos", port 10809) over the USB NCM link. The gadget, usb0 address and
# udhcpd set up here must survive switch_root: the rootfs keeps usb0 unmanaged and
# runs no USB gadget service of its own.
G=/sys/kernel/config/usb_gadget/g1
n=0; while [ $n -lt 30 ] && [ -z "$(ls /sys/class/udc 2>/dev/null)" ]; do sleep 1; n=$((n+1)); done
for r in /sys/class/usb_role/*/role; do [ -e "$r" ] && echo device > "$r" 2>/dev/null; done
UDC=$(ls /sys/class/udc 2>/dev/null | head -1)
[ -n "$UDC" ] || { echo "nbdroot: no UDC"; exit 1; }
mkdir -p $G; cd $G
echo 0x1d6b > idVendor; echo 0x0104 > idProduct
mkdir -p strings/0x409; echo TB710FU-steamos > strings/0x409/product; echo tb710fu > strings/0x409/serialnumber
mkdir -p functions/ncm.usb0 configs/c.1/strings/0x409; echo ncm > configs/c.1/strings/0x409/configuration
ln -s functions/ncm.usb0 configs/c.1/; echo $UDC > UDC; cd /
sleep 2; ifconfig usb0 172.16.42.1 netmask 255.255.255.0 up
mkdir -p /run/udhcpd
printf "start 172.16.42.2\nend 172.16.42.10\ninterface usb0\noption subnet 255.255.255.0\nlease_file /run/udhcpd/leases\n" > /run/udhcpd/conf
touch /run/udhcpd/leases; udhcpd /run/udhcpd/conf
echo "nbdroot: USB NCM up on $UDC, waiting for the Mac NBD server (172.16.42.x:10809)"
i=0
while [ $i -lt 120 ]; do
  # carrier stuck (seen 10/19): rebind the UDC once in a while
  if [ $((i % 20)) = 19 ] && [ "$(cat /sys/class/net/usb0/carrier 2>/dev/null)" != 1 ]; then
    echo "" > $G/UDC; sleep 1; echo $UDC > $G/UDC; sleep 2; ifconfig usb0 172.16.42.1 up
  fi
  # -b 512: the image has a 512-byte-sector MBR (busybox defaults to 4096 -> wrong partitions)
  # the Mac's address comes from our udhcpd (it may get .2 .. .10, e.g. its old lease .8)
  for h in 2 3 4 5 6 7 8 9 10; do
    nc -w 1 172.16.42.$h 10809 </dev/null 2>/dev/null | grep -q NBDMAGIC || continue
    nbd-client -b 512 -N steamos 172.16.42.$h 10809 /dev/nbd0 && { MAC=172.16.42.$h; break 2; }
  done
  sleep 1; i=$((i+1))
done
[ -b /dev/nbd0p2 ] || { sleep 2; blockdev --rereadpt /dev/nbd0 2>/dev/null; sleep 1; }
ls /dev/nbd0* 2>/dev/null
mkdir -p /newroot
mount -t ext4 -o rw,noatime /dev/nbd0p2 /newroot && [ -x /newroot/sbin/init ] || { echo "nbdroot: mount failed"; exit 1; }
echo "nbdroot: root on /dev/nbd0p2 from $MAC after ${i}s"
exit 0
