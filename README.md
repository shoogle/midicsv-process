# midicsv-process
Process output of John Walker's [midicsv](http://www.fourmilab.ch/webtools/midicsv/) to get real-world timing information. Convert ticks to seconds, taking tempo changes into account.

## Usage

With a MIDI file ([midicsv](http://www.fourmilab.ch/webtools/midicsv/) must be installed and in `$PATH`)

```
./midicsv-process.py infile.mid > outfile.csv
```

With a CSV file created by [midicsv](http://www.fourmilab.ch/webtools/midicsv/)
```
./midicsv-process.py infile.csv > outfile.csv
```

## License 

Distributed under the MIT License (a.k.a. the "Expat License"). See [LICENSE.txt](LICENSE.txt).

## Copyright

Copyright (c) 2017 Peter Jonas.
