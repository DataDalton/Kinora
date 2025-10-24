# Search Engine Priority & Cascading Analysis

## Core Principle: Ordered Lists

**IMPORTANT:** The system uses a single unified approach for ALL quality preferences:

- **If value is IN the list**: It is ALLOWED
- **Position in list**: Determines PREFERENCE (index 0 = highest priority)
- **If value is NOT in the list**: It is REJECTED

There are NO separate "preferred vs allowed" fields. Order determines both.

---

## Current Cascading Search Implementation

### Priority Hierarchy (Top to Bottom)

The search engine uses a **2-tier cascading system**:

#### Tier 1: Cascading Query (search_engine.py)

These determine WHICH searches are performed and in what order:

**Multi-dimensional cascading** - Each attribute cascades in priority order:

1. **Resolution** (HIGHEST PRIORITY)
   - Source: `profile.resolutions` (ordered list, first = most preferred)
   - Example: `["2160p", "1080p", "720p"]`

2. **Source** (SECOND PRIORITY)
   - Source: `profile.sources` (ordered list, first = most preferred)
   - Example: `["REMUX", "BluRay", "WEB-DL"]`

3. **Codec** (THIRD PRIORITY)
   - Source: `profile.codecs` (ordered list, first = most preferred)
   - Example: `["AV1", "HEVC", "x265"]`

4. **HDR** (FOURTH PRIORITY)
   - Source: `profile.hdr_formats` (ordered list, first = most preferred)
   - Example: `["Dolby Vision", "HDR10+", "HDR10"]`

5. **Uploader** (FIFTH PRIORITY)
   - Source: `profile.uploaders` (ordered list, first = most preferred)
   - Example: `["RARBG", "SPARKS", "YTS"]`

**Cascade Order Example:**
```
Profile:
  resolutions: ["2160p", "1080p"]
  sources: ["BluRay", "WEB-DL"]
  uploaders: ["RARBG", "SPARKS"]

Search order:
1. 2160p BluRay RARBG
2. 2160p BluRay SPARKS
3. 2160p WEB-DL RARBG
4. 2160p WEB-DL SPARKS
5. 1080p BluRay RARBG
6. 1080p BluRay SPARKS
7. 1080p WEB-DL RARBG
8. 1080p WEB-DL SPARKS
```

The search stops as soon as an acceptable release is found.

#### Tier 2: Filtering & Scoring (media_profile.py)

Once results are found, these determine WHICH releases pass and which is best:

**Step 1: Hard Filters** (`_meets_minimum_requirements`)
Releases MUST pass ALL of these or get rejected:

1. **Resolution** - Must be in `profile.resolutions` list
2. **Codec** - Must be in `profile.codecs` list (if set)
3. **Source** - Must be in `profile.sources` list (if set)
4. **Audio Codec** - Must be in `profile.audio_codecs` list (if set)
5. **Audio Channels** - Must be in `profile.audio_channels` list (if set)
6. **HDR Format** - Must be in `profile.hdr_formats` list (if set)
7. **Edition** - Must be in `profile.editions` list (if set)
8. **Language** - Must be in `profile.languages` list (if set)
9. **File Size** - Must be between `min_size` and `max_size`
10. **Minimum Seeders** - Must have at least 1 seeder
11. **Uploader** - Must be in `profile.uploaders` list (if set)
12. **Release Group** - Must be in `profile.release_groups` list (if set)
13. **Regex Filters** - Must match ALL `regex_filters` patterns

**Step 2: Scoring** (`score_release`)
Surviving releases get scored (higher = better):

| Feature | Points | Calculation Method |
|---------|--------|-------------------|
| **Quality (Resolution)** | 0-100 | Base hierarchy score + position bonus (first in list gets 25pts bonus, decreases by 5 per position) |
| **Codec** | 0-30 | Base hierarchy score + position bonus (first in list gets 15pts bonus, decreases by 3 per position) |
| **Source** | 0-30 | Base hierarchy score + position bonus (first in list gets 15pts bonus, decreases by 3 per position) |
| **Audio Codec** | 0-20 | Base hierarchy score + position bonus (first in list gets 20pts bonus, decreases by 4 per position) |
| **HDR** | 0-20 | Base hierarchy score + position bonus (first in list gets 20pts bonus, decreases by 5 per position) |
| **Resolution** | 0-15 | Position bonus (first gets 15pts, decreases by 3 per position) |
| **Audio Channels** | 0-10 | Position bonus (first gets 10pts, decreases by 2 per position) |
| **Edition** | 0-10 | Base hierarchy score + position bonus (first gets 10pts, decreases by 2 per position) |
| **Seeders** | 0-50 | Logarithmic scale, weighted by `seeder_weight` (default 34%) |
| **Size** | Variable | Penalty for size outside optimal range, weighted by `size_weight` (default 33%) |
| **Preferred Uploader** | +50 | Bonus if in preferred_uploaders parameter (separate from profile.uploaders) |
| **Trusted Group** | +30 | Bonus for hardcoded trusted groups |
| **PROPER/REPACK** | +20 | Bonus for proper or repack releases |

