"""
modules/voice.py  —  Non-blocking voice command listener.

Fixes vs previous version:
  - Phrase table re-ordered: specific phrases BEFORE general ones
    (so "thicker brush" matches thick_up, not toggle_brush)
  - Single-word color catches added ("red", "blue", etc.)
  - Natural phrases added ("change color to red", "make it red")
  - toggle_brush removed (was overriding thickness commands)
  - 3D command table expanded with more natural phrases
  - No voice instruction text shown on screen
"""

from __future__ import annotations
import threading
import queue
import time
import sys
import os
from typing import Callable, Optional

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

try:
    import speech_recognition as sr
    _SR_AVAILABLE = True
except ImportError:
    _SR_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# IMPORTANT: ORDER MATTERS.
# Longer / more specific phrases must come BEFORE shorter ones.
# "thicker brush" must be checked before "brush" so it matches thick_up, not
# toggle_brush.  Single-word catches ("red") come last as a final fallback.
# ─────────────────────────────────────────────────────────────────────────────

VOICE_COMMANDS_2D = [
    # ── Colors (specific multi-word first, single-word last) ─────────────────
    (["change color to red",  "color to red",  "color red",  "set color red",
      "make it red",   "use red",   "paint red",   "switch to red"],   "color_red"),
    (["change color to blue", "color to blue", "color blue", "set color blue",
      "make it blue",  "use blue",  "paint blue",  "switch to blue"],  "color_blue"),
    (["change color to green","color to green","color green","set color green",
      "make it green", "use green", "paint green", "switch to green"], "color_green"),
    (["change color to white","color to white","color white","set color white",
      "make it white", "use white", "paint white"],                    "color_white"),
    (["change color to yellow","color to yellow","color yellow",
      "make it yellow","use yellow","paint yellow"],                   "color_yellow"),
    (["change color to orange","color to orange","color orange",
      "make it orange","use orange","paint orange"],                   "color_orange"),
    (["change color to purple","color to purple","color purple",
      "make it purple","use purple","paint purple"],                   "color_purple"),
    (["change color to cyan","color to cyan","color cyan",
      "make it cyan",  "use cyan",  "paint cyan"],                     "color_cyan"),

    # ── Canvas ────────────────────────────────────────────────────────────────
    (["clear the canvas", "clear canvas", "clear drawing", "clear everything",
      "erase everything", "erase all",   "start over",    "wipe clean",
      "clean the canvas", "new drawing"],                              "clear_canvas"),
    (["undo that", "undo last", "undo action", "go back", "undo"],    "undo"),
    (["save drawing", "save the drawing", "save image", "save file",
      "save this", "save"],                                            "save"),

    # ── Brush size (MUST come before the plain "brush" entry) ────────────────
    (["bigger brush", "larger brush", "increase brush", "thicker brush",
      "brush bigger",  "brush larger", "make brush bigger",
      "thicker",       "make thicker", "increase thickness",
      "make it thicker"],                                              "thick_up"),
    (["smaller brush", "thinner brush", "decrease brush", "reduce brush",
      "brush smaller",  "brush thinner","make brush smaller",
      "thinner",        "make thinner", "decrease thickness",
      "make it thinner"],                                              "thick_down"),

    # ── Eraser size (MUST come before plain "eraser") ────────────────────────
    (["bigger eraser",  "larger eraser",   "increase eraser",
      "eraser bigger",  "eraser larger"],                              "erase_up"),
    (["smaller eraser", "decrease eraser", "reduce eraser",
      "eraser smaller"],                                               "erase_down"),

    # ── Tool switch ───────────────────────────────────────────────────────────
    (["switch to eraser", "use the eraser", "use eraser",
      "eraser mode",      "eraser tool",    "eraser"],                 "toggle_eraser"),

    # ── AI snap ───────────────────────────────────────────────────────────────
    (["enable ai",    "turn on ai",    "ai on",  "snap on",
      "enable snap",  "shape snap on"],                                "snap_on"),
    (["disable ai",   "turn off ai",   "ai off", "snap off",
      "disable snap", "shape snap off"],                               "snap_off"),
    (["toggle ai",    "toggle snap"],                                  "snap_toggle"),

    # ── Single-word color fallbacks (last, after all multi-word) ─────────────
    (["red"],    "color_red"),
    (["blue"],   "color_blue"),
    (["green"],  "color_green"),
    (["white"],  "color_white"),
    (["yellow"], "color_yellow"),
    (["orange"], "color_orange"),
    (["purple"], "color_purple"),
    (["cyan"],   "color_cyan"),
]

