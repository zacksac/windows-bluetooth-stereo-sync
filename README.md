# windows-bluetooth-stereo-sync
Turn any  two bluetooth speakers into a synchronized stereo sound system on windows .

Download exe direct from release page . 
https://github.com/zacksac/windows-bluetooth-stereo-sync/releases/tag/v.1.0

1.  **Download the Driver:** [VB-Cable (Donationware)](https://vb-audio.com/Cable/)
2.  **Install:** Extract the zip, right-click `VBCABLE_Setup_x64.exe`, and select **"Run as Administrator"**.
3.  **Reboot:** Restart your computer to finalize the driver installation.
4.  Open the app select input source as Cable Output (VB-Audio vitrtual (In:16 Out:0)
5.  On windows sound set CABLE Input (VB Audio Virtual Cable) as default playback device .
6.  On app select the bluetooth speaker 1 and 2 you want to use adjust delay and click start to enjoy dual stereo sync sound .


---------------------------------------------------------------------------------------------------------------------------
For developers
1.  **Clone the repository:**
    ```bash
    git clone https://github.com/zacksac/windows-bluetooth-stereo-sync.git
    cd YOUR_REPO_NAME
    ```

2.  **Install Dependencies:**
    ```bash
    pip install sounddevice numpy
    ```
    *(Note: You must also have the [PortAudio](http://www.portaudio.com/) library installed, which usually comes with sounddevice).*

3.  **Run the App:**
    ```bash
    python split.py
    ```

### Building the EXE
To compile your own executable using PyInstaller:
```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --name "windows_bluetooth_stereo_sync" split.py
   
