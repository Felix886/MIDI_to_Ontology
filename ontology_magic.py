import numpy as np # linear algebra
import pandas as pd # data processing, CSV file I/O (e.g. pd.read_csv)
from music21 import converter, corpus, instrument, midi, note, chord, pitch, roman, stream, harmony
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
import re
from owlready2 import *


# Listing current data on our folder.
import os

midi_path = "MIDIs"

def open_midi(midi_path, remove_drums):
    # There is an one-line method to read MIDIs
    # but to remove the drums we need to manipulate some
    # low level MIDI events.
    mf = midi.MidiFile()
    mf.open(midi_path)
    mf.read()
    mf.close()
    if (remove_drums):
        for i in range(len(mf.tracks)):
            mf.tracks[i].events = [ev for ev in mf.tracks[i].events if ev.channel != 10]          

    return midi.translate.midiFileToStream(mf)

print('Please enter the name of a song:')
tune = str(input())
    
base_midi = open_midi('MIDIs/'+tune+'.mid', True)

def list_instruments(midi):
    partStream = midi.parts.stream()
    print("List of instruments found on MIDI file:")
    for p in partStream:
        aux = p
        print (p.partName)

#print(list_instruments(base_midi))

def extract_notes(midi_part):
    parent_element = []
    ret = []
    for nt in midi_part.flat.notes:        
        if isinstance(nt, note.Note):
            ret.append(max(0.0, nt.pitch.ps))
            parent_element.append(nt)
        elif isinstance(nt, chord.Chord):
            for pitch in nt.pitches:
                ret.append(max(0.0, pitch.ps))
                parent_element.append(nt)
    
    return ret, parent_element

def print_parts_countour(midi):
    fig = plt.figure(figsize=(12, 5))
    ax = fig.add_subplot(1, 1, 1)
    minPitch = pitch.Pitch('C10').ps
    maxPitch = 0
    xMax = 0
    
    # Drawing notes.
    for i in range(len(midi.parts)):
        top = midi.parts[i].flat.notes                  
        y, parent_element = extract_notes(top)
        if (len(y) < 1): continue
            
        x = [n.offset for n in parent_element]
        ax.scatter(x, y, alpha=0.6, s=7)
        
        aux = min(y)
        if (aux < minPitch): minPitch = aux
            
        aux = max(y)
        if (aux > maxPitch): maxPitch = aux
            
        aux = max(x)
        if (aux > xMax): xMax = aux
    
    for i in range(1, 10):
        linePitch = pitch.Pitch('C{0}'.format(i)).ps
        if (linePitch > minPitch and linePitch < maxPitch):
            ax.add_line(mlines.Line2D([0, xMax], [linePitch, linePitch], color='red', alpha=0.1))      

timeSignature = base_midi.getTimeSignatures()[0]
music_analysis = base_midi.analyze('key')
print("Music time signature: {0}/{1}".format(timeSignature.beatCount, timeSignature.denominator))
print("Expected music key: {0}".format(music_analysis))
print("Music key confidence: {0}".format(music_analysis.correlationCoefficient))
# for analysis in music_analysis.alternateInterpretations:
#     if (analysis.correlationCoefficient > 0.5):
#         print(analysis)


def note_count(measure, count_dict):
    bass_note = None
    for chord in measure.recurse().getElementsByClass('Chord'):
        # All notes have the same length of its chord parent.
        note_length = chord.quarterLength
        for note in chord.pitches:          
            # If note is "C5", note.name is "C". We use "C5"
            # style to be able to detect more precise inversions.
            note_name = str(note) 
            if (bass_note is None or bass_note.ps > note.ps):
                bass_note = note
                
            if note_name in count_dict:
                count_dict[note_name] += note_length
            else:
                count_dict[note_name] = note_length
        
    return bass_note
                
def simplify_roman_name(roman_numeral):
    # Chords can get nasty names as "bII#86#6#5",
    # in this method we try to simplify names, even if it ends in
    # a different chord to reduce the chord vocabulary and display
    # chord function clearer.
    ret = roman_numeral.romanNumeral
    inversion_name = None
    inversion = roman_numeral.inversion()
    
    # Checking valid inversions.
    if ((roman_numeral.isTriad() and inversion < 3) or
            (inversion < 4 and
                 (roman_numeral.seventh is not None or roman_numeral.isSeventh()))):
        inversion_name = roman_numeral.inversionName()
        
    if (inversion_name is not None):
        ret = ret + str(inversion_name)
        
    elif (roman_numeral.isDominantSeventh()): ret = ret + "M7"
    elif (roman_numeral.isDiminishedSeventh()): ret = ret + "o7"
    return ret
                
