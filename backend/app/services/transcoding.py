import asyncio
import subprocess
import re
import json
import platform
from pathlib import Path
from typing import Dict, Optional, List, Callable, Any
import asyncpg
from datetime import datetime

from app.core.database import get_pool


class HardwareAccelerationService:
    """Detects and manages hardware acceleration devices"""

    def get_cpu_name(self) -> str:
        """Get CPU model name"""
        try:
            # Try lscpu command (available in most Linux containers)
            try:
                result = subprocess.run(
                    ["lscpu"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if line.startswith("Model name:"):
                            cpu_name = line.split(":", 1)[1].strip()
                            if cpu_name:
                                return cpu_name
            except (FileNotFoundError, Exception) as e:
                print(f"lscpu failed: {e}")

            # Try Linux /proc/cpuinfo
            try:
                if Path("/proc/cpuinfo").exists():
                    with open("/proc/cpuinfo", "r") as f:
                        for line in f:
                            if line.startswith("model name"):
                                cpu_name = line.split(":", 1)[1].strip()
                                if cpu_name:
                                    return cpu_name
            except Exception as e:
                print(f"/proc/cpuinfo failed: {e}")

            # Try Windows PowerShell (for native Windows)
            try:
                result = subprocess.run(
                    ["powershell", "-Command", "Get-CimInstance -ClassName Win32_Processor | Select-Object -ExpandProperty Name"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    cpu_name = result.stdout.strip()
                    if cpu_name:
                        print(f"Detected CPU via PowerShell: {cpu_name}")
                        return cpu_name
                    print(f"PowerShell output: {result.stdout}")
                else:
                    print(f"PowerShell return code: {result.returncode}, stderr: {result.stderr}")
            except (FileNotFoundError, Exception) as e:
                print(f"PowerShell failed: {e}")

            # Try macOS sysctl
            try:
                result = subprocess.run(
                    ["sysctl", "-n", "machdep.cpu.brand_string"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    cpu_name = result.stdout.strip()
                    if cpu_name:
                        return cpu_name
            except (FileNotFoundError, Exception) as e:
                print(f"sysctl failed: {e}")

            print("All CPU detection methods failed")
            return "CPU (Software Encoding)"
        except Exception as e:
            print(f"Error detecting CPU name: {e}")
            return "CPU (Software Encoding)"

    async def detect_nvidia_gpus(self) -> List[Dict[str, Any]]:
        """Detect NVIDIA GPUs using nvidia-smi"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "nvidia-smi",
                "--query-gpu=index,name,uuid,pci.bus_id,compute_cap,memory.total,driver_version",
                "--format=csv,noheader,nounits",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                return []

            gpus = []
            for line in stdout.decode().strip().split("\n"):
                if not line:
                    continue
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 7:
                    gpus.append({
                        "device_type": "nvidia",
                        "device_index": int(parts[0]),
                        "device_name": parts[1],
                        "device_uuid": parts[2],
                        "pci_bus_id": parts[3],
                        "compute_capability": parts[4],
                        "memory_total": int(float(parts[5]) * 1024 * 1024),
                        "driver_version": parts[6],
                    })
            return gpus
        except FileNotFoundError:
            return []
        except Exception as e:
            print(f"Error detecting NVIDIA GPUs: {e}")
            return []

    async def detect_intel_gpus(self) -> List[Dict[str, Any]]:
        """Detect Intel GPUs using vainfo"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "vainfo",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                return []

            output = stdout.decode() + stderr.decode()
            if "intel" in output.lower() and "driver" in output.lower():
                return [{
                    "device_type": "intel",
                    "device_index": 0,
                    "device_name": "Intel Quick Sync Video",
                    "device_uuid": None,
                    "pci_bus_id": None,
                    "compute_capability": None,
                    "memory_total": None,
                    "driver_version": None,
                }]
            return []
        except FileNotFoundError:
            return []
        except Exception as e:
            print(f"Error detecting Intel GPUs: {e}")
            return []

    async def detect_amd_gpus(self) -> List[Dict[str, Any]]:
        """Detect AMD GPUs using rocm-smi"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "rocm-smi",
                "--showproductname",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                return []

            output = stdout.decode()
            gpus = []
            device_index = 0

            for line in output.split("\n"):
                if "GPU" in line and ":" in line:
                    gpu_name = line.split(":")[-1].strip()
                    if gpu_name:
                        gpus.append({
                            "device_type": "amd",
                            "device_index": device_index,
                            "device_name": gpu_name,
                            "device_uuid": None,
                            "pci_bus_id": None,
                            "compute_capability": None,
                            "memory_total": None,
                            "driver_version": None,
                        })
                        device_index += 1
            return gpus
        except FileNotFoundError:
            return []
        except Exception as e:
            print(f"Error detecting AMD GPUs: {e}")
            return []

    async def detect_all_devices(self) -> List[Dict[str, Any]]:
        """Detect all available hardware acceleration devices"""
        all_devices = []

        # Always add CPU as an available option
        cpu_name = self.get_cpu_name()
        cpu_device = {
            "device_type": "cpu",
            "device_index": 0,
            "device_name": cpu_name,
            "device_uuid": None,
            "pci_bus_id": None,
            "compute_capability": None,
            "memory_total": None,
            "driver_version": None,
        }
        all_devices.append(cpu_device)

        nvidia_devices = await self.detect_nvidia_gpus()
        intel_devices = await self.detect_intel_gpus()
        amd_devices = await self.detect_amd_gpus()

        all_devices.extend(nvidia_devices)
        all_devices.extend(intel_devices)
        all_devices.extend(amd_devices)

        return all_devices

    async def save_devices_to_db(self, devices: List[Dict[str, Any]]) -> None:
        """Save detected devices to database"""
        pool = await get_pool()
        async with pool.acquire() as conn:
            for device in devices:
                await conn.execute(
                    """
                    INSERT INTO hardware_accel_devices (
                        device_type, device_index, device_name, device_uuid,
                        pci_bus_id, compute_capability, memory_total, driver_version,
                        is_available, last_detected
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, true, NOW())
                    ON CONFLICT (device_type, device_index)
                    DO UPDATE SET
                        device_name = EXCLUDED.device_name,
                        device_uuid = EXCLUDED.device_uuid,
                        pci_bus_id = EXCLUDED.pci_bus_id,
                        compute_capability = EXCLUDED.compute_capability,
                        memory_total = EXCLUDED.memory_total,
                        driver_version = EXCLUDED.driver_version,
                        is_available = true,
                        last_detected = NOW()
                    """,
                    device["device_type"],
                    device["device_index"],
                    device["device_name"],
                    device["device_uuid"],
                    device["pci_bus_id"],
                    device["compute_capability"],
                    device["memory_total"],
                    device["driver_version"],
                )

    async def get_devices_from_db(self) -> List[Dict[str, Any]]:
        """Get available devices from database"""
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM hardware_accel_devices
                WHERE is_available = true
                ORDER BY device_type, device_index
                """
            )
            return [dict(row) for row in rows]


class FFmpegService:
    """Handles FFmpeg transcoding operations with hardware acceleration"""

    def __init__(self):
        self.ffmpeg_path = "ffmpeg"
        self.ffprobe_path = "ffprobe"

    async def get_media_info(self, file_path: str) -> Dict[str, Any]:
        """Get media file information using ffprobe"""
        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path,
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise Exception(f"ffprobe failed: {stderr.decode()}")

        return json.loads(stdout)

    async def count_frames(self, file_path: str) -> Optional[int]:
        """Count total frames in video"""
        try:
            info = await self.get_media_info(file_path)
            for stream in info.get("streams", []):
                if stream.get("codec_type") == "video":
                    nb_frames = stream.get("nb_frames")
                    if nb_frames and nb_frames != "N/A":
                        return int(nb_frames)

                    duration = float(stream.get("duration", 0))
                    fps_str = stream.get("r_frame_rate", "0/1")
                    if "/" in fps_str:
                        num, den = map(int, fps_str.split("/"))
                        if den > 0:
                            fps = num / den
                            return int(duration * fps)
            return None
        except Exception as e:
            print(f"Error counting frames: {e}")
            return None

    def build_ffmpeg_command(
        self,
        input_path: str,
        output_path: str,
        profile: Dict[str, Any],
        hardware_accel_type: Optional[str] = None,
        hardware_accel_device: Optional[int] = None,
    ) -> List[str]:
        """Build FFmpeg command from profile settings"""
        cmd = [self.ffmpeg_path]

        # Hardware acceleration input
        if hardware_accel_type == "nvidia":
            cmd.extend(["-hwaccel", "cuda"])
            if hardware_accel_device is not None:
                cmd.extend(["-hwaccel_device", str(hardware_accel_device)])
        elif hardware_accel_type == "intel":
            cmd.extend(["-hwaccel", "qsv"])
            if hardware_accel_device is not None:
                cmd.extend(["-qsv_device", f"/dev/dri/renderD{128 + hardware_accel_device}"])
        elif hardware_accel_type == "amd":
            cmd.extend(["-hwaccel", "vaapi"])
            cmd.extend(["-vaapi_device", f"/dev/dri/renderD{128 + (hardware_accel_device or 0)}"])

        cmd.extend(["-i", input_path])

        # Video codec
        video_codec = profile.get("video_codec", "libx264")
        if hardware_accel_type == "nvidia":
            codec_map = {
                "libx264": "h264_nvenc",
                "libx265": "hevc_nvenc",
                "h264": "h264_nvenc",
                "h265": "hevc_nvenc",
                "hevc": "hevc_nvenc",
                "av1": "av1_nvenc",
            }
            video_codec = codec_map.get(video_codec.lower(), video_codec)
        elif hardware_accel_type == "intel":
            codec_map = {
                "libx264": "h264_qsv",
                "libx265": "hevc_qsv",
                "h264": "h264_qsv",
                "h265": "hevc_qsv",
                "hevc": "hevc_qsv",
                "av1": "av1_qsv",
                "vp9": "vp9_qsv",
            }
            video_codec = codec_map.get(video_codec.lower(), video_codec)
        elif hardware_accel_type == "amd":
            codec_map = {
                "libx264": "h264_vaapi",
                "libx265": "hevc_vaapi",
                "h264": "h264_vaapi",
                "h265": "hevc_vaapi",
                "hevc": "hevc_vaapi",
                "vp9": "vp9_vaapi",
            }
            video_codec = codec_map.get(video_codec.lower(), video_codec)

        cmd.extend(["-c:v", video_codec])

        # Video quality
        quality_mode = profile.get("video_quality_mode", "crf")
        quality_value = profile.get("video_quality_value", 23)

        if quality_mode == "crf":
            cmd.extend(["-crf", str(quality_value)])
        elif quality_mode == "bitrate":
            cmd.extend(["-b:v", f"{quality_value}k"])
        elif quality_mode == "lossless":
            if "nvenc" in video_codec:
                cmd.extend(["-preset", "lossless"])
            elif video_codec == "libx264":
                cmd.extend(["-crf", "0"])
            elif video_codec == "libx265":
                cmd.extend(["-x265-params", "lossless=1"])

        # Video preset
        if profile.get("video_preset"):
            cmd.extend(["-preset", profile["video_preset"]])

        # Tune
        if profile.get("tune"):
            cmd.extend(["-tune", profile["tune"]])

        # Resolution
        resolution = profile.get("resolution")
        if resolution and resolution != "original":
            resolution_map = {
                "1080p": "scale=-2:1080",
                "720p": "scale=-2:720",
                "4k": "scale=-2:2160",
                "480p": "scale=-2:480",
                "2160p": "scale=-2:2160",
            }
            scale_filter = resolution_map.get(resolution.lower())
            if scale_filter:
                cmd.extend(["-vf", scale_filter])

        # FPS
        if profile.get("fps") and profile.get("fps") != "original":
            cmd.extend(["-r", profile["fps"]])

        # Audio codec
        audio_codec = profile.get("audio_codec", "aac")
        if audio_codec == "copy":
            cmd.extend(["-c:a", "copy"])
        else:
            cmd.extend(["-c:a", audio_codec])
            if profile.get("audio_bitrate"):
                cmd.extend(["-b:a", f"{profile['audio_bitrate']}k"])

        # Audio channels
        if profile.get("audio_channels"):
            channels_map = {
                "mono": "1",
                "stereo": "2",
                "2.0": "2",
                "5.1": "6",
                "7.1": "8",
            }
            channels = channels_map.get(profile["audio_channels"].lower())
            if channels:
                cmd.extend(["-ac", channels])

        # Container format
        container = profile.get("container", "mkv")
        if container and not output_path.endswith(f".{container}"):
            output_path = str(Path(output_path).with_suffix(f".{container}"))

        # Custom FFmpeg args
        if profile.get("custom_ffmpeg_args"):
            if isinstance(profile["custom_ffmpeg_args"], list):
                cmd.extend(profile["custom_ffmpeg_args"])
            elif isinstance(profile["custom_ffmpeg_args"], dict):
                for key, value in profile["custom_ffmpeg_args"].items():
                    cmd.extend([key, str(value)])

        # Progress tracking
        cmd.extend(["-progress", "pipe:1", "-stats_period", "1"])

        # Overwrite output
        cmd.extend(["-y"])

        # Output
        cmd.append(output_path)

        return cmd

    async def transcode(
        self,
        job_id: int,
        input_path: str,
        output_path: str,
        profile: Dict[str, Any],
        hardware_accel_type: Optional[str] = None,
        hardware_accel_device: Optional[int] = None,
        progress_callback: Optional[Callable] = None,
    ) -> bool:
        """Execute transcoding with progress tracking"""
        cmd = self.build_ffmpeg_command(
            input_path,
            output_path,
            profile,
            hardware_accel_type,
            hardware_accel_device,
        )

        print(f"Transcoding command: {' '.join(cmd)}")

        total_frames = await self.count_frames(input_path)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Parse progress from stdout
        async def read_progress():
            progress_data = {}
            async for line in proc.stdout:
                line = line.decode().strip()
                if "=" in line:
                    key, value = line.split("=", 1)
                    progress_data[key] = value

                    if key == "progress" and progress_data.get("progress") in ["continue", "end"]:
                        frame = int(progress_data.get("frame", 0))
                        fps_val = float(progress_data.get("fps", 0))
                        bitrate = progress_data.get("bitrate", "0kbits/s")
                        size = int(progress_data.get("total_size", 0))
                        time_str = progress_data.get("out_time_us", "0")
                        speed = progress_data.get("speed", "0x")

                        progress_percent = 0
                        if total_frames and frame > 0:
                            progress_percent = min(100, (frame / total_frames) * 100)

                        if progress_callback:
                            await progress_callback(
                                job_id,
                                {
                                    "frame": frame,
                                    "fps": fps_val,
                                    "bitrate": bitrate,
                                    "size": size,
                                    "time": time_str,
                                    "speed": speed,
                                    "progress": progress_percent,
                                },
                            )

                        progress_data = {}

        await asyncio.gather(read_progress(), proc.wait())

        return proc.returncode == 0


hardware_accel_service = HardwareAccelerationService()
ffmpeg_service = FFmpegService()
