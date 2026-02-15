# Migration Summary: Meeting History & Analytics

## What Changed

### 1. Models Updated
**Files Modified:**
- `backend/models/user.py` - Added relationships: `meetings`, `usage_records`
- `backend/models/meeting.py` - Added relationships: `user`, `usage_records`; Added index: `idx_meeting_user_created(user_id, created_at)`
- `backend/models/usage_record.py` - Added relationships: `user`, `meeting`; Added indices: `idx_usage_user_created(user_id, created_at)`, `idx_usage_created(created_at)`

### 2. Schemas Added
**File:** `backend/schemas/meeting.py`
- `MeetingMetadata` - Meeting with preview & metadata only
- `MeetingDetail` - Full meeting data with usage info
- `UserStats` - User's aggregated cost/token/meeting stats
- `DailyStats` - Per-day breakdown
- `GlobalStats` - System-wide stats
- `PaginatedMeetings` - Paginated meeting list wrapper

### 3. New Service Layer
**File Created:** `backend/services/analytics_service.py`
- `get_user_stats()` - Aggregated user stats with date range
- `get_user_daily_stats()` - Daily breakdown for user
- `get_global_stats()` - System-wide aggregates
- `get_global_daily_stats()` - Global daily breakdown
- `get_user_top_expensive_meetings()` - Top 10 expensive meetings
- `parse_date_range()` - Date range parsing (presets: today/7d/30d/all + custom)

**File Extended:** `backend/services/meeting_service.py`
- `get_user_meetings()` - Paginated meeting list (metadata only)
- `get_meeting_detail()` - Full meeting data with auth check

### 4. API Endpoints Added
**File:** `backend/api/meetings.py`

**User-Scoped (Authenticated):**
- `GET /meetings` - List user's meetings (paginated, metadata only)
- `GET /meetings/{meeting_id}` - Get full meeting details
- `GET /analytics/user` - User stats (date range support)
- `GET /analytics/user/daily` - User daily breakdown

**Admin-Scoped (TODO: Add admin role check):**
- `GET /analytics/global` - Global stats
- `GET /analytics/global/daily` - Global daily breakdown

## How to Apply

### Option 1: Automatic (Recommended)
Run the migration helper:
```bash
cd backend
python -m scripts.apply_migrations
```

### Option 2: Manual
Execute the following SQL statements or use your ORM's migration tool:

## Deduplication Status
✅ Already Implemented
- DB level: `transcript_hash` unique constraint
- Service level: Check before insert, handle race conditions
- Both are enforced in `process_meeting_transcript()`

## Testing Checklist
- [ ] Access `/meetings` → returns paginated list
- [ ] Access `/meetings/{meeting_id}` → returns full detail or 404 if not owner
- [ ] Access `/analytics/user?preset=today` → returns user stats
- [ ] Access `/analytics/user/daily?preset=7d` → returns daily breakdown
- [ ] Access `/analytics/global` → returns global stats (implement admin check)
- [ ] Same transcript twice → only one meeting persisted
- [ ] Different users, same transcript → separate meetings (both have metadata)

## Next Steps
1. Add admin role check to global analytics endpoints (see TODO in api/meetings.py)
2. Run migration script to apply indices
3. Test endpoints with sample data
4. Monitor query performance with new indices
