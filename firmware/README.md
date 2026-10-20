# ESP32-C3 sorting controller

The controller is configured for `COM7` at 115200 baud. Open the `firmware`
folder as the Arduino sketch; `firmware.ino` is the Arduino entry file and the
implementation is in `main_engine.ino`.

Arduino IDE settings:

* Board: **ESP32C3 Dev Module**
* Port: **COM7**
* Serial Monitor: **115200 baud**

Compile from PowerShell with the Arduino IDE bundled CLI:

```powershell
& "$env:LOCALAPPDATA\Programs\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe" `
  compile --fqbn esp32:esp32:esp32c3 firmware
```

Before uploading, disconnect pneumatic actuator power or isolate the relay
outputs. After upload, reconnect and test one output at a time from the local
dashboard.