**Total Possible Score**: ~400+ points

---

## Search Flow Example

**Query:** "Iron Man"
**Profile Settings:**

```python
profile = {
    "resolutions": ["2160p", "1080p"],              # Order = priority
    "sources": ["BluRay", "WEB-DL"],                # Order = priority
    "hdr_formats": ["Dolby Vision", "HDR10"],       # Order = priority
    "uploaders": ["RARBG", "SPARKS"],               # Order = priority
    "audio_channels": ["Atmos", "7.1", "5.1"],      # Filter only (not cascaded)
}
```

### Execution Order

```
┌─────────────────────────────────────────────────────────┐
│ TIER 1: CASCADING SEARCH (Multi-dimensional)            │
└─────────────────────────────────────────────────────────┘

1. Search: "Iron Man 2160p BluRay Dolby Vision RARBG"
   ├─ 0 results found
   └─ Continue to next uploader

2. Search: "Iron Man 2160p BluRay Dolby Vision SPARKS"
   ├─ 0 results found
   └─ Cascade to next HDR format

3. Search: "Iron Man 2160p BluRay HDR10 RARBG"
   ├─ 0 results found
   └─ Continue cascading...

4. Search: "Iron Man 2160p WEB-DL Dolby Vision RARBG"
   ├─ 0 results found
   └─ Continue cascading...

5. Search: "Iron Man 1080p BluRay Dolby Vision RARBG"
   ├─ Found 8 releases
   └─ Apply Tier 2 filtering...

┌─────────────────────────────────────────────────────────┐
│ TIER 2: FILTERING & SCORING                             │
└─────────────────────────────────────────────────────────┘

HARD FILTERS (must pass ALL):
├─ Release 1: "Iron Man 1080p BluRay x264 RARBG"
│  ✓ Resolution: 1080p (in resolutions list)
│  ✓ Audio Channels: 5.1 (in audio_channels list)
│  ✗ HDR: None (NOT in hdr_formats list)
│  → REJECTED

├─ Release 2: "Iron Man 1080p BluRay x265 HDR10 RARBG"
│  ✓ Resolution: 1080p (in resolutions list)
│  ✓ Audio Channels: 5.1 (in audio_channels list)
│  ✓ HDR: HDR10 (in hdr_formats list, position 2)
│  ✓ Size: 8GB (within limits)
│  ✓ Seeders: 45
│  → PASSED (score: 285 points)

├─ Release 3: "Iron Man 1080p WEB-DL Atmos DV RARBG"
│  ✓ Resolution: 1080p (in resolutions list)
│  ✓ Audio Channels: Atmos (in audio_channels list, position 0 = highest)
│  ✓ HDR: Dolby Vision (in hdr_formats list, position 0 = highest)
│  ✓ Size: 12GB
│  ✓ Seeders: 120
│  → PASSED (score: 340 points - higher due to position bonuses)

└─ Release 4: "Iron Man 1080p CAM x264"
   ✗ Source: CAM (not in sources list, if sources specified)
   → REJECTED

SCORING WINNER:
└─ Release 3: "Iron Man 1080p WEB-DL Atmos DV RARBG"
   Score: 340 points (highest due to Atmos and DV being position 0 in lists)
   ✓ SELECTED - Stop searching
```

---

## What IS Cascaded (Tier 1 - Search Query)

✅ **Resolution** - Priority 1, searches in order from list
✅ **Source** - Priority 2, searches in order from list
✅ **Codec** - Priority 3, searches in order from list
✅ **HDR** - Priority 4, searches in order from list
✅ **Uploader** - Priority 5, searches in order from list

## What is NOT Cascaded (Tier 2 - Filtering Only)

These are used for filtering/scoring WITHIN results, not for cascading queries:

