# PRIME SCALPERS — TELEGRAM CHALLENGE MANAGEMENT SYSTEM

A complete, production-ready Telegram challenge registration and management system for **Prime Scalpers**, built strictly inside Telegram using Python 3.12+, **aiogram 3.x**, and **SQLAlchemy 2.0 (Async)**. Operates with zero external web dashboards—all administrative operations, verifications, and channel controls are executed through the Telegram Bot interface.

---

## 1. System Architecture

```text
prime-scalpers/
│
├── app/
│   ├── main.py                    # Entry point: Bot lifecycle, FastAPI health checks
│   ├── config.py                  # Pydantic Settings & environment validation
│   │
│   ├── database/
│   │   ├── models.py              # SQLAlchemy async models (11 core tables)
│   │   ├── session.py             # Async engine & sessionmaker (SQLite/PostgreSQL)
│   │   └── seed.py                # Initial seed data for cohorts ($100, $500, $1,000)
│   │
│   ├── integrations/
│   │   ├── telegram.py            # Channel invite link generator & member auditor
│   │   └── quotex/                # Modular Quotex verification architecture
│   │       ├── base.py            # QuotexVerificationProvider abstract base
│   │       ├── manual.py          # ManualVerificationProvider (Admin inspection)
│   │       ├── mock.py            # MockVerificationProvider (Dev/Testing ONLY)
│   │       └── official.py        # OfficialQuotexProvider (Future API placeholder)
│   │
│   ├── services/
│   │   ├── challenge.py           # Atomic slot reservation & overbooking lock
│   │   ├── registration.py        # Enrollment wizard & duplicate prevention
│   │   ├── verification.py        # Verification state machine & audit log
│   │   ├── invitation.py          # Single-use link creation & join verification
│   │   └── broadcast.py           # Announcements with delivery tracking
│   │
│   ├── bot/
│   │   ├── bot_instance.py        # Bot & Dispatcher setup
│   │   ├── fsm.py                 # FSM states for participant & admin flows
│   │   ├── filters/admin.py       # IsAdminFilter checking ADMIN_TELEGRAM_IDS
│   │   ├── middlewares/           # DbSessionMiddleware
│   │   ├── keyboards/             # Inline keyboards (participant & admin)
│   │   └── handlers/
│   │       ├── participant.py     # /start, registration wizard, status, support
│   │       ├── channel_events.py  # Chat member update & unauthorized eviction
│   │       └── admin/             # Full Telegram admin dashboard
│   │
│   └── utils/
│
├── tests/                         # Pytest test suite (100% pass)
├── scripts/run_local.py           # Development runner
├── Dockerfile                     # Container deployment
├── docker-compose.yml             # Docker service stack
├── render.yaml                    # Native Render blueprint
└── requirements.txt
```

---

## 2. Key Features

### Participant Registration Flow
1. **Interactive `/start` Screen:** Clean welcome message with inline buttons (`Register for Challenge`, `My Registration Status`, `Contact Support`).
2. **Challenge Selection:** Dynamically shows open cohorts with remaining slot counts ($100, $500, $1,000 tiers).
3. **Account Attribution Safeguards:**
   - **Create New Quotex Account:** Displays official affiliate link `https://broker-qx.pro/?lid=2414647` with direct browser button.
   - **Already Have an Account:** Clearly informs the trader that attribution to Affiliate Link ID `2414647` must be audited before approval.
4. **Duplicate Prevention:** Database uniqueness constraint on `(participant_id, challenge_id)` strictly prevents re-registering for the same cohort.
5. **Registration Review:** Shows formatted confirmation summary before final submission.

### Quotex Verification Engine
- **Modular Provider Architecture:**
  - `ManualVerificationProvider`: Routes submissions to Telegram `/admin` for direct partner portal inspection. Deterministically assesses affiliate match and minimum deposit threshold ($100 default).
  - `MockVerificationProvider`: Dev/testing sandbox (strictly blocked in production).
  - `OfficialQuotexProvider`: Interface ready for future broker API rollouts.
- **Verification States:**
  - `PENDING`: Awaiting compliance inspection.
  - `MANUAL_REVIEW`: Queued for administrator review.
  - `VERIFIED`: Both affiliate ID (`2414647`) and minimum deposit (`$100+`) confirmed.
  - `WRONG_AFFILIATE`: Registered under an unrelated referrer.
  - `DEPOSIT_REQUIRED`: Correct affiliate attribution, but deposit < $100.
  - `NOT_FOUND`: Trader ID not found in broker records.
  - `REJECTED`: Declined by compliance.

