#!/usr/bin/env python3
"""Generates build/Audio Processor User Guide.pdf -- the end-user guide.

Same structure and styling as the other HamProjects guides (Rig Deck's
build_user_guide.py). Screenshots come from docs/guide/, rendered by
scripts/guide_screens.py. The app's name is part of the file name on
purpose, so guides for different apps can sit in one folder.

Usage (from this project's root):
    python scripts/guide_screens.py     # only when the screen has changed
    python build_user_guide.py

Requires: pip install reportlab pillow (build-time only).
"""
from __future__ import annotations

import os

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (CondPageBreak, Image, KeepTogether, ListFlowable, ListItem,
                                Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

APP = "Audio Processor"
ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(ROOT, "build", f"{APP} User Guide.pdf")
SHOTS = os.path.join(ROOT, "docs", "guide")

ACCENT = colors.HexColor("#1565c0")
CALLOUT_BG = colors.HexColor("#fff3e0")
CALLOUT_BORDER = colors.HexColor("#e0a030")
NOTE_BG = colors.HexColor("#e8f0fe")
NOTE_BORDER = colors.HexColor("#8ab4f8")
TABLE_HEADER_BG = colors.HexColor("#eeeeee")
MUTED = colors.HexColor("#555555")
CONTENT_W = 7.2 * inch

styles = getSampleStyleSheet()
style_title = ParagraphStyle("GuideTitle", parent=styles["Title"], fontSize=26, leading=30, spaceAfter=2)
style_subtitle = ParagraphStyle("GuideSubtitle", parent=styles["Normal"], fontSize=11, leading=14,
                                textColor=MUTED, alignment=TA_CENTER, spaceAfter=14)
style_body = ParagraphStyle("GuideBody", parent=styles["Normal"], fontSize=10, leading=13, spaceAfter=5)
style_h2 = ParagraphStyle("GuideH2", parent=styles["Heading2"], fontSize=12.5, leading=14, textColor=ACCENT,
                          spaceBefore=8, spaceAfter=3)
style_h3 = ParagraphStyle("GuideH3", parent=styles["Heading3"], fontSize=10.5, leading=13,
                          textColor=colors.HexColor("#333333"), spaceBefore=5, spaceAfter=2)
style_bullet = ParagraphStyle("GuideBullet", parent=styles["Normal"], fontSize=9.5, leading=12)
style_note = ParagraphStyle("GuideNote", parent=styles["Normal"], fontSize=9.5, leading=13)
style_cell = ParagraphStyle("GuideCell", parent=styles["Normal"], fontSize=9, leading=11.5)
style_head = ParagraphStyle("GuideHead", parent=style_cell, fontName="Helvetica-Bold")
style_caption = ParagraphStyle("GuideCaption", parent=styles["Normal"], fontSize=8.5, leading=11,
                               textColor=MUTED, alignment=TA_CENTER, spaceBefore=2, spaceAfter=8)
style_code = ParagraphStyle("GuideCode", parent=styles["Code"], fontSize=8, leading=10.5,
                            backColor=colors.HexColor("#f4f4f4"), borderPadding=6, spaceBefore=4, spaceAfter=8)


def P(text, style=style_body):
    return Paragraph(text, style)


def bullets(items):
    return ListFlowable([ListItem(Paragraph(i, style_bullet), spaceAfter=2.5) for i in items],
                        bulletType="bullet", bulletFontSize=7, leftIndent=14, bulletOffsetY=1)


def numbered(items):
    return ListFlowable([ListItem(Paragraph(i, style_bullet), spaceAfter=4) for i in items],
                        bulletType="1", leftIndent=18)


def box(text, bg=NOTE_BG, border=NOTE_BORDER):
    return Table([[Paragraph(text, style_note)]], colWidths=[CONTENT_W],
                 style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("BOX", (0, 0), (-1, -1), 1, border),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                                   ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))


def warn(text):
    return box(text, CALLOUT_BG, CALLOUT_BORDER)


