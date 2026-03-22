from __future__ import annotations

# Mongo fields
USER_ID = "user_id"
FILM_ID = "film_id"
REVIEW_ID = "review_id"
VALUE = "value"
TEXT = "text"
CREATED_AT = "created_at"
UPDATED_AT = "updated_at"
USER_FILM_RATING = "user_film_rating"

# Aggregation output keys
COUNT = "count"
AVG = "avg"
LIKE_CNT = "like_cnt"
DISLIKE_CNT = "dislike_cnt"

# Mongo operators
OP_MATCH = "$match"
OP_GROUP = "$group"
OP_SUM = "$sum"
OP_AVG = "$avg"
OP_COND = "$cond"
OP_EQ = "$eq"

# Sentry env vars
ENV_SENTRY_DSN = "SENTRY_DSN"
ENV_SENTRY_TRACES_SAMPLE_RATE = "SENTRY_TRACES_SAMPLE_RATE"
ENV_SENTRY_PROFILES_SAMPLE_RATE = "SENTRY_PROFILES_SAMPLE_RATE"
ENV_SENTRY_ENVIRONMENT = "SENTRY_ENVIRONMENT"
ENV_GIT_SHA = "GIT_SHA"
