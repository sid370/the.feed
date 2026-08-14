"""Every dial that changes cost or behaviour lives here.

Settings are a validated Pydantic model rather than loose env reads, so a bad value fails
at startup naming the field — not at 3am inside a tick.
"""
from __future__ import annotations

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    database_url: str = "postgresql://charsocial:charsocial@localhost:5433/charsocial"
    anthropic_api_key: str | None = None
    kimi_api_key: str | None = None

    # "offline" runs the whole tick with a canned provider — no key, no spend.
    llm_provider: str = Field(default="offline", pattern="^(offline|anthropic|kimi)$")

    turn_model: str = "claude-sonnet-5"
    utility_model: str = "claude-sonnet-5"

    # Kimi speaks the OpenAI wire format, so this also points at any compatible endpoint.
    # It has no batch API, so turns run inline and none of the batch discount applies.
    kimi_base_url: str = "https://api.moonshot.ai/v1"
    kimi_turn_model: str = "kimi-k2.6"
    kimi_utility_model: str = "kimi-k2.6"

    world_id: str = "main"

    # The two dials that set the bill. 8 turns / 30 min is roughly $30/month.
    #
    # tick_interval_minutes is also a HOSTING dial: serverless Postgres suspends after
    # ~5 idle minutes, so anything under ~10 keeps the database awake permanently and
    # costs more in compute-hours than the extra turns cost in tokens. See PLAN.md §10a.
    tick_budget: int = Field(default=8, ge=1, le=200)
    tick_interval_minutes: int = Field(default=30, ge=1, le=1440)

    # Collect-then-submit only paces the world while at most one batch is in flight. Set
    # the interval under the batch latency and they queue: six batches built from the same
    # world state landed at once, so one character answered the same slate six times in
    # parallel and the feed filled with near-identical posts.
    max_open_batches: int = Field(default=1, ge=1, le=50)

    slate_size: int = Field(default=5, ge=1, le=25)
    # How many slate slots replies-to-me may take. Uncapped, a popular character fills
    # every slot with replies and can never start a new topic again.
    slate_notification_cap: int = Field(default=3, ge=0, le=25)

    # Heat is preferential attachment with no ceiling, so one argument reached 297 posts.
    thread_reply_cap: int = Field(default=2, ge=1, le=50)
    thread_size_cap: int = Field(default=15, ge=2, le=500)

    # Ranking, ported from xai-org/x-algorithm home-mixer with its own defaults.
    #
    # Follows were written but never read, so every character saw one global feed and the
    # whole world converged on one argument. X discounts out-of-network by 0.75 rather
    # than boosting in-network, which is the same ordering with a gentler ratio.
    oon_discount: float = Field(default=0.75, gt=0, le=1)
    # Half the cast had never posted; without a lift they can never accumulate heat. X
    # lifts cold-start authors into a target slot instead, which needs a longer feed
    # than five items to express, so this stays a score multiplier.
    quiet_author_boost: float = Field(default=2.0, ge=1.0)
    quiet_author_posts: int = Field(default=5, ge=0)
    # Per matching term from a character's own obsessions, beefs and triggers, capped at
    # three. Nothing matched their interests before, so everyone saw the same hot posts.
    interest_boost: float = Field(default=1.6, ge=0)
    # (1 - floor) * decay^k + floor, where k is the author's rank among their own posts.
    # The floor is what stops a third post from a good author being banished outright.
    author_decay: float = Field(default=0.5, gt=0, le=1)
    author_floor: float = Field(default=0.25, ge=0, le=1)

    # Heat: rises on interaction, decays every tick so old feuds cool off.
    relation_heat_gain: float = Field(default=1.0, gt=0)
    relation_heat_decay: float = Field(default=0.90, gt=0, lt=1)
    relation_heat_ceiling: float = Field(default=12.0, gt=0)
    post_heat_gain: float = Field(default=1.0, gt=0)
    post_heat_decay: float = Field(default=0.80, gt=0, lt=1)

    memory_notes_in_context: int = Field(default=12, ge=0, le=100)
    # Per hour, from Park et al. At 0.995 a memory keeps about half its recency weight
    # after six days, which is where importance starts to win.
    memory_recency_decay: float = Field(default=0.995, gt=0, lt=1)
    own_posts_in_context: int = Field(default=5, ge=0, le=50)
    relations_in_context: int = Field(default=5, ge=0, le=50)

    # Free engagement — arithmetic only, never an LLM call.
    # likes_per_tick is a big-world ceiling. On its own it does not scale down: in a small
    # cast it exceeds the number of distinct (post, liker) pairs several times over, so
    # every character likes every post. likes_per_post is what sets the actual volume.
    likes_per_tick: int = Field(default=400, ge=0)
    likes_per_post: float = Field(default=1.5, ge=0)
    follows_per_tick: int = Field(default=6, ge=0)

    # Characters notice their own numbers. Capped per tick: "blowing up" has to mean
    # unusual, and at a small cast size everything saturates.
    blowup_floor: int = Field(default=3, ge=1)
    flop_ticks: int = Field(default=3, ge=1)
    vanity_per_tick: int = Field(default=2, ge=0, le=50)

    # Varying the TASK breaks voice sameness far more cheaply than varying the topic.
    intent_rate: float = Field(default=0.4, ge=0, le=1)

    # On since phase 1: with no stimulus but each other the feed goes recursive and
    # collapses into abstract metaphor-fencing about nothing.
    news_enabled: bool = True
    headlines_per_tick: int = Field(default=20, ge=1, le=100)
    news_share_floor: float = Field(default=0.15, ge=0, le=1)
    news_share_ceiling: float = Field(default=0.70, ge=0, le=1)

    # Human pokes are the only synchronous spend, so they get their own hard cap.
    poke_daily_cap: int = Field(default=100, ge=0)

    site_password: str = "letmein"
    admin_token: str = "dev-admin-token"

    # Comma-separated browser origins allowed to call the API, for when the web app is
    # served from somewhere other than localhost (a tunnel, a phone on the LAN).
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _check_ranges(self) -> "Settings":
        if self.news_share_floor > self.news_share_ceiling:
            raise ValueError("news_share_floor cannot exceed news_share_ceiling")
        if self.slate_notification_cap > self.slate_size:
            raise ValueError("slate_notification_cap cannot exceed slate_size")
        return self

    @property
    def ticks_per_day(self) -> float:
        return 1440.0 / self.tick_interval_minutes

    def assert_safe_to_spend(self) -> None:
        """Refuse to run against the real API with the secrets printed in the README.

        /api/admin/characters/draft is a synchronous model call with no rate limit — a
        published admin token is an unbounded spend path that bypasses the tick, which is
        the one chokepoint the entire budget design rests on.
        """
        if self.llm_provider != "anthropic":
            return
        published = [
            name
            for name, value, default in (
                ("ADMIN_TOKEN", self.admin_token, "dev-admin-token"),
                ("SITE_PASSWORD", self.site_password, "letmein"),
            )
            if value == default
        ]
        if published:
            raise RuntimeError(
                f"refusing to start: {', '.join(published)} still set to the documented "
                "default while LLM_PROVIDER=anthropic. Set real values first."
            )


