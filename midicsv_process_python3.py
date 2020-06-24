#!/usr/bin/env python3
"""
With [midicsv](https://www.fourmilab.ch/webtools/midicsv/) installed to $PATH,
parse MIDI file and format it into CSV useable for c82.net's
[Off the Staff](https://c82.net/blog/?id=75)
Usage (from command line):
python midicsv_process_python3 MID_OR_CSV_FILENAME OUTPUT_CSV_FILENAME
"""
import argparse
from io import BytesIO
import numpy as np
import pandas as pd
import pathlib
import subprocess
from typing import Dict, Sequence

NOTELETTERS = ["C","C","D","D","E","F","F","G","G","A","A","B"]
SHARPS = [ "","#", "","#", "", "","#", "","#", "","#", ""]


def open_file(input_file: str) -> pd.DataFrame:
    """
    Open the input_file and format it into a pandas DataFrame
    If input_file's extension is .mid/.midi/.kar, run it through midicsv to translate to .csv
    If input_file's extension is .csv, load it into the DataFrame
    """
    filepath: pathlib.Path = pathlib.Path(input_file).expanduser()
    if filepath.suffix in ('.mid', '.midi', '.kar'):
        return pd.read_csv(
            BytesIO(subprocess.check_output(["midicsv", filepath])),
            sep=r"\,\s",
            engine="python",
            names=['part', 'tick', 'type', 'tempo', 'pitch', 'velocity', 'time_signature'],
            encoding="iso-8859-1"
        )
    if filepath.suffix in ('.csv'):
        return pd.read_csv(
            filepath,
            sep=r"\,\s",
            engine="python",
            names=['part', 'tick', 'type', 'tempo', 'pitch', 'velocity', 'time_signature'],
            encoding="iso-8859-1"
        )
    raise NotImplementedError(
        f"File with extension {filepath.suffix} not supported, "
        "use (.mid/.midi/.kar/.csv)"
    )


def get_ticks_per_quarter_note(df: pd.DataFrame) -> int:
    """
    For this piece, get the number of ticks per quarter note, stored on the Header-type entry
    """
    return int(df.loc[df['type'] == 'Header', 'velocity'].values[0])