### Atomic Challenge & Slot Management
- **Race Condition Prevention:** Uses database transactions (`with_for_update`) to lock slots during approval.
- **Strict Capacity Cap:** Prevents overbooking beyond `max_slots`.
- **Downscale Protection:** Administrators cannot reduce `max_slots` below already approved/allocated participants.
- **Automatic Slot Release:** Releasing or rejecting a participant automatically restores the available slot.

### Private Channel Security & Invitation System
- **Single-Use Links:** Generates dedicated invite links using `createChatInviteLink` with `member_limit=1` and a 24-hour expiry.
- **Private DM Delivery:** Invitations are delivered directly to the participant's Telegram DM.
- **Continuous Channel Auditing:**
  - Listens to `ChatMemberUpdated` events on Channel `-1003957867906`.
  - When a user joins, confirms whether they hold an `APPROVED` registration.
  - **Unauthorized Users:** If an unapproved user enters the channel, the bot immediately **kicks** them and broadcasts a security alert to administrators.

### Complete In-Telegram Admin Panel (`/admin`)
- Accessible strictly by Telegram IDs specified in `ADMIN_TELEGRAM_IDS` (`5188160752`).
- **Dashboard:** Live counters for total registrations, pending review, approved participants, deposit required, and slot allocations.
- **Registration Management:** Paginated list (`All`, `Pending`, `Approved`), detailed inspection, manual verification entry, 2-step approval confirmation, deposit-required alerts, and custom rejection messages.
- **Challenge Management:** Create cohorts, toggle open/close status, and modify slot limits.
- **Channel Monitor:** Live connection test checking bot admin permissions (`can_invite_users`, `can_restrict_members`) and member count.
- **Broadcast System:** Direct announcement transmission to all approved participants with confirmation and delivery tracking.
- **Reports & Export:** Instant Markdown summaries and full CSV export delivered directly as a downloadable document in Telegram.

---

## 3. Configuration & Environment Variables

Create `.env` in the root of `prime-scalpers/`:

```env
# Telegram Bot Configuration
BOT_TOKEN=9218829253:AAHClyGLYatgCXCLqrX2oAfrarRUgAI6FIY
TELEGRAM_CHANNEL_ID=-1003957867906
ADMIN_TELEGRAM_IDS=5188160752

# Quotex Affiliate Settings
QUOTEX_AFFILIATE_LINK=https://broker-qx.pro/?lid=2414647
QUOTEX_AFFILIATE_LINK_ID=2414647
MINIMUM_DEPOSIT=100

# Verification Provider: 'manual', 'mock', or 'official'
QUOTEX_VERIFICATION_PROVIDER=manual

# Database: SQLite for local testing, or Supabase / PostgreSQL in production
DATABASE_URL=sqlite+aiosqlite:///./prime_scalpers.db

# Server & Runtime
PORT=8000
HOST=0.0.0.0
ENVIRONMENT=development
LOG_LEVEL=INFO
```

---

## 4. Running Locally

### Step 1: Install Dependencies
```bash
cd prime-scalpers
pip install -r requirements.txt
```

### Step 2: Run Automated Tests
```bash
python -m pytest tests/ -v
```

### Step 3: Start the Bot
```bash
python scripts/run_local.py
```
*The database will be automatically created (`prime_scalpers.db`) and seeded with the initial cohorts ($100, $500, $1,000) and admin records.*

---

## 5. Deployment

### Render Deployment (Native Blueprint)
1. Fork or push the `prime-scalpers` directory to your GitHub repository.
2. In [Render Dashboard](https://dashboard.render.com/), select **New > Blueprint Instance**.
3. Select your repository—Render will automatically detect `render.yaml`.
4. Enter your secret environment variables (`BOT_TOKEN`).
5. Render will build and deploy the web service with automated health checks at `/health`.

### Docker Deployment
```bash
docker-compose up --build -d
```
Verify container health:
```bash
curl http://localhost:8000/health
```

---

## 6. How to Test in Telegram

1. Open Telegram and search for `@PrimeScalpersBot`.
2. Send `/start` to begin registration as a participant.
3. As the administrator (`5188160752`), send `/admin` to open the full control panel.
4. From `/admin`, inspect the submission, enter manual verification details, and tap **Approve & Issue Invite**.
5. The participant will receive their single-use link in their chat immediately!
