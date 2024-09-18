# FrameExtractor

Extract frames from videos.

## Requirements

`ffmpeg` and `ffprobe` must be available in your `PATH`.

## Usage

```
Usage: frame_extractor.py [OPTIONS] INPUT_DIR

Options:
  --output-dir DIRECTORY      Base directory to save extracted frames.
                              [required]
  --frames-per-video INTEGER  Number of frames to extract per video.
  --max-workers INTEGER       Maximum number of concurrent workers.
  --skip-start INTEGER        Number of seconds to skip at the start of the
                              video.
  --skip-end INTEGER          Number of seconds to skip at the end of the
                              video.
  --limit INTEGER             Limit the number of video files processed.
  --random-sample             Randomly sample the videos if limit is set.
  --crop                      Detect and crop black bars.
  --interval-jitter INTEGER   Adjust each interval timestamp by N seconds in
                              range -interval_jitter to interval_jitter, e.g.
                              -2 to 2, interval could be adjusted by -2, -1,
                              0, 1, 2 seconds.
  --help                      Show this message and exit.
```
