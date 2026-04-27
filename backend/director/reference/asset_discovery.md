# Asset Discovery Guide

Find videos, audios, and images in a collection using the assets API. Use this when a user references media by name, partial name, or when you need to resolve a name to an asset ID before performing operations.

## The Assets API

The `/assets` endpoint provides efficient asset discovery with filtering, sorting, and regex-based name search. This is the correct way to find assets - do NOT iterate through `get_videos()` or use non-existent methods like `get_video_by_name()`.

### Endpoint

```
GET /assets
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `collection_id` | string | - | Scope to a specific collection |
| `asset_type` | string | all | Filter by type: `video`, `audio`, `image` (comma-separated) |
| `name_pattern` | string | - | **Regex pattern** to filter by asset name (case-insensitive) |
| `sort_by` | string | `created_at` | Sort field: `name`, `duration`, `size`, `created_at` |
| `sort_order` | string | `desc` | Sort order: `asc`, `desc` |
| `min_duration` | float | - | Minimum duration in seconds |
| `max_duration` | float | - | Maximum duration in seconds |
| `min_size` | int | - | Minimum file size in bytes |
| `max_size` | int | - | Maximum file size in bytes |
| `page` | int | 1 | Page number (1-indexed) |
| `page_size` | int | 50000 | Items per page (max 50000) |

### Response

```json
{
  "assets": [
    {
      "id": "m-abc123",
      "type": "video",
      "name": "Product Demo 2024",
      "length": 125.5,
      "size": 52428800,
      "created_at": "2024-01-15T10:30:00Z",
      "stream_url": "https://...",
      "player_url": "https://...",
      "thumbnail_url": "https://..."
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 50000,
    "total_count": 42,
    "total_pages": 1
  }
}
```

## Finding Assets by Name

Use the `name_pattern` parameter with a regex pattern to search by name.

### Exact Name Match

```python
# Find video named exactly "Product Demo"
result = conn.get(path="/assets", params={
    "collection_id": collection_id,
    "asset_type": "video",
    "name_pattern": "^Product Demo$"
})
```

### Partial / Contains Match

```python
# Find any asset containing "Huberman" in the name
result = conn.get(path="/assets", params={
    "collection_id": collection_id,
    "name_pattern": ".*Huberman.*"
})
```

### Case-Insensitive Fuzzy Match

```python
# Find videos matching "meeting" anywhere in name (case-insensitive)
result = conn.get(path="/assets", params={
    "collection_id": collection_id,
    "asset_type": "video",
    "name_pattern": "(?i).*meeting.*"
})
```

### Common Regex Patterns

| User Input | Regex Pattern | Description |
|------------|---------------|-------------|
| `"Product Demo"` | `(?i).*product.*demo.*` | Contains both words, any order |
| `"Dr. Huberman"` | `(?i).*huberman.*` | Contains "huberman" |
| `"Meeting 2024"` | `(?i).*meeting.*2024.*` | Contains "meeting" and "2024" |
| `"Screen Recording"` | `(?i)^screen recording` | Starts with "screen recording" |

## Fetching by ID

When you have asset IDs, fetch them directly:

```python
# Single asset by ID
video = coll.get_video("m-abc123")
audio = coll.get_audio("a-xyz789")
image = coll.get_image("img-def456")
```

### ID Prefixes

| Type | Prefix | Example |
|------|--------|---------|
| Video | `m-` | `m-abc123` |
| Audio | `a-` | `a-xyz789` |
| Image | `img-` | `img-def456` |

## Workflow: Resolve Name to Asset

When a user provides a name instead of an ID, resolve it first:

```python
def resolve_asset_by_name(conn, collection_id, name, asset_type=None):
    """
    Find an asset by name using the assets API.
    
    Returns the first matching asset or None.
    """
    # Build regex pattern for fuzzy matching
    # Escape special characters and create contains pattern
    import re
    escaped = re.escape(name)
    pattern = f"(?i).*{escaped}.*"
    
    params = {
        "collection_id": collection_id,
        "name_pattern": pattern,
        "page_size": 10  # Only need first few matches
    }
    if asset_type:
        params["asset_type"] = asset_type
    
    result = conn.get(path="/assets", params=params)
    assets = result.get("assets", [])
    
    if not assets:
        return None
    
    # Return exact match if found, otherwise first partial match
    name_lower = name.lower()
    for asset in assets:
        if asset.get("name", "").lower() == name_lower:
            return asset
    
    return assets[0]


# Usage
asset = resolve_asset_by_name(conn, collection_id, "Dr. Huberman Sleep Tips", asset_type="video")
if asset:
    video_id = asset["id"]
    video = coll.get_video(video_id)
    # Now proceed with operations
else:
    print("Asset not found")
```

## Critical Rules

### ALWAYS search by name BEFORE operations

When a user mentions an asset by name:

```
User: "Summarize the Huberman podcast"
```

1. **First**: Search for the asset using the assets API
2. **Then**: Get the asset ID from results
3. **Finally**: Perform the operation

```python
# Step 1: Find the asset
result = conn.get(path="/assets", params={
    "collection_id": collection_id,
    "asset_type": "video",
    "name_pattern": "(?i).*huberman.*podcast.*"
})

assets = result.get("assets", [])
if not assets:
    raise ValueError("Video not found. Please check the name.")

# Step 2: Get the ID
video_id = assets[0]["id"]

# Step 3: Perform operation
video = coll.get_video(video_id)
video.index_spoken_words(force=True)
# ... continue with summarization
```

### NEVER do these

| Wrong | Why | Correct |
|-------|-----|---------|
| `coll.get_video_by_name("...")` | Method doesn't exist | Use assets API with `name_pattern` |
| `coll.get_video("My Video Title")` | Names are not IDs | Search first, then use returned ID |
| `for v in coll.get_videos(): if v.name == ...` | Inefficient, doesn't scale | Use assets API with `name_pattern` |
| `coll.get_video("local-xxx")` | Invalid ID format | Only `m-`, `a-`, `img-` prefixes are valid |

### Invalid ID Formats

These will always fail:

| Format | Problem |
|--------|---------|
| `local-xxx` | Not a valid prefix |
| `genai-video-xxx` | Temporary generation ID, may not persist |
| `My Video Title` | Names are not IDs |
| `3_idiots` | File names are not IDs |

## Examples

### Find and Search a Video

```python
# User says: "Search for mentions of AI in the team meeting video"

# 1. Find the video
result = conn.get(path="/assets", params={
    "collection_id": collection_id,
    "asset_type": "video",
    "name_pattern": "(?i).*team.*meeting.*"
})

if not result.get("assets"):
    raise ValueError("Could not find a video matching 'team meeting'")

video_id = result["assets"][0]["id"]

# 2. Get video and search
video = coll.get_video(video_id)
video.index_spoken_words(force=True)
results = video.search("AI", search_type=SearchType.semantic)
```

### Find and Edit a Video

```python
# User says: "Trim the first 30 seconds from the product demo"

# 1. Find the video
result = conn.get(path="/assets", params={
    "collection_id": collection_id,
    "asset_type": "video",
    "name_pattern": "(?i).*product.*demo.*"
})

if not result.get("assets"):
    raise ValueError("Could not find a video matching 'product demo'")

video_id = result["assets"][0]["id"]
video = coll.get_video(video_id)

# 2. Create timeline starting at 30s
from videodb.timeline import Timeline
from videodb.asset import VideoAsset

timeline = Timeline(conn)
timeline.add_inline(VideoAsset(asset_id=video.id, start=30))
stream_url = timeline.generate_stream()
```

### List All Videos in Collection

```python
# User says: "What videos do I have?"

result = conn.get(path="/assets", params={
    "collection_id": collection_id,
    "asset_type": "video",
    "sort_by": "created_at",
    "sort_order": "desc"
})

for asset in result.get("assets", []):
    print(f"- {asset['name']} ({asset['id']}) - {asset.get('length', 0):.1f}s")
```

## Handling Special Characters in Names

Video names often contain special characters (`|`, `&`, `[]`, parentheses) that break regex patterns, even with `re.escape()`. The VideoDB API's regex engine may reject complex escaped patterns.

### Problem

```python
# This FAILS for names with | or []
target_name = "How to Feel Energized & Sleep Better | Dr. Andrew Huberman"
escaped = re.escape(target_name)  # Creates complex escape sequences
pattern = f"(?i).*{escaped}.*"
# Error: "Invalid request: Invalid name_pattern"
```

### Solution: Keyword-Based Search

Extract 2-3 distinctive keywords instead of escaping the full name:

```python
import re

def get_search_keywords(name):
    """Extract searchable keywords from a name with special characters."""
    # Remove special characters and extract words
    words = re.findall(r'\b[a-zA-Z0-9]{3,}\b', name)
    # Filter out common words, keep distinctive ones
    stopwords = {'the', 'and', 'for', 'with', 'from', 'this', 'that', 'how'}
    keywords = [w for w in words if w.lower() not in stopwords]
    return keywords[:3]  # Use top 3 keywords

# Usage
target_name = "How to Feel Energized & Sleep Better | Dr. Andrew Huberman"
keywords = get_search_keywords(target_name)  # ['Feel', 'Energized', 'Sleep']

# Build simpler pattern
pattern = f"(?i).*{'.*'.join(keywords)}.*"  # (?i).*Feel.*Energized.*Sleep.*
```

### Fallback Strategy

Try exact match first, fall back to keyword search:

```python
import re

def find_asset_by_name(conn, collection_id, name, asset_type="video"):
    """Find asset with fallback for special characters."""
    
    # Strategy 1: Try escaped pattern (works for simple names)
    try:
        escaped = re.escape(name)
        result = conn.get(path="/assets", params={
            "collection_id": collection_id,
            "asset_type": asset_type,
            "name_pattern": f"(?i).*{escaped}.*",
            "page_size": 10
        })
        if result.get("assets"):
            return result["assets"]
    except Exception:
        pass  # Pattern rejected, try fallback
    
    # Strategy 2: Keyword-based search
    words = re.findall(r'\b[a-zA-Z0-9]{4,}\b', name)
    if words:
        # Use longest/most distinctive words
        keywords = sorted(words, key=len, reverse=True)[:2]
        pattern = f"(?i).*{'.*'.join(keywords)}.*"
        result = conn.get(path="/assets", params={
            "collection_id": collection_id,
            "asset_type": asset_type,
            "name_pattern": pattern,
            "page_size": 10
        })
        if result.get("assets"):
            return result["assets"]
    
    return []
```

### Characters That Cause Issues

| Character | Example | Problem |
|-----------|---------|---------|
| `\|` (pipe) | `"Topic A \| Topic B"` | Regex alternation confusion |
| `[]` (brackets) | `"[Dubbed in hi] Video"` | Character class syntax |
| `()` (parens) | `"Meeting (2024)"` | Grouping syntax |
| `&` (ampersand) | `"Sleep & Energy"` | Usually OK but combine with others |

### Best Practice

For names with special characters, **prefer keyword extraction over full regex escaping**:

```python
# AVOID: Full name with re.escape() - may fail
pattern = f"(?i).*{re.escape(full_name)}.*"

# PREFER: Keyword-based matching - more reliable
keywords = ["Huberman", "Sleep", "Energy"]
pattern = f"(?i).*Huberman.*"
```

## Tips

- **Always use regex patterns**: The `name_pattern` parameter uses regex. Wrap user input with `(?i).*{name}.*` for fuzzy matching.
- **Escape special characters**: Use `re.escape()` on user input before building regex — but use keyword fallback for complex names.
- **Search first, then act**: Never assume an asset exists. Always verify via the assets API.
- **Return helpful errors**: If no match found, tell the user what's available.
- **Use asset_type filter**: Narrow results by specifying `video`, `audio`, or `image`.
