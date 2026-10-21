// usage: swift setprofile.swift <icc path | reset>   -- assigns a custom profile to the Xiaomi AirPlay display
import AppKit
import ColorSync
for s in NSScreen.screens where s.localizedName.contains("Xiaomi") {
  let id = s.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as! CGDirectDisplayID
  let uuid = CGDisplayCreateUUIDFromDisplayID(id)!.takeRetainedValue()
  let arg = CommandLine.arguments[1]
  let val: Any = arg == "reset" ? kCFNull! : URL(fileURLWithPath: arg) as CFURL
  let dict = [kColorSyncDeviceDefaultProfileID.takeUnretainedValue() as String: val,
              kColorSyncProfileUserScope.takeUnretainedValue() as String: kCFPreferencesCurrentUser] as CFDictionary
  let ok = ColorSyncDeviceSetCustomProfiles(kColorSyncDisplayDeviceClass.takeUnretainedValue(), uuid, dict)
  print(s.localizedName, "uuid", CFUUIDCreateString(nil, uuid)!, "set:", ok)
}