def harmonic_reduction(midi_file):
    chord_list = []
    ret = []
    temp_midi = stream.Score()
    temp_midi_chords = midi_file.chordify()
    temp_midi.insert(0, temp_midi_chords)    
    music_key = temp_midi.analyze('key')
    max_notes_per_chord = 4   
    for m in temp_midi_chords.measures(0, None): # None = get all measures.
        if (type(m) != stream.Measure):
            continue
        
        # Here we count all notes length in each measure,
        # get the most frequent ones and try to create a chord with them.
        count_dict = dict()
        bass_note = note_count(m, count_dict)
        if (len(count_dict) < 1):
            ret.append("-") # Empty measure
            continue
        
        sorted_items = sorted(count_dict.items(), key=lambda x:x[1])
        sorted_notes = [item[0] for item in sorted_items[-max_notes_per_chord:]]
        measure_chord = chord.Chord(sorted_notes)
        #print(measure_chord)

        # Convert the chord to the functional roman representation
        # to make its information independent of the music key.
        roman_numeral = roman.romanNumeralFromChord(measure_chord, music_key)
        ret.append(simplify_roman_name(roman_numeral))
        
        str_chord = str(harmony.chordSymbolFromChord(measure_chord))
        str_chord = str_chord.split(' ')[1][:-1]
        str_chord = str_chord.split('/')[0] #remove bass notes

        if 'power' in str_chord: #interpret power chords as minor chords
            str_chord = str_chord.split('power')[0]
            if '-' not in str_chord:
                str_chord += '-'

        # str_chord = str_chord.split('dim')[0] 
        # str_chord = str_chord.split('maj7')[0]
        # str_chord = str_chord.split('7')[0]
        # str_chord = str_chord.split('+')[0]
        # str_chord = str_chord.split('-')[0]
        # str_chord = str_chord.split('pedal')[0]
        # str_chord = str_chord.split('sus')[0]
        # str_chord = str_chord.split('add')[0]
        # str_chord = str_chord.split('ø')[0]
        #print(measure_chord)

        if str_chord == 'Chor':
            str_chord_test = (str(measure_chord).split(' ')[1])
            str_chord = str_chord_test.split()[0]
            str_chord = [x for x in str_chord][0]
            
        chord_list.append(str_chord)

    numeral_chords = []    


    #remove the inversions from the roman numerals
    for numeral in ret:
        numeral = ''.join([i for i in numeral if not i.isdigit()])
        numeral_chords.append(numeral)


    print()
    print('The following chords are played:',chord_list)
    print()
    print('From the chords of these root notes, the following progression follows:',numeral_chords)
    print()

    # Initializing text and pattern
    
    blues_pattern1 = ['I', 'ii']
    blues_pattern2 = ['vi', 'I', 'II']
    blues_pattern3 = ['VI', 'I', 'II']
    blues_pattern4 = ['vi', 'IV', 'V']
    blues_pattern5 = ['V', 'IV', 'I']
    blues_pattern6 = ['vi', 'IV', 'I']
    blues_pattern6 = ['I', 'vi', 'IV', 'V'] #doo woop
    blues_pattern7 = ['I', 'IV', 'V']
    blues_pattern8 = ['I', 'VI', 'ii', 'V']
    most_common1 = ['I', 'V', 'vi', 'IV'] #most commonly used progression in pop music {optimistic, dream like, joyful}
    most_common2 = ['V', 'vi', 'IV', 'I'] #{resolution, completion}
    most_common3 = ['IV', 'I', 'V', 'vi'] #{longing}
    most_common4 = ['I', 'V', 'VI', 'V']
    classic_jazz = ['ii', 'V', 'I'] #most common jazz progression 
    myxolidian = ['I', 'bVII', 'I'] #common harmonic technique
    myxolidian_flirt = ['I', 'bVII', 'IV', 'I']
    flamenco_pop = ['I', 'bVII', 'bVI', 'bVII']

    pattern=[blues_pattern1, blues_pattern2, blues_pattern3, blues_pattern4, blues_pattern5, 
             blues_pattern6, blues_pattern7, blues_pattern8, most_common1, most_common2, most_common3,
             most_common4, classic_jazz, myxolidian, myxolidian_flirt, flamenco_pop]


    # Iterating over the text to search for pattern
    matching_patterns = []

    for p in pattern:
        res = any(numeral_chords[idx: idx + len(p)] == p
            for idx in range(len(numeral_chords) - len(p) + 1))
        if res:
            matching_patterns.append(p)
            # print(p,' is present in the music piece!')


    print(matching_patterns)
    
            
    #data preparation for the ontology        
    temp_key = str(music_analysis)[0].upper() + str(music_analysis)[1:]
    ontology_key = (temp_key.replace(' ','').replace('m','M').replace('#','Sharp').replace('b','Flat'))
    print(ontology_key)
    

    #Ontology

    onto_path.append("C:/Users/frn690/Documents/Experiment22feb")
    onto = get_ontology("ChordProgression3.1.rdf").load()
    mo = get_namespace("http://purl.org/ontology/mo/")
    keys = get_namespace("http://purl.org/NET/c4dm/keys.owl#")
    mto = get_namespace("http://purl.org/ontology/mto/")

    #onto_key = exec(ontology_key)
    song_title = tune
    song_artist = str('TheBeatles')


    onto_song = mo.MusicalWork(song_title)
    onto_artist = mo.MusicArtist(song_artist)

    onto_key = keys.Key(ontology_key)
    onto_song.key.append(onto_key)
    onto_song.artist.append(onto_artist)

    for pattern in matching_patterns:
        onto_pattern = mto.HarmonicProgression(pattern)
        onto_song.commonProgression.append(onto_pattern)

    onto_time_signature = mto.TimeSignature("{0}/{1}".format(timeSignature.beatCount, timeSignature.denominator))
    onto_time_signature.hasLowerNumeral.append(timeSignature.denominator)
    onto_time_signature.hasUpperNumeral.append(timeSignature.beatCount)
    onto_song.timeSignature.append(onto_time_signature)

    onto.save()

    return ret
    
harmonic_reduction(base_midi)

