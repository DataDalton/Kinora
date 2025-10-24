# Layer 3: Deep Media Inspection Design

## Overview

Add a third metadata extraction layer that analyzes actual media files instead of just parsing titles.

## Current State (Layers 1 & 2)

### Layer 1: Indexer Parsing
- **Source**: Torrent title string
- **When**: When torrent is fetched from indexer
- **Method**: Regex pattern matching on title
- **Storage**: `TorrentRelease` object fields

### Layer 2: Profile Parsing
- **Source**: Torrent title string (same as Layer 1)
- **When**: During filtering/scoring
- **Method**: Uses Layer 1 values OR re-parses title
- **Limitation**: Still relying on title parsing

**Problem**: Both layers parse the SAME source (title). No actual file inspection.

## Proposed Layer 3: Deep Media Inspection

### Sources of Truth

1. **Downloaded Media Files**
   - Use MediaInfo or FFprobe to extract real metadata
   - 100% accurate codec, resolution, audio tracks, HDR info

2. **Torrent File Structure**
   - Analyze .torrent file metadata
   - File lists, sizes, directory structure

3. **Download Client Data**
   - qBittorrent API file information
   - Completion status, file paths

### When to Use Layer 3

**Timing Options:**

1. **Pre-Download Validation** (if .torrent file is available)
   - Download .torrent file before committing
   - Parse file list to verify quality claims
   - Reject if title lies about content

2. **Post-Download Verification** (most accurate)
   - After download completes
   - Analyze actual video file with MediaInfo/FFprobe
   - Update database with real metadata
   - Optionally reject/delete if doesn't match profile

3. **Hybrid Approach**
   - Use title parsing for initial filtering (fast)
   - Use deep inspection for final verification (accurate)

### Implementation Components

#### 1. MediaInfo/FFprobe Integration

```python
# app/services/media/inspector.py

class MediaInspector:
    """Extract real metadata from video files"""

    def analyze_file(self, file_path: str) -> MediaMetadata:
        """Use ffprobe to extract video/audio metadata"""
        pass

    def get_video_info(self, file_path: str) -> VideoInfo:
        """Extract: codec, resolution, HDR, bitrate"""
        pass

    def get_audio_tracks(self, file_path: str) -> List[AudioTrack]:
        """Extract: codec, channels, language for each track"""
        pass

    def get_subtitle_tracks(self, file_path: str) -> List[SubtitleTrack]:
        """Extract: language, format for each subtitle"""
        pass
```

#### 2. Post-Download Hook

```python
# app/services/automation/download_handler.py

async def on_download_complete(torrent_id: str):
    """Called when download finishes"""

    # Get file path from download client
    file_path = await qbittorrent_client.get_file_path(torrent_id)

    # Analyze with MediaInfo/FFprobe
    metadata = media_inspector.analyze_file(file_path)

    # Compare to media profile requirements
    if not profile.deep_inspection_enabled:
        return  # Skip if not enabled

    if not matches_profile(metadata, profile):
        # Optionally reject and delete
        if profile.reject_on_inspection_fail:
            await qbittorrent_client.remove_torrent(torrent_id)
            logger.warning(f"Rejected {file_path}: failed deep inspection")

    # Update database with real metadata
    await update_media_metadata(media_id, metadata)
```

#### 3. Database Schema Extensions

```sql
-- Add analyzed metadata columns to movies/shows/anime tables
ALTER TABLE movies ADD COLUMN analyzed_codec VARCHAR(50);
ALTER TABLE movies ADD COLUMN analyzed_resolution VARCHAR(10);
ALTER TABLE movies ADD COLUMN analyzed_hdr VARCHAR(50);
ALTER TABLE movies ADD COLUMN analyzed_audio_tracks JSONB;
ALTER TABLE movies ADD COLUMN analyzed_subtitle_tracks JSONB;
ALTER TABLE movies ADD COLUMN analyzed_bitrate INTEGER;
ALTER TABLE movies ADD COLUMN analysis_date TIMESTAMP;

-- Add deep inspection settings to media_profiles
ALTER TABLE media_profiles ADD COLUMN deep_inspection_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE media_profiles ADD COLUMN reject_on_inspection_fail BOOLEAN DEFAULT FALSE;
ALTER TABLE media_profiles ADD COLUMN require_analysis_match BOOLEAN DEFAULT FALSE;
```

