# Next Steps -- EdgeIQ Growth Roadmap

> Path A (B2C subscription) + Path D (content/media + tool)
> combined into a single execution plan.

## Build Priority

Build in this order. Each step unlocks the next.

| Priority | Feature | Why First |
|---|---|---|
| 1 | Verified Track Record | Zero-cost, 5 min to start, every day delayed is proof you can never get back |
| 2 | Promo Optimizer | Tool pays for itself day 1 -- easiest subscriber justification |
| 3 | Bet Tracker + Tax Engine | Year-round stickiness, eliminates seasonal churn |
| 4 | Contextualized Alerts | Premium tier differentiator, Claude API moat |
| 5 | Community Leaderboard | Network effects -- the only structural moat in this space |
| 6 | State Personalization | Conversion optimization, makes every recommendation actionable |
| 7 | Hedge Calculator | Loyalty builder, locks in profit feeling |

---

## 1. Cryptographically Verified Track Record

**Problem**: Every tout claims 65% win rate. Nobody can prove it. Trust is the #1 barrier to conversion.

**What to build**:
- SHA-256 hash every pick (game, selection, odds, timestamp) BEFORE game start
- Commit hashes to a public GitHub repo or blockchain timestamp
- After settlement, anyone can verify the hash matches
- Public dashboard showing verified CLV, ROI, and win rate
- Mathematically impossible to fake -- picks are timestamped pre-game

**Why this is #1**:
- Zero cost to implement
- Once you have 6-12 months of verified positive CLV, it becomes a permanent moat
- Competitors can't catch up without waiting their own 12 months
- Media outlets will cover "the only sports betting tool with cryptographically verified results"
- Converts skeptics into subscribers because proof is public

**Revenue impact**: Reduces churn 30-50%. Increases free-to-paid conversion because proof is visible before purchase.

**Build scope**: Small. SHA-256 hash function, public commit script, results dashboard page.

---

## 2. Sportsbook Promo Optimizer

**Problem**: The money most bettors leave on the table isn't bad picks -- it's unused or misused promos. A $1,000 deposit match converts to $800-950 guaranteed profit. Most bettors don't know how.

**What to build**:
- Track active promos across all major books (DraftKings, FanDuel, BetMGM, Caesars, etc.)
- Calculate guaranteed conversion value of each promo
- Step-by-step hedging instructions personalized to which books the user has:
  "Deposit $500 on DraftKings, bet LAL ML at -110, hedge on FanDuel at +112 -- guaranteed $430 profit"
