from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


def to_camel(string: str) -> str:
    """Convert snake_case to camelCase"""
    components = string.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


class HardwareAccelDevice(BaseModel):
    """Hardware acceleration device"""
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel
    )

    id: int
    device_type: str
    device_index: int
    device_name: Optional[str] = None
    device_uuid: Optional[str] = None
    pci_bus_id: Optional[str] = None
    compute_capability: Optional[str] = None
    memory_total: Optional[int] = None
    driver_version: Optional[str] = None
    is_available: bool
    last_detected: datetime


class TranscodingProfileCreate(BaseModel):
    """Create transcoding profile"""
    name: str
    description: Optional[str] = None
    container: str = "mkv"
    video_codec: str = "libx265"
    video_quality_mode: str = "crf"
    video_quality_value: int = 23
    video_preset: Optional[str] = "medium"
    audio_codec: str = "aac"
    audio_bitrate: Optional[int] = 192
    audio_channels: Optional[str] = "original"
    resolution: str = "original"
    fps: Optional[str] = "original"
    hardware_accel_type: Optional[str] = None
    hardware_accel_device: Optional[int] = None
    tune: Optional[str] = None
    custom_ffmpeg_args: Optional[Dict[str, Any]] = None


class TranscodingProfileUpdate(BaseModel):
    """Update transcoding profile"""
    name: Optional[str] = None
    description: Optional[str] = None
    container: Optional[str] = None
    video_codec: Optional[str] = None
    video_quality_mode: Optional[str] = None
    video_quality_value: Optional[int] = None
    video_preset: Optional[str] = None
    audio_codec: Optional[str] = None
    audio_bitrate: Optional[int] = None
    audio_channels: Optional[str] = None
    resolution: Optional[str] = None
    fps: Optional[str] = None
    hardware_accel_type: Optional[str] = None
    hardware_accel_device: Optional[int] = None
    tune: Optional[str] = None
    custom_ffmpeg_args: Optional[Dict[str, Any]] = None


class TranscodingProfileResponse(BaseModel):
    """Transcoding profile response"""
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel
    )

    id: int
    name: str
    description: Optional[str]
    container: str
    video_codec: str
    video_quality_mode: str
    video_quality_value: int
    video_preset: Optional[str]
    audio_codec: str
    audio_bitrate: Optional[int]
    audio_channels: Optional[str]
    resolution: str
    fps: Optional[str]
    hardware_accel_type: Optional[str]
    hardware_accel_device: Optional[int]
    tune: Optional[str]
    custom_ffmpeg_args: Optional[Dict[str, Any]]
    is_system: bool
    created_at: datetime
    updated_at: datetime


class TranscodingJobCreate(BaseModel):
    """Create transcoding job"""
    media_id: Optional[int] = None
    media_type: Optional[str] = None
    input_path: str
    output_action: str = Field(default="replace", description="'replace' or 'new_file'")
    use_media_profile_naming: bool = Field(default=True, description="Use media profile naming format for output")
    output_path: Optional[str] = Field(default=None, description="Custom output path (only if use_media_profile_naming=False)")
    profile_id: int
    hardware_accel_type: Optional[str] = Field(default=None, description="'nvidia', 'intel', 'amd', or None for CPU")
    hardware_accel_device: Optional[int] = Field(default=None, description="GPU device index if multiple GPUs")


class TranscodingJobResponse(BaseModel):
    """Transcoding job response"""
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel
    )

    id: int
    user_id: int
    media_id: Optional[int]
    media_type: Optional[str]
    media_title: Optional[str]
    input_path: str
    output_path: Optional[str]
    output_action: str
    use_media_profile_naming: bool
    profile_id: Optional[int]
    profile_snapshot: Dict[str, Any]
    hardware_accel_type: Optional[str]
    hardware_accel_device: Optional[int]
    status: str
    progress: float
    current_frame: Optional[int]
    total_frames: Optional[int]
    fps: Optional[float]
    speed: Optional[str]
    bitrate: Optional[str]
    file_size_input: Optional[int]
    file_size_output: Optional[int]
    eta_seconds: Optional[int]
    celery_task_id: Optional[str]
    error_message: Optional[str]
    log_file: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    updated_at: datetime


class TranscodingRuleCreate(BaseModel):
    """Create transcoding rule"""
    name: str
    enabled: bool = True
    priority: int = 0
    trigger_type: str = Field(description="'on_download', 'on_import', 'scheduled'")
    conditions: Dict[str, Any] = Field(description="Conditions like {file_size_gt: 10000000000, codec: 'h264'}")
    profile_id: int
    output_action: str = "replace"
    use_media_profile_naming: bool = True
    media_types: List[str] = ["movie", "show", "anime"]


class TranscodingRuleUpdate(BaseModel):
    """Update transcoding rule"""
    name: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    trigger_type: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None
    profile_id: Optional[int] = None
    output_action: Optional[str] = None
    use_media_profile_naming: Optional[bool] = None
    media_types: Optional[List[str]] = None


class TranscodingRuleResponse(BaseModel):
    """Transcoding rule response"""
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel
    )

    id: int
    name: str
    enabled: bool
    priority: int
    trigger_type: str
    conditions: Dict[str, Any]
    profile_id: int
    output_action: str
    use_media_profile_naming: bool
    media_types: List[str]
    created_at: datetime
    updated_at: datetime


class MediaFileInfo(BaseModel):
    """Media file information from ffprobe"""
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel
    )

    format_name: str
    duration: float
    size: int
    bit_rate: int
    video_codec: Optional[str]
    video_resolution: Optional[str]
    video_fps: Optional[float]
    audio_codec: Optional[str]
    audio_channels: Optional[int]
    audio_bitrate: Optional[int]