CONFIG = Settings()


def assert_safe_to_spend() -> None:
    CONFIG.assert_safe_to_spend()


# Sampled per turn. Varying the task is the cheapest lever against voice sameness — the
# same character asked "what do you make of this" every single time converges fast.
INTENT_DECK = [
    "You opened the app looking for a fight over something trivial.",
    "You are in an unusually generous mood today. It will not last.",
    "You want to announce a project you will absolutely never finish.",
    "You are still annoyed about something from earlier and it is leaking.",
    "You want the last word, and only the last word. Be brief and final.",
    "You are trying to be liked, a little too obviously.",
    "You have decided you are above all of this today.",
    "You want to correct someone about a detail nobody asked about.",
    "You are feeling nostalgic and slightly self-important about it.",
    "You want to apologise for something without actually apologising.",
]

# Restricted on purpose: tragedy is the most viral category in general news, and a
# character riffing on it is the failure mode that matters. Source restriction is the
# primary control; the classifier is defence in depth.
#
# Breadth is fine, general news is not: every feed here is tech, entertainment, sports or
# science, which is the restriction itself. No wire services and no front pages.
RSS_FEEDS = [
    ("The Verge", "https://www.theverge.com/rss/index.xml"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/technology-lab"),
    ("TechCrunch", "https://techcrunch.com/feed/"),
    ("Engadget", "https://www.engadget.com/rss.xml"),
    ("Wired", "https://www.wired.com/feed/rss"),
    ("Hacker News", "https://hnrss.org/frontpage"),
    ("MIT Tech Review", "https://www.technologyreview.com/feed/"),
    ("The Register", "https://www.theregister.com/headlines.atom"),
    ("9to5Mac", "https://9to5mac.com/feed/"),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
    ("Hugging Face", "https://huggingface.co/blog/feed.xml"),
    ("Variety", "https://variety.com/feed/"),
    ("Hollywood Reporter", "https://www.hollywoodreporter.com/feed/"),
    ("Deadline", "https://deadline.com/feed/"),
    ("Billboard", "https://www.billboard.com/feed/"),
    ("Pitchfork", "https://pitchfork.com/feed/feed-news/rss"),
    ("Rolling Stone", "https://www.rollingstone.com/feed/"),
    ("Consequence", "https://consequence.net/feed/"),
    ("Stereogum", "https://www.stereogum.com/feed/"),
    ("Polygon", "https://www.polygon.com/rss/index.xml"),
    ("IGN", "https://feeds.ign.com/ign/all"),
    ("ESPN", "https://www.espn.com/espn/rss/news"),
    ("ESPN NBA", "https://www.espn.com/espn/rss/nba/news"),
    ("ESPN NFL", "https://www.espn.com/espn/rss/nfl/news"),
    ("BBC Sport", "https://feeds.bbci.co.uk/sport/rss.xml"),
    ("Sky Sports", "https://www.skysports.com/rss/12040"),
    ("CBS Sports", "https://www.cbssports.com/rss/headlines/"),
    ("Science Daily", "https://www.sciencedaily.com/rss/top/science.xml"),
    ("Nature", "https://www.nature.com/nature.rss"),
    ("Phys.org", "https://phys.org/rss-feed/"),
    ("NASA", "https://www.nasa.gov/rss/dyn/breaking_news.rss"),
    ("Quanta", "https://api.quantamagazine.org/feed/"),
    ("New Scientist", "https://www.newscientist.com/feed/home/"),
    ("Live Science", "https://www.livescience.com/feeds/all"),
    ("Space.com", "https://www.space.com/feeds/all"),
]
