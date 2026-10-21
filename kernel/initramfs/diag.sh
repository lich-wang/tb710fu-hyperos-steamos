#!/bin/sh
# diagnostic shell (USB NCM telnet), called by /init when the root fs is not usable
# TB710FU kShimC "Linux diagnostic" initramfs: no disk is touched.
echo; echo "===== TB710FU Linux diagnostic (kShimC) ====="; uname -a; cat /proc/cmdline; free -m
echo "--- fb:"; cat /proc/fb; echo "--- udc:"; ls /sys/class/udc
G=/sys/kernel/config/usb_gadget/g1
mount -t debugfs none /sys/kernel/debug 2>/dev/null
n=0; while [ $n -lt 30 ] && [ -z "$(ls /sys/class/udc 2>/dev/null)" ]; do sleep 1; n=$((n+1)); done
# dual-role USB: UCSI (pmic-glink) is a rootfs module, so force the device role here
for r in /sys/class/usb_role/*/role; do [ -e "$r" ] && echo device > "$r" 2>/dev/null; done
UDC=$(ls /sys/class/udc 2>/dev/null | head -1)
echo "udc after ${n}s: $UDC"
if [ -n "$UDC" ]; then
  mkdir -p $G; cd $G
  echo 0x1d6b > idVendor; echo 0x0104 > idProduct
  mkdir -p strings/0x409; echo TB710FU-diag > strings/0x409/product; echo kshim > strings/0x409/serialnumber
  mkdir -p functions/ncm.usb0 configs/c.1/strings/0x409; echo ncm > configs/c.1/strings/0x409/configuration
  ln -s functions/ncm.usb0 configs/c.1/; echo $UDC > UDC; cd /
  sleep 2; ifconfig usb0 172.16.42.1 netmask 255.255.255.0 up
  echo "start 172.16.42.2" > /tmp/udhcpd.conf; echo "end 172.16.42.10" >> /tmp/udhcpd.conf
  echo "interface usb0" >> /tmp/udhcpd.conf; echo "option subnet 255.255.255.0" >> /tmp/udhcpd.conf
  touch /tmp/udhcpd.leases; echo "lease_file /tmp/udhcpd.leases" >> /tmp/udhcpd.conf
  udhcpd /tmp/udhcpd.conf; telnetd -l /bin/sh
  echo "USB NCM up: telnet 172.16.42.1 (UDC $UDC)"
else
  echo "no UDC -- deferred devices:"
  cat /sys/kernel/debug/devices_deferred 2>/dev/null | cut -c1-150
  echo "-- usb/dwc/phy/glink dmesg:"
  dmesg | grep -i -E "dwc3|usb|eusb|phy|glink|repeater|spmi" | tail -25 | cut -c1-150
fi
echo "auto reboot in 600 s (touch /tmp/stay to keep running)"
i=0
while [ $i -lt 120 ]; do sleep 5; i=$((i+1)); [ -f /tmp/stay ] && i=0; done
echo "rebooting"; sync; reboot -f