def get_tempos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parse the midicsv-transformed data to pull out and record tempo-type entries
    """
    return (
        df.loc[df['type'] == 'Tempo', ['tick', 'tempo']]
          .drop_duplicates()
          .set_index('tick')
          .loc[:, 'tempo']
          .astype(int)
    )


def get_notes(df: pd.DataFrame, tempos: pd.Series) -> pd.DataFrame:
    """
    Parse the midicsv-transformed data to pull out and record note-type entries
    """
    return (
        df
        # Get "on" notes
        .loc[(df['type'] == 'Note_on_c') & (df['velocity'].fillna(0).astype(int) != 0),
             ['part', 'tick', 'pitch', 'velocity']]
        .drop_duplicates()
        # Remove bad data
        .loc[lambda x: x['pitch'].astype(int) != 0]
        # Append something with null part/pitch/velocity for each tempo for tempo-filling
        .append(pd.DataFrame({'tick': tempos.index}))
        # Sort by tick and attach tempo to each tick (using fillna with ffill method)
        .sort_values('tick')
        .assign(tempo=lambda x: x['tick'].map(tempos).fillna(method='ffill'))
        # Get rid of the tempo-filling placeholders
        .dropna()
        # Resort to original order
        .sort_values(['part', 'tick'])
        # Cross-join all "off" notes for a part/pitch combo
        .merge(
            df.loc[(df['type'] == 'Note_off_c') | (df['velocity'].fillna(1).astype(int) == 0),
                   ['part', 'tick', 'pitch']],
            on=['part', 'pitch'],
            suffixes=('', '_off')
        )
        # Make sure the cross-joined dataframe is sorted
        .sort_values(['part', 'tick', 'tick_off'])
        # Determine how long is between each tick/tick_off pair
        .assign(dur_ticks=lambda x: x['tick_off'] - x['tick'])
        # Remove "off" ticks that occur before tick
        .loc[lambda x: x['dur_ticks'] > 0]
        # Only keep the first "off" tick, thus eliminating the cross-join
        .groupby(['part', 'tick', 'pitch', 'velocity', 'tempo'])
        .agg(
            tick_off=('tick_off', 'first'),
            dur_ticks=('dur_ticks', 'first')
        )
        # Get rid of tick_off column, since only dur_ticks is needed
        .drop(columns=['tick_off'])
        # Rename ticks to start_ticks
        .reset_index()
        .rename(columns={'tick': 'start_ticks'})
    )


def tick_to_time(ticks: pd.Series, tempo: pd.Series, ticks_per_quarter_note: int) -> pd.Series:
    """
    Translate ticks to seconds given the ticks_per_quarter_note conversion factor
    """
    return ticks * tempo / ticks_per_quarter_note / 1000000


def get_times(notes: pd.DataFrame, tempos: pd.Series, ticks_per_quarter_note: int) -> pd.DataFrame:
    """
    Parse the midicsv-transformed data to process timestamps
    """
    start_times = pd.DataFrame(
        {
            'tempo_starts': np.append(
                0, tick_to_time(np.diff(tempos.index), tempos[:-1].values, ticks_per_quarter_note)
            ).cumsum(),
            'tempo_ticks': tempos.index
        }
    )
    return (
        notes
        .assign(dur_secs=lambda x: tick_to_time(x['dur_ticks'], x['tempo'], ticks_per_quarter_note))
        .merge(start_times, left_on='start_ticks', right_on='tempo_ticks', how='outer')
        .assign(tick_index=lambda x: x['start_ticks'].fillna(x['tempo_ticks']))
        .sort_values('tick_index')
        .assign(tempo_starts=lambda x: x['tempo_starts'].fillna(method='ffill'))
        .assign(tempo_ticks=lambda x: x['tempo_ticks'].fillna(method='ffill'))
        .assign(
            start_secs=(
                lambda x: (
                    tick_to_time(x['start_ticks'] - x['tempo_ticks'],
                    x['tempo'],
                    ticks_per_quarter_note) + x['tempo_starts']
                )
            )
        )
        .dropna()
        .drop(columns=['tick_index', 'tempo_starts', 'tempo_ticks'])
    )


def get_note_names(pitch: pd.Series) -> pd.Series:
    """
    Parse the pitches to get note names
    """
    letters = ["C","C","D","D","E","F","F","G","G","A","A","B"]
    sharps = [ "","#", "","#", "", "","#", "","#", "","#", ""]
    return (
        pd.Series(
            [
                letters[x % 12] + str(int(x / 12) - 1) + sharps[x % 12] for x in pitch.astype(int)
            ],
            name='fullNoteOctave',
            index=pitch.index
        )
    )



def process_midicsv(df: pd.DataFrame) -> pd.DataFrame:
    """
    Process the midicsv-transformed data
    """
    ticks_per_quarter_note = get_ticks_per_quarter_note(df)
    tempos = get_tempos(df)
    notes = get_notes(df, tempos)
    times = get_times(notes, tempos, ticks_per_quarter_note)
    note_names = get_note_names(notes['pitch'])
    return (
        times
        .assign(fullNoteOctave=note_names)
        .astype({
            'start_ticks': int,
            'start_secs': float,
            'dur_ticks': int,
            'dur_secs': float,
            'pitch': int,
            'fullNoteOctave': str,
            'velocity': int,
            'part': int
        })
        .loc[:, ['start_ticks', 'start_secs', 'dur_ticks', 'dur_secs',
                 'pitch', 'fullNoteOctave', 'velocity', 'part']]
        .sort_values(['start_ticks', 'part'])
    )


if __name__ == "__main__":
    # Parse command line arguments to get input and output files
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file", help="input file (raw .mid or midicsv output .csv)")
    parser.add_argument("output_file", help="output filename (.csv format)")
    args = parser.parse_args()
    # Load the midicsv-transformed data as a pandas DataFrame
    df_input = open_file(args.input_file)
    # Process the midicsv to get a properly formatted CSV for use by c82.net's Off the Staff
    df_output = process_midicsv(df_input)
    # Save the DataFrame to output_file
    df_output.to_csv(args.output_file, index=False)
