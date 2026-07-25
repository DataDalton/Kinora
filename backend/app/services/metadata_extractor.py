"""
File metadata extractor using ffprobe.
Extracts technical metadata and embedded tags from media files.
"""

import json
import subprocess
from typing import Optional, Dict, Any
from pathlib import Path


class MetadataExtractor:
    """Extracts metadata from media files using ffprobe."""

    VIDEO_EXTENSIONS = {
        ".mkv",
        ".mp4",
        ".avi",
        ".mov",
        ".wmv",
        ".flv",
        ".m4v",
        ".mpg",
        ".mpeg",
        ".m2ts",
        ".ts",
        ".webm",
    }

    AUDIO_EXTENSIONS = {
        ".flac",
        ".mp3",
        ".m4a",
        ".aac",
        ".ogg",
        ".opus",
        ".wav",
        ".wma",
        ".alac",
        ".ape",
        ".wv",
        ".dsf",
        ".dff",
    }

    def __init__(self, ffprobe_path: str = "ffprobe"):
        """
        Initialize metadata extractor.

        Args:
            ffprobe_path: Path to ffprobe executable (default: 'ffprobe' from PATH)
        """
        self.ffprobe_path = ffprobe_path

    def extract_metadata(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Extract metadata from media file using ffprobe.

        Args:
            file_path: Absolute path to media file

        Returns:
            Dictionary with extracted metadata or None if extraction fails
        """
        try:
            # Run ffprobe with JSON output
            cmd = [
                self.ffprobe_path,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                file_path,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=True)

            data = json.loads(result.stdout)
            return self._parse_ffprobe_output(data, file_path)

        except subprocess.TimeoutExpired:
            return None
        except subprocess.CalledProcessError:
            return None
        except json.JSONDecodeError:
            return None
        except Exception:
            return None

    def _parse_ffprobe_output(self, data: Dict[str, Any], file_path: str) -> Dict[str, Any]:
        """Parse ffprobe JSON output into structured metadata."""
        format_data = data.get("format", {})
        streams = data.get("streams", [])

        # Find video stream
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)

        # Find audio streams
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

        # Extract format tags (container-level metadata)
        tags = format_data.get("tags", {})

        # Normalize tag keys (ffprobe returns various casings)
        normalized_tags = {k.lower(): v for k, v in tags.items()}

        metadata = {
            "file_path": file_path,
            "file_name": Path(file_path).name,
            "file_size": int(format_data.get("size", 0)),
            "duration": float(format_data.get("duration", 0)),
            "format_name": format_data.get("format_name", ""),
            "bit_rate": int(format_data.get("bit_rate", 0)),
        }

        # Extract embedded title (many MKV/MP4 files have this)
        metadata["title"] = (
            normalized_tags.get("title") or normalized_tags.get("movie_name") or normalized_tags.get("show") or None
        )

        # Extract year from tags
        year_fields = ["year", "date", "creation_time", "release_date"]
        for field in year_fields:
            if field in normalized_tags:
                year_str = normalized_tags[field]
                # Extract 4-digit year
                import re

                year_match = re.search(r"(\d{4})", str(year_str))
                if year_match:
                    metadata["year"] = int(year_match.group(1))
                    break

        # Extract other useful tags
        metadata["description"] = normalized_tags.get("description") or normalized_tags.get("comment")
        metadata["genre"] = normalized_tags.get("genre")
        metadata["encoder"] = normalized_tags.get("encoder")

        # Video stream metadata
        if video_stream:
            pix_fmt = video_stream.get("pix_fmt")
            metadata["video"] = {
                "codec": video_stream.get("codec_name"),
                "codec_long": video_stream.get("codec_long_name"),
                "width": video_stream.get("width"),
                "height": video_stream.get("height"),
                "aspect_ratio": video_stream.get("display_aspect_ratio"),
                "frame_rate": self._parse_frame_rate(video_stream.get("r_frame_rate")),
                "bit_rate": int(video_stream.get("bit_rate", 0)),
                "profile": video_stream.get("profile"),
                "pix_fmt": pix_fmt,
                "color_transfer": video_stream.get("color_transfer"),
                "color_primaries": video_stream.get("color_primaries"),
                "color_space": video_stream.get("color_space"),
                "bit_depth": self._parse_bit_depth(pix_fmt),
                "dynamic_range": self._parse_dynamic_range(video_stream),
            }

            # Determine quality from resolution
            height = metadata["video"]["height"]
            if height:
                if height >= 2160:
                    metadata["quality"] = "2160p"
                elif height >= 1080:
                    metadata["quality"] = "1080p"
                elif height >= 720:
                    metadata["quality"] = "720p"
                elif height >= 480:
                    metadata["quality"] = "480p"
                else:
                    metadata["quality"] = f"{height}p"

        # Audio streams metadata
        if audio_streams:
            metadata["audio"] = []
            for audio in audio_streams:
                audio_info = {
                    "codec": audio.get("codec_name"),
                    "codec_long": audio.get("codec_long_name"),
                    "channels": audio.get("channels"),
                    "channel_layout": audio.get("channel_layout"),
                    "sample_rate": audio.get("sample_rate"),
                    "bit_rate": int(audio.get("bit_rate", 0)),
                    # Bit depth drives the lossless music tier. FLAC and ALAC report it
                    # in bits_per_raw_sample, PCM in bits_per_sample.
                    "bit_depth": self._parse_audio_bit_depth(audio),
                }

                # Extract language from stream tags
                stream_tags = audio.get("tags", {})
                normalized_stream_tags = {k.lower(): v for k, v in stream_tags.items()}
                audio_info["language"] = normalized_stream_tags.get("language")
                audio_info["title"] = normalized_stream_tags.get("title")

                metadata["audio"].append(audio_info)

        # Extract subtitle count
        subtitle_streams = [s for s in streams if s.get("codec_type") == "subtitle"]
        if subtitle_streams:
            metadata["subtitles"] = []
            for sub in subtitle_streams:
                sub_tags = sub.get("tags", {})
                normalized_sub_tags = {k.lower(): v for k, v in sub_tags.items()}
                metadata["subtitles"].append(
                    {
                        "codec": sub.get("codec_name"),
                        "language": normalized_sub_tags.get("language"),
                        "title": normalized_sub_tags.get("title"),
                    }
                )

        return metadata

    def _parse_bit_depth(self, pix_fmt: Optional[str]) -> Optional[int]:
        """Derive video bit depth from the pixel format (e.g. yuv420p10le -> 10)."""
        if not pix_fmt:
            return None
        pf = pix_fmt.lower()
        if "12" in pf:
            return 12
        if "10" in pf or "p010" in pf:
            return 10
        return 8

    def _parse_audio_bit_depth(self, audio_stream: Dict[str, Any]) -> Optional[int]:
        """Read the audio sample bit depth from an ffprobe audio stream."""
        for key in ("bits_per_raw_sample", "bits_per_sample"):
            value = audio_stream.get(key)
            try:
                depth = int(value) if value else 0
            except TypeError, ValueError:
                depth = 0
            if depth > 0:
                return depth
        return None

    def _parse_dynamic_range(self, video_stream: Dict[str, Any]) -> Optional[str]:
        """
        Determine the video dynamic range type: DV, HDR10+, HDR10, HLG, or SDR.
        Reads color transfer plus stream side data for Dolby Vision.
        """
        transfer = (video_stream.get("color_transfer") or "").lower()

        # Dolby Vision is signalled by a DOVI configuration record in side data.
        has_dv = False
        has_hdr10plus = False
        for side in video_stream.get("side_data_list", []) or []:
            side_type = str(side.get("side_data_type", "")).lower()
            if "dovi" in side_type or "dolby vision" in side_type:
                has_dv = True
            if "hdr dynamic metadata" in side_type or "smpte st 2094" in side_type:
                has_hdr10plus = True

        is_pq = transfer in ("smpte2084", "smpte st 2084")
        is_hlg = transfer in ("arib-std-b67", "arib_std_b67")

        if has_dv:
            return "DV HDR" if is_pq else "DV"
        if is_pq and has_hdr10plus:
            return "HDR10+"
        if is_pq:
            return "HDR10"
        if is_hlg:
            return "HLG"
        return "SDR"

    def _parse_frame_rate(self, frame_rate_str: Optional[str]) -> Optional[float]:
        """Parse frame rate string like '24000/1001' to float."""
        if not frame_rate_str:
            return None

        try:
            if "/" in frame_rate_str:
                num, denom = frame_rate_str.split("/")
                return float(num) / float(denom)
            return float(frame_rate_str)
        except ValueError, ZeroDivisionError:
            return None

    def is_video_file(self, file_path: str) -> bool:
        """Check if file has a video extension."""
        return Path(file_path).suffix.lower() in self.VIDEO_EXTENSIONS

    def is_audio_file(self, file_path: str) -> bool:
        """Check if file has an audio extension."""
        return Path(file_path).suffix.lower() in self.AUDIO_EXTENSIONS

    def is_sample(self, file_path: str) -> bool:
        """Check if file appears to be a sample/trailer based on filename or size."""
        file_name = Path(file_path).name.lower()

        # Check filename indicators
        if any(indicator in file_name for indicator in ["sample", "trailer", "preview", "rarbg"]):
            return True

        # Check file size (samples are usually < 100MB)
        try:
            file_size = Path(file_path).stat().st_size
            if file_size < 100 * 1024 * 1024:  # 100MB
                # If it's small AND has sample-like duration
                metadata = self.extract_metadata(file_path)
                if metadata and metadata.get("duration", 0) < 300:  # Less than 5 minutes
                    return True
        except:
            pass

        return False

    def get_video_info_summary(self, file_path: str) -> Optional[str]:
        """
        Get a human-readable summary of video info.

        Returns:
            String like "1080p HEVC 5.1" or None
        """
        metadata = self.extract_metadata(file_path)
        if not metadata:
            return None

        parts = []

        # Quality
        if metadata.get("quality"):
            parts.append(metadata["quality"])

        # Video codec
        if metadata.get("video", {}).get("codec"):
            codec = metadata["video"]["codec"]
            codec_map = {
                "hevc": "HEVC",
                "h264": "H.264",
                "h265": "HEVC",
                "vp9": "VP9",
                "av1": "AV1",
            }
            parts.append(codec_map.get(codec.lower(), codec.upper()))

        # Audio channels
        if metadata.get("audio") and len(metadata["audio"]) > 0:
            channels = metadata["audio"][0].get("channels")
            if channels == 6:
                parts.append("5.1")
            elif channels == 8:
                parts.append("7.1")
            elif channels == 2:
                parts.append("Stereo")

        return " ".join(parts) if parts else None


# Module-level singleton
metadata_extractor = MetadataExtractor()
