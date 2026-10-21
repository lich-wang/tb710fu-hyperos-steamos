# source: mount image partitions by offset. IMG, RO=1 for read-only
o=""; [ "${RO:-1}" = 1 ] && o="-r"
P1=$(losetup -f --show $o -o $((2048*512)) --sizelimit $((1048576*512)) $IMG)
P2=$(losetup -f --show $o -o $((1050624*512)) --sizelimit $((23623680*512)) $IMG)
P3=$(losetup -f --show $o -o $((24674304*512)) $IMG)
mkdir -p /b /r /h; mo=ro; [ "${RO:-1}" = 1 ] || mo=rw
mount -o $mo $P1 /b; mount -o $mo $P2 /r; mount -o $mo $P3 /h
