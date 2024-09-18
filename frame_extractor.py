import random
import re
import subprocess
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Optional, List
import click

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class FrameExtractor:
    def __init__(
        self,
        output_dir: Path,
        frames_per_video: int = 100,
        max_workers: int = 4,
        skip_start: int = 6,
        skip_end: int = 60,
        crop: bool = False,
        interval_jitter: Optional[int] = None,
    ) -> None:
        self.output_dir = output_dir
        self.frames_per_video = frames_per_video
        self.max_workers = max_workers
        self.skip_start = skip_start
        self.skip_end = skip_end
        self.crop = crop
        self.interval_jitter = interval_jitter

    def create_output_directory(self, name: str) -> Path:
        output_dir = self.output_dir / name
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    @staticmethod
    def get_framerate(video_path: Path) -> float:
        command = f'ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of default=noprint_wrappers=1:nokey=1 "{video_path}"'
        output = subprocess.check_output(command, shell=True, text=True).strip()
        num, denom = map(int, output.split("/"))
        return num / denom if denom else 1.0

    def get_crop_parameters(self, video_path: Path, timestamp: float) -> Optional[str]:
        command = [
            "ffmpeg",
            "-ss",
            str(timestamp),
            "-i",
            str(video_path),
            "-vf",
            "cropdetect=24:16:0",
            "-frames:v",
            "1",
            "-f",
            "null",
            "-",
        ]
        result = subprocess.run(command, shell=True, stderr=subprocess.PIPE, text=True)
        output = result.stderr
        match = re.search(r"crop=\d+:\d+:\d+:\d+", output)
        if match:
            return match.group(0)
        return None

    def extract_frame_with_crop(
        self, video_path: Path, output_file: Path, timestamp: float
    ) -> None:
        if self.crop:
            crop_params = self.get_crop_parameters(video_path, timestamp)
        else:
            crop_params = None
        if crop_params:
            command = [
                "ffmpeg",
                "-ss",
                str(timestamp),
                "-i",
                str(video_path),
                "-vf",
                crop_params,
                "-frames:v",
                "1",
                "-q:v",
                "1",
                str(output_file),
            ]
        else:
            command = [
                "ffmpeg",
                "-ss",
                str(timestamp),
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-q:v",
                "1",
                str(output_file),
            ]
        subprocess.run(
            command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
        )

    def extract_frames(self, video_path: Path, output_dir: Path) -> None:
        logging.info(f"Processing {video_path}")
        try:
            duration_cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{video_path}"'
            duration = float(subprocess.check_output(duration_cmd, shell=True).strip())
            framerate = self.get_framerate(video_path)
            duration -= self.skip_end
            if duration <= self.skip_start:
                logging.warning(
                    f"Skipping {video_path} because duration is too short after excluding start and end."
                )
                return
            interval = (duration - self.skip_start) / self.frames_per_video
            video_filename = video_path.stem
            for i in range(self.frames_per_video):
                timestamp = round(self.skip_start + interval * i, 3)
                if self.interval_jitter:
                    jitter = random.randint(-self.interval_jitter, self.interval_jitter)
                    timestamp = min(duration - 1, max(1, timestamp + jitter))
                output_file = (
                    output_dir
                    / f"{video_filename}_frame_{int(timestamp * framerate)}.jpg"
                )
                self.extract_frame_with_crop(video_path, output_file, timestamp)
        except Exception as e:
            logging.error(f"Error processing {video_path}: {e}")

    def process_video(
        self, input_dir: Path, limit: Optional[int] = None, random_sample: bool = False
    ) -> None:
        name = input_dir.name
        output_dir = self.create_output_directory(name)
        if output_dir.exists() and any(output_dir.iterdir()):
            logging.info(f"Skipping {name} as it already exists in {output_dir}")
            return
        logging.info(f"Processing: {name}")
        video_files: List[Path] = [
            f for f in input_dir.rglob("*") if f.suffix in {".mkv", ".mp4"}
        ]
        if limit is not None:
            video_files = video_files[:limit]
        if random_sample:
            video_files = random.sample(
                video_files, min(len(video_files), limit or len(video_files))
            )
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(self.extract_frames, video_file, output_dir)
                for video_file in video_files
            ]
            for future in as_completed(futures):
                future.result()


@click.command()
@click.option(
    "--output-dir",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Base directory to save extracted frames.",
)
@click.option(
    "--frames-per-video", default=100, help="Number of frames to extract per video."
)
@click.option("--max-workers", default=4, help="Maximum number of concurrent workers.")
@click.option(
    "--skip-start",
    default=6,
    help="Number of seconds to skip at the start of the video.",
)
@click.option(
    "--skip-end", default=60, help="Number of seconds to skip at the end of the video."
)
@click.option(
    "--limit",
    default=None,
    type=int,
    help="Limit the number of video files processed.",
)
@click.option(
    "--random-sample", is_flag=True, help="Randomly sample the videos if limit is set."
)
@click.option("--crop", is_flag=True, help="Detect and crop black bars.")
@click.option(
    "--interval-jitter",
    default=None,
    type=int,
    help="Adjust each interval timestamp by N seconds in range -interval_jitter to interval_jitter, e.g. -2 to 2, interval could be adjusted by -2, -1, 0, 1, 2 seconds.",
)
@click.argument(
    "input_dir", type=click.Path(exists=True, file_okay=False, path_type=Path)
)
def main(
    output_dir: Path,
    frames_per_video: int,
    max_workers: int,
    skip_start: int,
    skip_end: int,
    limit: Optional[int],
    random_sample: bool,
    crop: bool,
    interval_jitter: Optional[int],
    input_dir: Path,
) -> None:
    extractor = FrameExtractor(
        output_dir=output_dir,
        frames_per_video=frames_per_video,
        max_workers=max_workers,
        skip_start=skip_start,
        skip_end=skip_end,
        crop=crop,
        interval_jitter=interval_jitter,
    )
    extractor.process_video(input_dir, limit, random_sample)


if __name__ == "__main__":
    main()