#### 4. Frontend Toggle (Media Profiles)

Add to each media profile:

```typescript
// Deep Inspection Settings Section
{
  deepInspectionEnabled: boolean;
  rejectOnInspectionFail: boolean;
  requireAnalysisMatch: boolean;
}
```

UI mockup:
```
┌─────────────────────────────────────────────┐
│ Deep Media Inspection                       │
├─────────────────────────────────────────────┤
│ ☐ Enable deep inspection after download    │
│                                             │
│ When enabled:                               │
│ ☐ Reject downloads that fail inspection    │
│ ☐ Require analyzed metadata to match       │
│   profile requirements                      │
│                                             │
│ ℹ Deep inspection uses FFprobe to analyze  │
│   actual video files, providing 100%       │
│   accurate metadata instead of relying     │
│   on torrent title parsing.                │
└─────────────────────────────────────────────┘
```

### Example Use Cases

#### Use Case 1: Verify HDR Claims
```
Title claims: "Movie.2024.2160p.DV.HDR10.x265"
After download: FFprobe reveals no Dolby Vision, only HDR10
Action: If reject_on_fail enabled, delete and search again
```

#### Use Case 2: Audio Track Verification
```
Profile requires: English audio track
Title parsing: Can't verify language from title
After download: FFprobe shows only Spanish audio
Action: Reject and re-search
```

#### Use Case 3: Real Resolution Check
```
Title claims: "1080p"
After download: FFprobe shows 720p upscaled to 1080p
Action: Mark as 720p in database, optionally reject
```

### Performance Considerations

1. **FFprobe Speed**: ~1-2 seconds per file (acceptable post-download)
2. **Optional**: Only analyze if enabled in profile
3. **Async**: Run analysis in background, don't block UI
4. **Caching**: Store results in database to avoid re-analysis

### Dependencies

**Required Packages:**
- `ffmpeg-python` or call `ffprobe` binary directly
- Alternative: `pymediainfo` for MediaInfo library

**Installation:**
```bash
# FFmpeg/FFprobe (must be installed on system)
apt-get install ffmpeg  # Linux
brew install ffmpeg     # macOS
choco install ffmpeg    # Windows

# Python wrapper
pip install ffmpeg-python
```

### Migration Path

1. **Phase 1**: Add Layer 3 infrastructure (inspector, hooks)
2. **Phase 2**: Add database columns and migrations
3. **Phase 3**: Add frontend toggles
4. **Phase 4**: Default to disabled, allow users to opt-in
5. **Phase 5**: Monitor accuracy improvements, consider defaulting to enabled

## Benefits

✅ **100% Accurate Metadata** - No relying on title naming conventions
✅ **Catches Mislabeled Releases** - Verify codec/resolution claims
✅ **Multi-Audio Detection** - Find releases with multiple language tracks
✅ **HDR Verification** - Confirm Dolby Vision/HDR10+ actually exists
✅ **Quality Control** - Automatically reject low-quality encodes

## Drawbacks

❌ **Slower** - Adds 1-2 seconds per file analysis
❌ **Post-Download Only** - Can't verify before downloading
❌ **Dependency** - Requires FFmpeg/FFprobe installed
❌ **Storage** - More database columns for analyzed metadata

## Recommendation

**Implement Layer 3 as optional feature:**
- Default: Disabled (keep current title-parsing behavior)
- Power Users: Enable for 100% accurate metadata
- Automation: Enable reject_on_fail for strict quality control

**Best of both worlds:**
- Fast title parsing for initial filtering (Layers 1 & 2)
- Deep inspection for verification (Layer 3)
- User choice for their use case