VOICE_COMMANDS_3D = [
    # ── Object switching ──────────────────────────────────────────────────────
    (["switch to globe",    "show globe",    "globe",
      "object one",  "option one",   "option 1", "object 1",  "number 1"],  "obj_globe"),
    (["switch to sphere",   "show sphere",   "sphere",   "ball",
      "object two",  "option two",   "option 2", "object 2",  "number 2"],  "obj_sphere"),
    (["switch to cube",     "show cube",     "cube",     "box",
      "object three","option three", "option 3", "object 3",  "number 3"],  "obj_cube"),
    (["switch to pyramid",  "show pyramid",  "pyramid",
      "object four", "option four",  "option 4", "object 4",  "number 4"],  "obj_pyramid"),
    (["switch to cylinder", "show cylinder", "cylinder", "tube",
      "object five", "option five",  "option 5", "object 5",  "number 5"],  "obj_cylinder"),

    # ── Scale ─────────────────────────────────────────────────────────────────
    (["make it bigger",  "zoom in",  "scale up",   "bigger",
      "increase size",   "larger",   "grow",        "expand"],               "scale_up"),
    (["make it smaller", "zoom out", "scale down",  "smaller",
      "decrease size",   "shrink",   "reduce size", "compress"],             "scale_down"),

    # ── Reset ─────────────────────────────────────────────────────────────────
    (["reset everything", "reset all", "reset position",
      "go back to start", "start over","reset"],                             "reset"),

    # ── Quit ──────────────────────────────────────────────────────────────────
    (["quit viewer",  "exit viewer", "close viewer",
      "quit",         "exit",        "close",   "stop"],                     "quit"),
]


class VoiceCommandListener:
    """
    Background thread voice listener.
    Non-blocking poll() returns action strings — safe to call every frame.
    """

    def __init__(self,
                 mode: str = "2d",
                 callback: Optional[Callable[[str], None]] = None):
        self._mode      = mode.lower()
        self._callback  = callback
        self._stop_evt  = threading.Event()
        self._q: queue.Queue[str] = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self.available  = _SR_AVAILABLE
        self._last_text = ""
        self._cmd_table = (VOICE_COMMANDS_2D if self._mode == "2d"
                           else VOICE_COMMANDS_3D)

    def start(self) -> bool:
        if not _SR_AVAILABLE:
            print("[Voice] SpeechRecognition not installed.")
            print("        Run: pip install SpeechRecognition pyaudio")
            return False
        self._stop_evt.clear()
        self._thread = threading.Thread(
            target=self._listen_loop, daemon=True,
            name=f"Voice_{self._mode}"
        )
        self._thread.start()
        print(f"[Voice] Listening ({self._mode.upper()} mode) ...")
        return True

    def stop(self):
        self._stop_evt.set()

    def poll(self) -> Optional[str]:
        try:
            return self._q.get_nowait()
        except queue.Empty:
            return None

    def last_heard(self) -> str:
        return self._last_text

    def set_mode(self, mode: str):
        self._mode      = mode.lower()
        self._cmd_table = (VOICE_COMMANDS_2D if self._mode == "2d"
                           else VOICE_COMMANDS_3D)

    def _listen_loop(self):
        recognizer = sr.Recognizer()
        recognizer.energy_threshold         = 300
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold          = 0.5

        try:
            mic = sr.Microphone()
        except Exception as e:
            print(f"[Voice] Microphone error: {e}")
            return

        while not self._stop_evt.is_set():
            try:
                with mic as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.2)
                    audio = recognizer.listen(source, timeout=3, phrase_time_limit=5)
                text = recognizer.recognize_google(audio).lower().strip()
                self._last_text = text
                print(f"[Voice] Heard: '{text}'")
                self._dispatch(text)

            except sr.WaitTimeoutError:
                pass
            except sr.UnknownValueError:
                pass
            except sr.RequestError as e:
                print(f"[Voice] API error: {e}")
                time.sleep(2)
            except Exception as e:
                print(f"[Voice] Error: {e}")
                time.sleep(1)

    def _dispatch(self, text: str):
        """Match heard text against phrase table — first match wins."""
        for phrases, action in self._cmd_table:
            for phrase in phrases:
                if phrase in text:
                    print(f"[Voice] '{phrase}' → {action}")
                    self._q.put(action)
                    if self._callback:
                        self._callback(action)
                    return
        print(f"[Voice] No command matched: '{text}'")