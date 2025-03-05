# Troubleshooting Guide

## Audio Device Issues

### ALSA Errors
If you see ALSA errors like:
```
ALSA lib confmisc.c:855:(parse_card) cannot find card '0'
ALSA lib conf.c:5178:(_snd_config_evaluate) function snd_func_card_inum returned error: No such file or directory
```

Try these solutions:

1. **Install ALSA utilities and check your devices:**
   ```bash
   # Install ALSA utilities
   sudo apt-get install alsa-utils
   
   # List recording devices
   arecord -l
   
   # List playback devices
   aplay -l
   ```

2. **Install PulseAudio tools:**
   ```bash
   # Debian/Ubuntu
   sudo apt-get install pulseaudio-utils
   
   # List PulseAudio sources
   pactl list sources
   ```

3. **Force use of PulseAudio:**
   If you're in a desktop environment, PulseAudio is likely the default sound server.
   Set this environment variable before running the script:
   ```bash
   export PULSE_SERVER=unix:/run/user/$(id -u)/pulse/native
   python main.py
   ```

4. **For WSL users:**
   WSL has limited audio device support. Consider using:
   - [WSLg](https://github.com/microsoft/wslg) for WSL 2 to enable audio
   - [PulseAudio for Windows](https://www.freedesktop.org/wiki/Software/PulseAudio/Ports/Windows/Support/)

5. **Try a virtual audio device:**
   ```bash
   # Install PulseAudio module-virtual-source
   sudo apt-get install pulseaudio
   
   # Create a virtual audio source
   pactl load-module module-null-sink sink_name=virtual_speaker
   pactl load-module module-virtual-source source_name=virtual_mic master=virtual_speaker.monitor
   
   # Set this as default
   export PULSE_SOURCE=virtual_mic
   ```

## Common Problems and Solutions

### No Audio Input Detected

If no audio input is detected:

1. **Check physical connection:**
   - Make sure your microphone is properly connected
   - Test it with another application

2. **Check permissions:**
   ```bash
   # Add yourself to the audio group
   sudo usermod -a -G audio $USER
   # Log out and back in for changes to take effect
   ```

3. **Check if microphone is muted:**
   ```bash
   # Start alsamixer
   alsamixer
   # Select your input device using F6
   # Make sure capture volume is up and not muted (MM)
   ```

### Whisper.cpp Errors

1. **Path to model files:**
   Make sure you have downloaded the model files and set the correct path in `config.py`.
   Update the whisper command in `transcriber.py` to include the full path.

2. **Missing dependencies:**
   Whisper.cpp requires certain libraries:
   ```bash
   sudo apt-get install libopenblas-dev
   ```

### Text Injection Issues

1. **Session Type Detection:**
   The application will automatically detect if you're using Wayland or X11 and use the appropriate tool:
   - Wayland: Uses wtype
   - X11: Uses xdotool
   - macOS: Uses AppleScript

   You can check your session type with:
   ```bash
   echo $XDG_SESSION_TYPE
   ```

2. **Installing Text Injection Tools:**
   - For Wayland sessions:
     ```bash
     sudo apt-get install wtype
     ```
   - For X11 sessions:
     ```bash
     sudo apt-get install xdotool
     ```
   
   The application should automatically select the correct tool based on your session type.
