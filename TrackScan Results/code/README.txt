TrackScan - how to re-run the analysis
1. Put all phyphox Excel exports (Accelerometer + Location sheets) in a folder called data/
2. pip install pandas numpy scipy openpyxl matplotlib
3. python3 trackscan.py data out eline.json     (processes every recording)
4. python3 finalize.py                          (ranks hotspots, draws the chart)
Outputs land in out/: TrackScan_hotspots.csv, TrackScan_chart.png, windows.csv, bins.csv
eline.json = LA Metro's published E Line track shape + stations (from their public GTFS feed)
stops_corridor.csv = LA Metro bus stop names near the line, used to label cross streets
