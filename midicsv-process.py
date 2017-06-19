#!/usr/bin/env python

import numpy
import sys
import subprocess

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
    
    def onTimeMillis(self, tempoMap):
        return tempoMap.millisAtTick(self.tick)
    
    def durationMillis(self, tempoMap):
        return tempoMap.millisAtTick(self.tick + self.duration) - self.onTimeMillis(tempoMap)
    
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
            self.onTimeMillis(tempoMap),
            self.duration,
            self.durationMillis(tempoMap),
            self.pitch,
            self.velocity,
            self.pitch,
            self.track)

class TempoEvent:
    tick   = 0
    millis = 0
    tempo  = 500000

class TempoMap:
    tpqn = 480 # ticks per quarter note
    tmap = []
    
    def addTempo(self, tick, tempo):
        tempoEvent = TempoEvent()
        tempoEvent.tick = tick
        tempoEvent.tempo = tempo
        tempoEvent.millis = self.millisAtTick(tick)
        self.tmap.append(tempoEvent)
    
    def tempoEventAtTick(self, tick):
        savedTempoEvent = TempoEvent()
        for tempoEvent in self.tmap:
            if tempoEvent.tick > tick:
                break
            savedTempoEvent = tempoEvent
        return savedTempoEvent
    
    def millisAtTick(self, tick):
        tempoEvent = self.tempoEventAtTick(tick)
        return tempoEvent.millis + ((tick - tempoEvent.tick)*tempoEvent.tempo)/(self.tpqn*1000)

rows = []
for file in sys.argv[1:]:
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
            tpqn = int(cells[5]) # set tickcells per quarter note
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
    rank = 0
    prevTick = onTicks[0]
    print "start_ticks,start_ms,dur_ticks,dur_ms,pitch,fullNoteOctave,part" # + ",order"
    for i, note in enumerate(notes):
        tick = onTicks[i]
        if tick != prevTick:
            rank += 1
        print note.toString(tempoMap) # + "," + str(rank)
        prevTick = tick