❌ **Audio Codec** (FLAC, DTS, AAC) - Not in search query, filtered/scored only
❌ **Audio Channels** (Atmos, 7.1, 5.1) - Not in search query, filtered/scored only
❌ **Edition** (IMAX, Director's Cut) - Not in search query, filtered/scored only
❌ **Language** - Not in search query, filtered/scored only
❌ **Size** - Not in search query, filtered/scored only

**Why not cascade everything?**
- Audio codec/channels are usually not in torrent titles the same way as sources/codecs
- Edition and language are less commonly used for searching
- Cascading too many dimensions causes exponential growth in API calls

---

## Profile Field Naming

### Database Schema (`media_profiles` table)

```sql
resolutions JSONB            -- Ordered list: ["2160p", "1080p", "720p"]
codecs JSONB                 -- Ordered list: ["AV1", "HEVC", "x265"]
sources JSONB                -- Ordered list: ["REMUX", "BluRay", "WEB-DL"]
audio_codecs JSONB           -- Ordered list: ["FLAC", "DTS-HD MA", "DTS"]
audio_channels JSONB         -- Ordered list: ["Atmos", "7.1", "5.1"]
hdr_formats JSONB            -- Ordered list: ["Dolby Vision", "HDR10+", "HDR10"]
editions JSONB               -- Ordered list: ["IMAX", "Director's Cut"]
languages JSONB              -- Ordered list: ["en", "es", "fr"]
indexers JSONB               -- Ordered list: ["1337x", "YTS"]
uploaders JSONB              -- Ordered list: ["RARBG", "SPARKS", "YTS"]
release_groups JSONB         -- Ordered list: ["FGT", "ROVERS"]
regex_filters JSONB          -- List of regex patterns (all must match)
```

### No More "Preferred vs Allowed"

**OLD (removed):**
```python
preferred_resolutions = ["2160p", "1080p"]
allowed_resolutions = ["2160p", "1080p", "720p", "480p"]
```

**NEW (current):**
```python
resolutions = ["2160p", "1080p", "720p", "480p"]  # In list = allowed, order = preference
```

---

## How Cascading Works

### Example 1: User Only Wants BluRay

**Profile:**
```python
sources = ["BluRay"]  # ONLY BluRay allowed
```

**Search Behavior:**
```
Search: "Iron Man 2160p BluRay"
  Found: BluRay release → DOWNLOAD ✓

Search: "Iron Man 2160p BluRay"
  Found: Only WEB-DL available
  Filter: WEB-DL NOT in sources list
  Result: NO DOWNLOAD ✗ (correct - user only wants BluRay)
```

### Example 2: User Prefers BluRay but Accepts WEB-DL

**Profile:**
```python
sources = ["BluRay", "WEB-DL"]  # Both allowed, BluRay preferred
```

**Search Behavior:**
```
Search: "Iron Man 2160p BluRay"
  Found: BluRay release → DOWNLOAD ✓ (preferred source found)

Search: "Iron Man 2160p BluRay"
  Not Found: No BluRay
  Cascade: "Iron Man 2160p WEB-DL"
  Found: WEB-DL release → DOWNLOAD ✓ (acceptable fallback)
```

### Example 3: Multi-attribute Cascading

**Profile:**
```python
resolutions = ["2160p", "1080p"]
sources = ["REMUX", "BluRay"]
codecs = ["AV1", "HEVC"]
```

**Search Behavior:**
```
Tries in order:
1. 2160p REMUX AV1
2. 2160p REMUX HEVC
3. 2160p BluRay AV1
4. 2160p BluRay HEVC
5. 1080p REMUX AV1
6. 1080p REMUX HEVC
7. 1080p BluRay AV1
8. 1080p BluRay HEVC

Stops as soon as ANY of these is found.
If NONE found, no download.
```

---

## Current State Summary

**Cascading Priority (Tier 1):**
1. Resolution (from `profile.resolutions`, first = highest priority)
2. Source (from `profile.sources`, second priority)
3. Codec (from `profile.codecs`, third priority)
4. HDR (from `profile.hdr_formats`, fourth priority)
5. Uploader (from `profile.uploaders`, fifth priority)

**Hard Filters (Tier 2):** (Must pass all)
- Resolution, Codec, Source, Audio Codec, Audio Channels, HDR, Edition, Language
- File Size, Seeders, Uploader, Release Group, Regex

**Scoring (Tier 2):** (Higher wins, with position bonuses)
- Quality (100pts) > Codec (30pts) > Source (30pts) > Audio (20pts)
- HDR (20pts) > Resolution (15pts) > Channels (10pts) > Edition (10pts)
- Seeders (50pts) + Size penalty + Uploader bonuses

**What works well:**
- ✅ Intelligent multi-dimensional cascading
- ✅ User controls exactly what's acceptable (in list = allowed)
- ✅ User controls preference order (position = priority)
- ✅ Simple, intuitive "in list = allowed, order = preference" model
- ✅ Comprehensive filtering and scoring with position bonuses
- ✅ Stops as soon as acceptable release found (efficient)

**Design Philosophy:**
- ✅ Single source of truth: one ordered list per attribute
- ✅ No confusion between "preferred" and "allowed"
- ✅ Clear priority: list order matters
- ✅ Flexible: user controls exactly what's acceptable and in what order
- ✅ If it's in the list, we'll try it (cascading)
- ✅ If it's NOT in the list, we'll reject it (filtering)