def table(rows, widths):
    data = [[Paragraph(c, style_head) for c in rows[0]]] + \
           [[Paragraph(c, style_cell) for c in r] for r in rows[1:]]
    return Table(data, colWidths=[w * inch for w in widths], repeatRows=1,
                 style=TableStyle([("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
                                   ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bbbbbb")),
                                   ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                   ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))


def img(name, width):
    path = os.path.join(SHOTS, name)
    w, h = PILImage.open(path).size
    return Image(path, width=width, height=width * h / w)


def shot(name, width=CONTENT_W, caption=None):
    parts = [img(name, width)]
    if caption:
        parts.append(Paragraph(caption, style_caption))
    return KeepTogether(parts)


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(0.65 * inch, 0.3 * inch, f"{APP} User Guide")
    canvas.drawRightString(LETTER[0] - 0.65 * inch, 0.3 * inch, f"Page {doc.page}")
    canvas.restoreState()


def build():
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    doc = SimpleDocTemplate(OUT_PATH, pagesize=LETTER, title=f"{APP} User Guide", author=APP,
                            topMargin=0.45 * inch, bottomMargin=0.55 * inch,
                            leftMargin=0.65 * inch, rightMargin=0.65 * inch)
    f = []
    f.append(P(f"{APP} User Guide", style_title))
    f.append(P("Filter and clean up audio from radios, microphones and other programs, for Windows",
               style_subtitle))
    f.append(Table([[""]], colWidths=[CONTENT_W], rowHeights=[1],
                   style=TableStyle([("LINEBELOW", (0, 0), (-1, -1), 1, colors.HexColor("#cccccc"))])))
    f.append(Spacer(1, 8))
    f.append(P(
        "Audio Processor takes audio from one or more inputs (a radio's USB audio, a microphone, or whatever "
        "another program is playing), mixes them, passes the mix through a <b>chain of processing blocks</b> that you "
        "choose and adjust, and plays the result on an output device. A <b>RECORD</b> function captures "
        "the raw input so you can replay the same stretch of audio through the chain while you adjust it."))
    f.append(shot("main.png", caption="A recorded clip looping through the SSB cleanup chain. Grey is the "
                                        "input, blue is the output: the carrier at 1.2 kHz has been notched "
                                        "out and everything outside the voice band is turned down."))

    # ---------------------------------------------------------------------
    f.append(P("Starting", style_h2))
    f.append(bullets([
        "Double-click the <b>Audio Processor</b> shortcut on the Desktop (it runs "
        "<i>build\\Audio_Processor.exe</i>). The window takes about ten seconds to appear.",
        "Nothing is heard until you press <b>START</b>.",
        "Your device choices, volume and the chain are remembered for next time.",
    ]))

    # ---------------------------------------------------------------------
    f.append(P("Quick Start", style_h2))
    f.append(numbered([
        "In <b>Audio devices</b>, choose the <b>Output</b> (where you listen).",
        "In the <b>Input mixer</b> at the bottom, switch <b>ON</b> the source you want to hear (one is on "
        "already the first time).",
        "Press <b>START</b>. The IN meter moves and you hear the input, unchanged.",
        "Click <b>+ Add block</b> and pick a block, or choose a ready-made chain from <b>Preset</b> "
        "(<i>SSB cleanup</i> or <i>CW narrow</i>).",
        "Move the sliders and listen. The spectrum shows the input in grey and the output in blue.",
    ]))
    f.append(Spacer(1, 4))
    f.append(warn("<b>Microphone + speakers = howl.</b> If the input is a microphone and the output is a "
                  "speaker near it, the sound feeds back. Tick <b>Mute</b>, turn the Volume down, or use "
                  "headphones."))

    # ---------------------------------------------------------------------
    f.append(CondPageBreak(3 * inch))
    f.append(P("Audio Devices", style_h2))
    f.append(shot("devices.png"))
    f.append(table([
        ["Control", "What it does"],
        ["Driver", "The Windows audio system used to reach the devices. Leave it on <b>WASAPI</b>. Try "
                   "<b>MME</b> or <b>DirectSound</b> only if a device will not open; they add delay and "
                   "MME cuts device names short."],
        ["Output", "Where the processed audio is played."],
        ["Rate", "The sample rate the processing runs at. <b>48000 Hz</b> suits everything. A lower rate "
                 "(16000 Hz) uses less processor but removes everything above half the rate."],
        ["Rescan", "Looks again for devices. Use it after plugging in a radio or sound card while the app "
                   "is open."],
        ["START / STOP", "Starts and stops the audio. Green while running."],
    ], [1.3, 5.9]))
    f.append(Spacer(1, 4))
    f.append(P("You can change the driver, output or rate at any time. If the audio is running it "
               "switches over straight away. Where the audio comes <i>from</i> is chosen in the Input "
               "mixer at the bottom of the window."))

    # ---------------------------------------------------------------------
    f.append(CondPageBreak(3 * inch))
    f.append(P("The Input Mixer", style_h2))
    f.append(shot("mixer.png", caption="One strip per source. Here a microphone and a radio are both ON and "
                                         "are being mixed; the radio is turned down by 6 dB."))
    f.append(P("The bottom of the window has one strip for every source the PC has. <b>Every strip that is "
               "switched ON is added together</b>, and that mix is what goes into the processing chain, "
               "what REC records and what the IN meter and the grey spectrum trace show. Switch one on "
               "for a single source, or several to combine them."))
    f.append(table([
        ["Part of a strip", "What it does"],
        ["Name", "The source. Hover over it for the full name. A radio connected by USB appears as "
                 "<i>USB Audio CODEC</i>; with two radios the number in front (11-, 12-) tells them apart. "
                 "Switch one on and watch its meter to see which radio it is."],
        ["ON", "Adds this source to the mix (green) or takes it out. It works while the audio is "
               "running. A source that is off is not opened at all."],
        ["Fader", "This source's level in the mix, shown in dB to the right. <b>+0 dB</b> is unchanged, "
                  "left is quieter, fully left is <b>off</b>, fully right is +12 dB."],
        ["Meter", "The level this source is contributing, after its fader."],
    ], [1.3, 5.9]))
    f.append(Spacer(1, 4))
    f.append(bullets([
        "<b>Microphones and radios</b> come first: every capture device Windows has.",
        "<b>PC playback: ...</b> strips follow, one for each output device. Each captures whatever any "
        "program is playing on that device. See <i>Processing Audio from Another Program</i>.",
        "The PC playback strip for the device chosen as <b>Output</b> is greyed out: capturing your own "
        "output would echo endlessly.",
        "A strip whose name turns <font color='#c62828'>red</font> could not be opened; hover over it for "
        "the reason. The other sources carry on.",
        "With every strip off there is no live input. That is fine for working on a recording or a WAV "
        "file.",
        "If the mix is too loud (the IN meter sits hard against the right), pull the faders down. Two "
        "sources at +0 dB add up to more than either alone.",
        "Which strips are on, and their fader positions, are remembered.",
    ]))

    # ---------------------------------------------------------------------
    f.append(CondPageBreak(3 * inch))
    f.append(P("Source and Recording", style_h2))
    f.append(shot("source.png", width=5.2 * inch))
    f.append(table([
        ["Control", "What it does"],
        ["LIVE", "Process the input mix (everything switched ON in the Input mixer). Lit blue when it is the "
                 "source."],
        ["PLAY CLIP", "Loop the clip (a recording or an opened WAV file) through the chain instead of the "
                      "live input. It starts from the beginning each time you press it and repeats until "
                      "you press LIVE or STOP."],
        ["&#9679; REC", "Record the <b>input mix, before any processing</b>. The button turns red and "
                        "counts the seconds. Press it again to stop."],
        ["Clip name and bar", "The clip's file name, length and sample rate; the bar shows the playback "
                              "position."],
        ["Open WAV...", "Load any WAV file as the clip."],
        ["Save processed...", "Run the whole clip through the chain as it is set now and save the result "
                              "as a new WAV file."],
    ], [1.5, 5.7]))
    f.append(P("Record, then adjust", style_h3))
    f.append(P("This is the easiest way to set up a chain, because you hear the same audio every time:"))
    f.append(numbered([
        "With the source switched ON in the Input mixer, press <b>&#9679; REC</b> (it starts the audio if needed). Record ten to "
        "thirty seconds of the signal you want to work on.",
        "Press the button again. The recording is saved in the <b>recordings</b> folder as "
        "<i>rec_date_time.wav</i> and immediately starts looping through the chain: <b>PLAY CLIP</b> "
        "lights up.",
        "Add blocks and move the sliders while it loops. Untick a block to hear the difference it makes.",
        "When it sounds right, press <b>LIVE</b> to use the same chain on the live input, and "
        "<b>Save as...</b> to keep it as a preset.",
        "To keep a cleaned-up copy of the recording, press <b>Save processed...</b>",
    ]))
    f.append(Spacer(1, 4))
    f.append(box("Recordings shorter than a tenth of a second are discarded. A recording in progress is "
                 "saved if you press STOP, change device or close the app."))

    # ---------------------------------------------------------------------
    f.append(P("Monitor", style_h2))
    f.append(shot("monitor.png", width=5.2 * inch))
    f.append(bullets([
        "<b>IN / OUT</b>: level meters for the input mix and for the processed output. The right-hand end is "
        "full scale. If OUT sits hard against the right, the output is clipping: lower a Gain, or add a "
        "Limiter as the last block.",
        "<b>Volume</b> and <b>Mute</b> affect only what you hear. They do not change the recording, the "
        "meters or a file saved with Save processed.",
        "<b>DSP load</b>: how much of the available time the chain is using. Keep it well under 100%.",
        "<b>dropouts</b>: how many times the output ran out of audio (heard as a click or gap). The odd "
        "one is normal; a steadily climbing count means the PC is too busy or the chain is too heavy.",
    ]))

    # ---------------------------------------------------------------------
    f.append(CondPageBreak(3 * inch))
    f.append(P("The Spectrum", style_h2))
    f.append(shot("spectrum.png"))
    f.append(bullets([
        "<b>Grey</b> is the input, <b>blue</b> is the output, measured over the same moment. Where blue is "
        "below grey the chain is removing something; where it is above, it is boosting.",
        "It opens showing 0 to 6 kHz. <b>Scroll the mouse wheel</b> over it to zoom the frequency scale "
        "and <b>drag</b> to move along it. Right-click and choose <i>View All</i> to see everything.",
        "The level scale runs from -120 dB to 0 dB (full scale).",
    ]))

    # ---------------------------------------------------------------------
    f.append(P("The Processing Chain", style_h2))
    f.append(shot("chain.png", caption="Audio flows through the panels from left to right."))
    f.append(Table([[img("panel.png", 2.6 * inch),
                     bullets([
                         "<b>+ Add block</b> adds a block at the right-hand end. The blocks are grouped "
                         "by type; hover over one for a description.",
                         "<b>Tick box</b> beside the name: untick to bypass the block without removing "
                         "it. Compare with and without.",
                         "The two <b>arrow buttons</b> move the block earlier or later in the chain. Order "
                         "matters.",
                         "The <b>X button</b> removes the block.",
                         "<b>Sliders</b> act immediately. For an exact value, type it in the box beside "
                         "the slider and press Enter.",
                         "With more blocks than fit, a scroll bar appears under the panels.",
                         "<b>Chain delay</b> (right) is the delay the blocks add, on top of the audio "
                         "devices' own delay.",
                     ])]], colWidths=[2.8 * inch, 4.4 * inch],
                   style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")])))
    f.append(P("Presets", style_h3))
    f.append(bullets([
        "<b>Preset</b> list: choose one to replace the current chain with it.",
        "<b>Save as...</b> saves the current chain under a name. Using an existing name replaces that "
        "preset.",
        "<b>BYPASS</b> skips the whole chain while it is lit red, so you hear (and see on the spectrum) "
        "the input unchanged. Click it on and off to compare with and without the chain.",
        "<b>Delete</b> removes the preset shown in the list. <b>Clear chain</b> removes every block (the "
        "audio then passes straight through).",
        "Two presets are supplied: <b>SSB cleanup</b> (band filter, auto notch, spectral noise reduction, "
        "AGC) and <b>CW narrow</b> (CW peak filter, LMS noise reduction, AGC).",
    ]))
    f.append(P("A sensible order", style_h3))
    f.append(P("Filters first, then notch and noise reduction, then AGC or compressor, with a Limiter last "
               "if you use one. Noise reduction works better on audio that has already been band-limited, "
               "and an AGC placed before a filter would react to noise the filter is about to remove."))

    # ---------------------------------------------------------------------
    f.append(CondPageBreak(4 * inch))
    f.append(P("The Blocks", style_h2))
    f.append(P("Filters", style_h3))
    f.append(table([
        ["Block", "Use it for", "Controls"],
        ["Band Filter", "Keeping only a range of frequencies, e.g. 300-2700 Hz for SSB speech.",
         "<b>Type</b>: band-pass, low-pass or high-pass. <b>Low cut</b> / <b>High cut</b>: the edges. "
         "<b>Steepness</b>: how sharply it cuts (1 gentle - 8 very sharp)."],
        ["Notch", "Removing one steady tone at a frequency you set: a carrier, a heterodyne, mains hum.",
         "<b>Frequency</b>: read it off the spectrum. <b>Sharpness (Q)</b>: higher = narrower notch that "
         "takes less of the wanted audio with it."],
        ["CW Peak Filter", "Picking out one CW signal.",
         "<b>Pitch</b>: the tone you listen to (match your radio's CW pitch). <b>Width</b>: narrower "
         "rejects more, but very narrow settings ring."],
    ], [1.2, 2.5, 3.5]))
    f.append(P("Adaptive", style_h3))
    f.append(table([
        ["Block", "Use it for", "Controls"],
        ["Auto Notch", "Removing steady tones automatically, wherever they are and however many. "
                       "<b>Do not use on CW</b>: it will remove the signal.",
         "<b>Filter length</b>: longer separates tones that are close together. <b>Delay</b>: raise it if "
         "speech sounds hollow. <b>Adapt speed</b>: higher catches a new tone sooner but disturbs speech "
         "more."],
        ["LMS Noise Reduction", "Reducing hiss behind CW and other steady signals. It helps speech less.",
         "<b>Filter length</b>, <b>Delay</b>, <b>Adapt speed</b> as above. <b>Leak</b>: higher removes "
         "more noise but dulls the signal. <b>Amount</b>: blend between untouched (0%) and fully "
         "processed (100%)."],
    ], [1.2, 2.5, 3.5]))
    f.append(CondPageBreak(1.6 * inch))
    f.append(P("Spectral", style_h3))
    f.append(table([
        ["Block", "Use it for", "Controls"],
        ["Spectral Noise Reduction", "Reducing steady background noise behind speech. It learns the noise "
                                     "level at each frequency by itself over about a second and a half, "
                                     "and keeps following it. Adds about 20 ms of delay.",
         "<b>Strength</b>: how readily it treats sound as noise. Too high sounds watery. <b>Max "
         "reduction</b>: the most it will turn the noise down; 10-15 dB sounds natural, more sounds "
         "processed."],
    ], [1.2, 2.5, 3.5]))
    f.append(P("Dynamics", style_h3))
    f.append(table([
        ["Block", "Use it for", "Controls"],
        ["AGC", "Keeping weak and strong signals at a similar loudness.",
         "<b>Target level</b>: the output level it aims for. <b>Max gain</b>: the most it will boost a "
         "weak signal (it also limits how far it brings up the noise between signals). <b>Attack</b>: how "
         "fast it turns down. <b>Decay</b>: how slowly it turns back up."],
        ["Compressor", "Evening out loudness within a signal.",
         "<b>Threshold</b>: level above which it acts. <b>Ratio</b>: how strongly (4 = a 4 dB rise comes "
         "out as 1 dB). <b>Attack</b> / <b>Release</b>. <b>Make-up gain</b>: restores the loudness lost."],
        ["Limiter", "A hard ceiling so nothing can overload the output. Put it last.",
         "<b>Ceiling</b>: the maximum level. <b>Release</b>: how fast it lets go."],
        ["Noise Gate", "Silencing the audio between transmissions, like a squelch.",
         "<b>Threshold</b>: level below which it closes. <b>Reduction</b>: how far it turns down when "
         "closed. <b>Open time</b>, <b>Hold</b> (stays open this long after the signal drops), <b>Close "
         "time</b>."],
    ], [1.2, 2.5, 3.5]))
    f.append(P("Tone", style_h3))
    f.append(table([
        ["Block", "Use it for", "Controls"],
        ["Parametric EQ", "Shaping the tone.",
         "<b>Low shelf</b> and <b>High shelf</b>: boost or cut everything below / above a frequency. "
         "<b>Mid 1</b> and <b>Mid 2</b>: boost or cut around a frequency; <b>Q</b> sets how narrow."],
        ["Gain", "A plain level change.", "<b>Gain</b> in dB."],
    ], [1.2, 2.5, 3.5]))

    # ---------------------------------------------------------------------
    f.append(CondPageBreak(3.5 * inch))
    f.append(P("Processing Audio from Another Program", style_h2))
    f.append(P("The <b>PC playback: ...</b> strips capture whatever is being played on an output device: an "
               "SDR program, a web receiver in a browser, a remote-control app. The audio then goes through "
               "the chain like any other input, and REC works too."))
    f.append(numbered([
        "Decide on two different output devices: one the other program plays to, and one you listen on.",
        "Make the other program play to the first device (in its own audio settings, or in Windows under "
        "<i>Settings &rarr; System &rarr; Sound &rarr; Volume mixer</i>).",
        "In Audio Processor choose <b>Output = the device you listen on</b>, switch <b>ON</b> the "
        "<b>PC playback: (that first device)</b> strip in the Input mixer, then START.",
    ]))
    f.append(Spacer(1, 4))
    f.append(warn("<b>The Output cannot also be captured.</b> The processed audio would be captured again "
                  "and echo endlessly, so the PC playback strip for the Output device is greyed out. To "
                  "capture that device, choose a different Output first."))
    f.append(Spacer(1, 4))
    f.append(bullets([
        "If the captured device is a real speaker, you will hear the unprocessed audio from it as well. "
        "Turn that speaker down at the speaker itself, or use a virtual audio cable as the in-between "
        "device.",
        "The USB Audio CODEC outputs are the radios' transmit audio inputs. Do not play other programs "
        "into them just to capture them.",
        "While nothing is playing, the dropouts counter may tick. That is silence arriving in bursts, not "
        "a fault.",
    ]))
    f.append(P("Sending the processed audio to another program", style_h3))
    f.append(P("To feed the processed audio into a program such as JTDX, WSJT-X or fldigi, install a virtual "
               "audio cable, choose it as the <b>Output</b> here and as the audio <b>input</b> in the other "
               "program."))

    # ---------------------------------------------------------------------
    f.append(CondPageBreak(3 * inch))
    f.append(P("Adding Your Own Blocks", style_h2))
    f.append(P("Every block is one small Python file. To add one, put the file in the <b>blocks</b> folder "
               "next to <i>Audio_Processor.exe</i> and restart. It appears under <b>+ Add block</b>, and its "
               "sliders are made automatically from the list of parameters in the file."))
    f.append(P("<b>blocks\\_template.py</b> is a complete working example. Copy it to a name without the "
               "leading underscore (files starting with an underscore are ignored) and edit it:"))
    f.append(P(
        "class Tremolo(Block):<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;name = \"Tremolo\"<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;category = \"Effects\"<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;params = [<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Param(\"rate\", \"Rate\", 0.5, 20, default=5, unit=\"Hz\"),<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Param(\"depth\", \"Depth\", 0, 100, default=50, unit=\"%\"),<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;]<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;def reset(self): ...&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# clear anything remembered between chunks<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;def configure(self, fs): ...&nbsp;# runs at start and whenever a slider moves<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;def process(self, x): ...&nbsp;&nbsp;&nbsp;&nbsp;# one chunk of samples in, same length out",
        style_code))
    f.append(bullets([
        "The audio arrives in small chunks. Anything the block must remember from one chunk to the next "
        "has to be kept on <i>self</i>, or the audio clicks at every chunk. The template shows how.",
        "If a block has an error while running, it is bypassed and its panel shows the reason in red. The "
        "audio carries on.",
        "If a file cannot be loaded at all, a message at start-up names the file and the error.",
    ]))

    # ---------------------------------------------------------------------
    f.append(P("Files", style_h2))
    f.append(P("Everything is kept next to <i>Audio_Processor.exe</i> (in the <b>build</b> folder):"))
    f.append(table([
        ["Item", "Contents"],
        ["recordings\\", "Recordings made with REC, named <i>rec_date_time.wav</i>. They are never deleted "
                         "automatically."],
        ["presets\\", "One file per saved preset."],
        ["blocks\\", "Your own block files, and the template."],
        ["settings.json", "The devices, volume and chain that were in use when the app was last closed."],
        [f"{APP} User Guide.pdf", "This guide."],
    ], [2.2, 5.0]))

    # ---------------------------------------------------------------------
    f.append(P("Good to Know", style_h2))
    f.append(bullets([
        "Processing is <b>mono</b>. A stereo input is mixed to one channel; the output is the same signal "
        "on left and right.",
        "Expect roughly a tenth of a second from input to output, more with Spectral Noise Reduction in the chain. "
        "That is fine for listening to received audio, but too long to listen comfortably to your own "
        "voice.",
        "Every input and the output keep their own time. The app absorbs the difference by "
        "occasionally dropping or padding a few milliseconds.",
    ]))

    # ---------------------------------------------------------------------
    f.append(CondPageBreak(3 * inch))
    f.append(P("Troubleshooting", style_h2))
    f.append(table([
        ["Symptom", "What to check"],
        ["No sound", "Is START green? Is <b>Mute</b> unticked and Volume up? Is the IN meter moving (if not, "
                     "nothing is ON in the Input mixer, or the source is silent)? Is the Output the device you are "
                     "listening to? Is the source LIVE when you expected the clip, or the other way round?"],
        ["IN meter moves but OUT does not", "A block is removing everything: untick blocks one at a time. "
                                            "Typical causes are a CW Peak Filter on the wrong pitch, a "
                                            "Noise Gate threshold set too high, or Auto Notch on a CW "
                                            "signal."],
        ["The blocks seem to do nothing", "Click <b>BYPASS</b> on and off. If the blue spectrum trace moves "
                                          "but the sound does not change, you are hearing the source by "
                                          "another route as well: the radio's own speaker, a captured "
                                          "speaker that is still turned up, or your own voice in the room. "
                                          "If neither changes, check that BYPASS is not lit, the block is "
                                          "ticked, and the setting is strong enough to hear: a band filter "
                                          "wider than the radio's own filter changes nothing."],
        ["Howling or squealing", "Microphone picking up the speakers. Mute, lower the Volume or use "
                                 "headphones."],
        ["A PC playback strip is greyed out", "It is the Output device, which cannot be captured. See "
                                                     "<i>Processing Audio from Another Program</i>."],
        ["\"Could not start audio\" or \"Input source failed\"", "The device is in use exclusively by another "
                                                                 "program, or was unplugged. Press Rescan, "
                                                                 "pick the device again, or try the MME "
                                                                 "driver."],
        ["A radio or sound card is missing from the list", "Press <b>Rescan</b>. If it is still missing, "
                                                           "Windows does not have it either: check the "
                                                           "cable and Windows Sound settings."],
        ["Clicks, gaps, dropouts counting up", "DSP load too high: remove a block (the two Adaptive blocks "
                                               "and Spectral Noise Reduction are the heaviest), or lower "
                                               "the Rate to 16000 Hz. Close other busy programs."],
        ["Sounds watery or robotic", "Spectral Noise Reduction is set too strong. Lower Strength or Max "
                                     "reduction."],
        ["Speech sounds hollow", "Auto Notch is working on the voice. Raise its Delay or lower Adapt speed."],
        ["Output distorted", "The OUT meter is at full scale. Lower the Gain, the AGC Target level or the "
                             "Compressor Make-up gain, or add a Limiter last."],
        ["PLAY CLIP and Save processed are greyed out", "There is no clip yet. Record one or use Open WAV."],
        ["A block's panel shows red text", "That block had an error and was bypassed. For your own block, "
                                           "the text is the error to fix; untick and re-tick to try again."],
    ], [2.3, 4.9]))
    doc.build(f, onFirstPage=footer, onLaterPages=footer)
    print("wrote", OUT_PATH)


if __name__ == "__main__":
    build()
