# XVoice 2.0 Roadmap

This document outlines potential features and enhancements planned for future releases of XVoice 2.0. These are based on anticipated user needs and technical possibilities.

## Completed

- ✅ **System-tray GUI** (PySide6) with a settings window and status icon —
  makes XVoice2 usable without the terminal.
- ✅ **AppImage packaging** with a first-run model-download screen — double-click
  install for non-technical users.
- ✅ **NVIDIA Parakeet engine** (local, ONNX Runtime) — high accuracy with inline
  punctuation and capitalization, no external LLM needed for basic formatting.
- ✅ **Auto-punctuation** — provided natively by Parakeet (no LLM required).
- ✅ **Wake-word activation** (session + prefix modes), replacing hotkeys with a
  fully hands-free model that also works over remote desktop (RDP/VNC).
- ✅ **Configurable wake/sleep phrases** — editable in the GUI Settings.
- ✅ **Microphone selection** in Settings (e.g. choose a USB mic).
- ✅ **Latency reduction** — model pre-warm at startup + tunable end-of-speech
  pause.
- ✅ **Non-speech rejection** — voicing/ZCR-based VAD plus a Whisper
  hallucination filter, so keyboard clicks and silence aren't transcribed.
- ✅ **Multilingual option** — Parakeet `nemo-parakeet-tdt-0.6b-v3` (~25 languages).

## High Priority Features

### Voice Commands Mode
- **Description**: Define custom voice commands that trigger specific actions (like "new paragraph", "delete that", "open browser")
- **Implementation**: Integrate pattern matching to detect commands and map them to keyboard shortcuts or scripts
- **Benefit**: Increases productivity by enabling hands-free control of applications

### Continuous Transcription Toggle
- **Description**: Switch easily between continuous listening and push-to-talk modes
- **Implementation**: Add command-line flag and runtime toggle via keyboard shortcut
- **Benefit**: Provides flexibility for different usage scenarios (meetings vs. dictation)

### Custom Hotkeys — superseded
- **Description**: User-configurable keyboard shortcuts to start/stop recording and control other functions
- **Note**: Largely superseded by the hands-free **wake-word** model (which also
  works over remote desktop, where a global hotkey would be captured by the
  client). A hotkey could still be offered as an optional trigger.
- **Benefit**: Improves user experience with personalized control scheme

### Transcription History
- **Description**: Save transcriptions to a local database with search and retrieval functionality
- **Implementation**: Add SQLite integration with timestamp, app context, and content
- **Benefit**: Creates searchable archive of all dictated content

## Medium Priority Features

### Specialized Domain Modes
- **Description**: Additional dictation modes optimized for specific domains (medical, legal, programming)
- **Implementation**: Domain-specific prompt templates and vocabulary enhancements for LLM formatting
- **Benefit**: Improves accuracy for specialized terminology and formatting conventions

### UI/GUI Interface — ✅ done
- **Description**: Simple graphical interface showing recording status, history, and settings
- **Implementation**: Delivered as a PySide6 system-tray app (`xvoice2-gui`) with a
  settings window. History view is still open.
- **Benefit**: Makes the application more accessible to non-technical users

### End-to-End Encryption
- **Description**: Secure transmission and processing of audio and text data when using cloud services
- **Implementation**: Add client-side encryption/decryption for network communications
- **Benefit**: Enhances privacy and security for sensitive dictation

### Language Support
- **Description**: Transcription in multiple languages beyond English
- **Implementation**: Integrate with multilingual Whisper models and provide language selection
- **Benefit**: Makes the tool useful for a global user base

## Future Enhancements

### Voice Profile Training
- **Description**: Adaptation to individual speech patterns and accents for improved accuracy
- **Implementation**: Create fine-tuning system for local Whisper models
- **Benefit**: Significantly improves accuracy for users with accents or speech patterns

### Translation Integration
- **Description**: Real-time translation of transcribed speech to different languages
- **Implementation**: Add translation API integration (local or cloud-based)
- **Benefit**: Enables cross-language communication and content creation

### Cloud Sync
- **Description**: Synchronize settings, voice profiles, and transcription history across multiple devices
- **Implementation**: Create lightweight sync service using standard protocols
- **Benefit**: Provides consistent experience across workstations

### Offline Mode Enhancements
- **Description**: Improve performance when running completely offline with local models
- **Implementation**: Optimize local model loading and processing for better speed
- **Benefit**: Makes the application more usable without internet connection

### Real-time Formatting Preview
- **Description**: See how text will be formatted by LLM before insertion into application
- **Implementation**: Add preview window showing before/after text with accept/reject options
- **Benefit**: Gives users control over automated formatting

### Auto-Punctuation — ✅ done
- **Description**: Improve punctuation insertion without relying on external LLM services
- **Implementation**: Provided natively by the Parakeet engine, which outputs
  punctuated, capitalized text locally with no LLM.
- **Benefit**: Faster punctuation with lower resource usage

### Speaker Identification
- **Description**: Differentiate between multiple speakers in recordings or meetings
- **Implementation**: Integrate diarization models to tag text with speaker identifiers
- **Benefit**: Creates useful transcripts from multi-person conversations

## Technical Improvements

### Performance Optimization
- Reduce latency in the transcription pipeline
- Implement streaming transcription for real-time feedback
- Optimize memory usage for long dictation sessions

### Cross-Platform Enhancements
- Improve Windows support
- Add mobile companion applications
- Create consistent experience across all platforms

### Developer Tools
- Extend test coverage to edge cases
- Add benchmarking tools for performance testing
- Create plugin system for community extensions

---

*Note: This roadmap is subject to change based on user feedback and technical feasibility. Features may be implemented in different order than listed.*