- Track which promos user has already used (they're one-time)
- Alert when new promos drop
- New state launch tracker (new states = massive promo waves)

**Why this matters**:
- Casual bettors (largest market) understand "guaranteed $430" better than "+3.2% CLV"
- RISK-FREE -- tool pays for itself on day 1
- No churn when users are making guaranteed money
- Gateway: users sign up for promos, stay for the +EV engine
- New state launches create demand spikes (Missouri, Maine, Vermont all recent)

**Revenue impact**: Justifies subscription immediately. "Pay $49/mo, make $500/mo in promos" is the easiest sell in the industry.

**Competition**: OddsJam has basic promo tracking. Nobody does full conversion calculator with personalized hedging instructions based on user's active sportsbook accounts.

**Build scope**: Medium. Promo database (manual curation initially), hedge calculator, user account registry, alert system.

---

## 3. Automated Bet Tracker + Tax Engine

**Problem**: Every bettor in the US must report gambling income. Most use spreadsheets or nothing. At tax time, they panic.

**What to build**:
- Manual entry + CSV import from sportsbook transaction history
- Automatic P&L by sport, book, market type, time period
- Tax report generator:
  - Itemized wins and losses
  - Estimated tax liability (federal + state)
  - Deductible loss calculations
  - State-specific rules (NY doesn't allow loss deductions, for example)
- Year-round utility -- not seasonal

**Why this matters**:
- **Sticky year-round**: Bettors cancel picks services in the offseason. Nobody cancels their bet tracker because 6 months of tax data is in it.
- Every serious bettor needs this. It's not optional.
- Creates switching costs: moving to a competitor means losing your history
- Cross-sell: free bet tracker tier funnels into paid +EV and promo tools

**Revenue impact**: Eliminates seasonal churn -- the #1 killer of sports betting subscriptions. A bettor tracking in January is still paying in July.

**Build scope**: Medium. Bet entry UI, CSV parser for major books (DraftKings/FanDuel export formats), P&L aggregation, tax calculation engine with state tax tables.

---

## 4. Real-Time Contextualized Alerts (Claude-Powered)

**Problem**: Speed is everything. The +EV window is 30-120 seconds. A raw alert saying "+EV on LAL -3.5" doesn't tell the user WHY or build confidence to act fast.

**What to build**:
- Push notification / SMS / Telegram when +EV opportunity detected
- Each alert includes:
  - The bet: LAL -3.5 at -108 on DraftKings
  - The edge: model 56.2%, market 52.1%, EV +4.1%
  - The WHY (Claude-generated): "AD listed questionable. Beat reporter: 'AD went through full shootaround, looked good.' Model: 72% he plays. Line should be LAL -5. Window ~2 min."
  - Kelly sizing for the user's bankroll
  - One-tap deep link to the sportsbook app
- Alert throttling: max 5/day to prevent fatigue
- User preferences: which sports, min EV threshold, which books

**Why this matters**:
- Nobody combines real-time odds + LLM injury analysis + personalized sizing in one alert
- Context builds trust -- users understand WHY, not just WHAT
- Push notifications drive daily active usage and engagement
- The Claude injury parser is the most unique piece of the stack -- this is where it becomes a product differentiator, not just a feature

**Revenue impact**: This is the premium tier feature ($99-149/mo). Serious bettors pay for speed + context. Upgrades Sharp subscribers to Pro.

**Build scope**: Large. Real-time pipeline (Celery + Redis pub/sub), Claude API calls per alert, push notification infrastructure (Firebase or Twilio), user preference storage, deep link generation.

---

## 5. Community Leaderboard by CLV (Network Effects)

**Problem**: The tool has zero network effects. One user's usage doesn't make it better for others. This is the structural weakness competitors can exploit.

**What to build**:
- Users opt-in to share verified bet history
- Public leaderboard ranked by CLV (NOT win rate -- this is the philosophical differentiator)
- Follow top performers, see their recent plays and bet patterns
- "Consensus" view: what % of EdgeIQ users are on each side of a game
- Sharp vs public split (EdgeIQ users ARE the sharp signal)
- Community discussion per game
- Seasonal awards / badges for consistent CLV

**Why this matters**:
- **Network effects**: More users = more data = better consensus signal = more valuable tool
- **Social proof**: "Top 10 EdgeIQ users are +4.2% CLV over 6 months" is marketing that writes itself
- **Retention**: Community keeps people engaged during losing streaks
- **Content**: Leaderboard rankings become content for newsletters and Twitter
- **Moat**: Competitors can copy code but not your community

**Revenue impact**: Viral growth (users share leaderboard rankings). Reduced churn (social ties keep users subscribed even during cold streaks).

**Build scope**: Medium-large. User profiles, opt-in sharing, leaderboard calculations, follow system, consensus aggregation, game discussion threads.

---

## 6. State-Specific Personalization

**Problem**: Different states have different legal books, different tax rates, different promo availability. The tool shows odds from books users can't access.

**What to build**:
- On signup, user selects their state
- Tool only shows odds from books licensed in their state
- Tax calculations use their state's rules
- Promo tracker filtered to their state
- New state launch alerts: "Sports betting goes live in Missouri Sept 1 -- here are sign-up promos worth $2,400"
- Multi-state support for users who travel

**Why this matters**: Makes the tool feel built for THEM, not generic. Every recommendation is immediately actionable. Increases conversion because there's no friction ("wait, I can't use that book").

**Revenue impact**: Conversion optimization. Users who see only relevant books convert at higher rates.

**Build scope**: Small-medium. State-to-sportsbook mapping table, user state preference, filter layer on all odds/promo queries, state tax rate table.

---

## 7. Automated Hedge Calculator

**Problem**: When a live bet is winning or a parlay has 3/4 legs hit, most bettors don't know the optimal hedge to lock in profit.

**What to build**:
- Input: open bet (team, odds, stake, current status)
- Scan current live odds across all available books
- Calculate two options:
  - **Lock in profit**: guaranteed $ regardless of outcome
  - **Minimize risk**: reduce downside while keeping upside
- Show exactly which book, which bet, what stake
- Works for straight bets, parlays (partial hedging), and futures
- "Hedge now" deep link to the sportsbook app

**Why this matters**: Turns "maybe I'll win $500" into "I'm guaranteed $320." That locked-in profit feeling creates enormous tool loyalty.

**Revenue impact**: Loyalty and word-of-mouth. Users tell friends "this tool just locked in $320 for me."

**Build scope**: Medium. Live odds integration, hedge math engine (already have the odds conversion functions), multi-book comparison, deep links.

---

## Revenue Model

### Subscription Tiers

| Tier | Price | Includes |
|---|---|---|
| **Free** | $0 | Yesterday's CLV report, 1 pick/day, bet tracker (limited), public leaderboard |
| **Sharp** | $49/mo or $399/yr | Real-time +EV alerts, promo optimizer, full bet tracker, tax reports, contextual splits, state personalization |
| **Pro** | $149/mo | Everything in Sharp + Claude contextualized alerts (with WHY), correlated parlay builder, hedge calculator, API access, priority alert speed |

### Non-Subscription Revenue

| Stream | How It Works | Estimated Monthly |
|---|---|---|
| **Sportsbook affiliates** | $200-500 per new depositor referred through promo optimizer | $10K-25K/mo at scale |
| **Newsletter sponsors** | Sportsbooks pay for placement in daily newsletter | $2-5K/mo |
| **Seasonal content** | Pre-season guides, playoff packages | Spiky but meaningful |

### Projected Revenue

**Year 1 (realistic with execution):**

| Stream | Monthly | Annual |
|---|---|---|
| 300 Sharp subscribers | $14,700 | $176K |
| 50 Pro subscribers | $7,450 | $89K |
| Affiliate referrals | $8,000 | $96K |
| Newsletter sponsors | $3,000 | $36K |
| **Total** | **$33,150** | **$397K** |
| Costs (infra, APIs, tools) | -$2,000 | -$24K |
| **Net** | **$31,150** | **$373K** |

**Year 2-3 (with verified track record + community):**

Subscriber base grows 3-5x once 12 months of verified CLV results exist. Affiliate revenue scales with audience. $800K-1.5M ARR realistic by year 2 if the model actually has edge.

---

## Content Strategy (Path D)

Content is the acquisition engine. The tool is the monetization layer.

### Daily

- **Morning Line newsletter**: Today's model picks + injury impact analysis + promo alerts
- **Twitter/X thread**: 1-2 best +EV plays with reasoning (builds audience)
- **Telegram/Discord alert**: Real-time +EV opportunities for paid subscribers

### Weekly

- **CLV Report Card**: Public, verified results from the past week (builds trust)
- **"The Sharps Are On..." segment**: Line movement analysis using EdgeIQ data
- **Promo Roundup**: Best active promos across all books this week

### Monthly

- **Model Performance Report**: Accuracy, Brier score, ROI by sport
- **Leaderboard Update**: Top community members by CLV
- **Market Insight**: Which books are sharpest, which are softest, where is edge concentrating

### Seasonal

- **Pre-season guides**: NFL preview, NBA preview (SEO + lead gen)
- **New state launch guides**: "Michigan sports betting just went live -- here's $3,200 in sign-up promos" (affiliate revenue spike)

---

## What Creates the Moat

Code is copyable. These five things are not:

1. **12+ months of cryptographically verified CLV** -- Can't be bought, faked, or accelerated
2. **Proprietary historical odds database** -- Start collecting NOW, grows daily
3. **Community with network effects** -- Competitors can't clone your users
4. **Content audience** -- Newsletter subscribers and Twitter followers take years to build
5. **Affiliate relationships** -- Sportsbook partner deals improve with volume

Every day you wait on #1 and #2 is a day of compounding advantage you lose. Start hashing picks and collecting odds data today, even before building anything else.
