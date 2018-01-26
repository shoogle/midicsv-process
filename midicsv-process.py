#!/usr/bin/env python

import numpy
import sys
import subprocess
import argparse

noteLetters  = ["C","C","D","D","E","F","F","G","G","A","A","B"]
sharps       = [ "","#", "","#", "", "","#", "","#", "","#", ""]

class NoteEvent:
    track    = 0
    tick     = 0
    pitch    = 64
    velocity = 127

    def __init__(self, track, tick, pitch, velocity):
        self.track    = track
        self.tick     = tick
        self.pitch    = pitch
        self.velocity = velocity

class Note:
    track    = 0
    tick     = 0
    pitch    = 64
    velocity = 127
    duration = 480

    def __init__(self, noteEvent_on, noteEvent_off):
        self.track    = noteEvent_on.track
        self.tick     = noteEvent_on.tick
        self.pitch    = noteEvent_on.pitch
        self.velocity = noteEvent_on.velocity
        self.duration = noteEvent_off.tick - noteEvent_on.tick

    def onTimeMicros(self, tempoMap):
        return tempoMap.microsAtTick(self.tick)

    def durationMicros(self, tempoMap):
        return tempoMap.microsAtTick(self.tick + self.duration) - self.onTimeMicros(tempoMap)

    def octave(self):
        return (self.pitch / 12) - 1

    def letter(self):
        return noteLetters[self.pitch % 12]

    def sharp(self):
        return sharps[self.pitch % 12]

    def fullNote(self):
        return "%s%s" % (self.letter(), self.sharp())

    def fullNoteOctave(self):
        return "%s%s%s" % (self.letter(), self.octave(), self.sharp())

    def toString(self, tempoMap):
        return "%s,%s,%s,%s,%s,%s,%s,%s" % (\
            self.tick,
            self.onTimeMicros(tempoMap)/1000000.0,
            self.duration,
            self.durationMicros(tempoMap)/1000000.0,
            self.pitch,
            self.fullNoteOctave(),
            self.velocity,
            self.track)

class TempoEvent:
    tick   = 0
    micros = 0
    tempo  = 500000

class TempoMap:
    tpqn = 480 # ticks per quarter note
    tmap = []

    def addTempo(self, tick, tempo):
        tempoEvent = TempoEvent()
        tempoEvent.tick = tick
        tempoEvent.tempo = tempo
        tempoEvent.micros = self.microsAtTick(tick)
        self.tmap.append(tempoEvent)

    def tempoEventAtTick(self, tick):
        savedTempoEvent = TempoEvent()
        for tempoEvent in self.tmap:
            if tempoEvent.tick > tick:
                break
            savedTempoEvent = tempoEvent
        return savedTempoEvent

    def microsAtTick(self, tick):
        tempoEvent = self.tempoEventAtTick(tick)
        return tempoEvent.micros + ((tick - tempoEvent.tick)*tempoEvent.tempo)/self.tpqn

parser = argparse.ArgumentParser()

parser.add_argument("files", nargs='+', help="path to input files")

modes = parser.add_mutually_exclusive_group()
modes.add_argument("-t", "--ticks", action="store_true", help="print total ticks for the file")
modes.add_argument("-d", "--duration", action="store_true", help="print total duration of the file in seconds")

args = parser.parse_args()

rows = []
for file in args.files:
    extension = file.split(".")[-1].lower()
    if extension == "csv":
        print >> sys.stderr, "File: " + file
        try:
            rows = open(file).read().splitlines()
        except:
            print "Couldn't open '" + file + "'. Does it exist?"
            continue
    elif extension == "mid" or extension == "midi" or extension == "kar":
        print >> sys.stderr, "File: " + file + " (via midicsv)"
        try:
            rows = subprocess.check_output(["midicsv", file]).splitlines()
        except:
            print "Couldn't open '" + file + "'. Does it exist? Is midicsv installed?"
            continue
    elif extension == "mscx" or extension == "mscz":
        print >> sys.stderr, "File: " + file + " (via mscore and midicsv)"
        try:
            tmpFile = "tmp-" + file + ".mid"
            subprocess.call(["bash", "-c", "mscore " + file + " -o " + tmpFile + " &>/dev/null"])
            rows = subprocess.check_output(["midicsv", tmpFile ]).splitlines()
            subprocess.call(["rm", tmpFile])
        except:
            print "Couldn't open '" + file + "'. Does it exist? Is mscore and midicsv installed?"
            continue
    else:
        print >> sys.stderr, "Ignoring: " + file + " (not a MIDI or CSV file)"
        continue
    tempoMap   = TempoMap()
    notes      = []
    noteEvents = []
    onTicks    = []
    # read MIDI events
    for i, row in enumerate(rows):
        cells = row.split(", ")
        track = int(cells[0])
        tick  = int(cells[1])
        type  =     cells[2]
        if type == "Header":
            tpqn = int(cells[5]) # set ticks per quarter note
            tempoMap.tpqn = tpqn
        elif type == "Tempo":
            tempo = int(cells[3])
            tempoMap.addTempo(tick, tempo)
        elif type == "Note_on_c":
            pitch    = int(cells[4])
            velocity = int(cells[5])
            noteEvents.append(NoteEvent(track, tick, pitch, velocity))
    # create notes by pairing noteOn and noteOff events
    for i, noteEvent_on in enumerate(noteEvents):
        if noteEvent_on.velocity == 0:
            continue
        for noteEvent_off in noteEvents[i:]:
            if noteEvent_off.velocity != 0 or noteEvent_off.track != noteEvent_on.track or noteEvent_off.pitch != noteEvent_on.pitch:
                continue
            note = Note(noteEvent_on, noteEvent_off)
            notes.append(note)
            onTicks.append(note.tick)
            break
    # sort notes by onTick
    notes = [x for (y,x) in sorted(zip(onTicks,notes))]
    onTicks.sort()
    if args.ticks or args.duration:
        finalNote = notes[-1]
        finalTick = finalNote.tick + finalNote.duration
        if args.ticks:
            print finalTick
        elif args.duration:
            print tempoMap.microsAtTick(finalTick)/1000000.0
    else: # print everything
        print "start_ticks,start_secs,dur_ticks,dur_secs,pitch,fullNoteOctave,velocity,part"
        for i, note in enumerate(notes):
            print note.toString(tempoMap)
