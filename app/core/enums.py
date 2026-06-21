"""All shared enums in one place to avoid duplication/inconsistency."""
import enum


class UserState(str, enum.Enum):
    NEW = "NEW"
    PROFILE_CREATION = "PROFILE_CREATION"
    VERIFICATION = "VERIFICATION"
    ACTIVE_SEARCH = "ACTIVE_SEARCH"
    ACTIVE_CHAT = "ACTIVE_CHAT"
    BUFFER_MATCH = "BUFFER_MATCH"
    PAUSE = "PAUSE"
    INACTIVE = "INACTIVE"
    LIMITED = "LIMITED"
    BANNED_BY_SYSTEM = "BANNED_BY_SYSTEM"


class Gender(str, enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class SeekingGender(str, enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    ANY = "ANY"


class Goal(str, enum.Enum):
    COMMUNICATION = "COMMUNICATION"      # общение
    DATE = "DATE"                        # свидание
    INTIMATE = "INTIMATE"                # секс
    REGULAR = "REGULAR"                  # регулярное
    FRIENDSHIP = "FRIENDSHIP"             # дружба
    INTERESTS = "INTERESTS"               # интересы
    EVENTS = "EVENTS"                     # события


class MatchStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    BUFFER = "BUFFER"
    CLOSED = "CLOSED"


class ChatStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    BUFFER = "BUFFER"
    CLOSED = "CLOSED"


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class PaymentProviderName(str, enum.Enum):
    TELEGRAM_STARS = "TELEGRAM_STARS"
    STRIPE = "STRIPE"
    LIQPAY = "LIQPAY"
    FONDY = "FONDY"
    WAYFORPAY = "WAYFORPAY"


class PaidFeature(str, enum.Enum):
    EXTEND_CHAT = "EXTEND_CHAT"
    EXTRA_LIKES = "EXTRA_LIKES"
    EARLY_ACCESS = "EARLY_ACCESS"
    EXTENDED_RADIUS = "EXTENDED_RADIUS"
    CREATE_COMMUNITY_EVENT = "CREATE_COMMUNITY_EVENT"
    PAID_CONTEST_ENTRY = "PAID_CONTEST_ENTRY"
    INVISIBLE_PAUSE = "INVISIBLE_PAUSE"
    EXTENDED_STATS = "EXTENDED_STATS"
    DONATION = "DONATION"


class ReferralStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVATED = "ACTIVATED"
    REJECTED = "REJECTED"


class VerificationStatus(str, enum.Enum):
    NONE = "NONE"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class VerificationMethod(str, enum.Enum):
    SELFIE_GESTURE = "SELFIE_GESTURE"
    SHORT_VIDEO = "SHORT_VIDEO"


class ModerationSignalType(str, enum.Enum):
    DANGER_BUTTON = "DANGER_BUTTON"          # scam/threats/coercion/money/violence
    RISK_KEYWORDS = "RISK_KEYWORDS"          # auto-detected risky dialog
    REPEAT_PHOTO = "REPEAT_PHOTO"
    SPAM_PATTERN = "SPAM_PATTERN"


class ModerationStatus(str, enum.Enum):
    OPEN = "OPEN"
    REVIEWING = "REVIEWING"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class ContestType(str, enum.Enum):
    BEST_PHOTO = "BEST_PHOTO"
    BEST_DIALOG = "BEST_DIALOG"
    JAZZ_EVENING = "JAZZ_EVENING"
    DISTRICT_WALK = "DISTRICT_WALK"
    SPEED_MATCH = "SPEED_MATCH"
    VOICE_EVENING = "VOICE_EVENING"
    CUSTOM = "CUSTOM"


class InterestCategory(str, enum.Enum):
    MUSIC = "MUSIC"
    SPORT = "SPORT"
    WALKS = "WALKS"
    CINEMA = "CINEMA"
    GAMES = "GAMES"
    DANCING = "DANCING"
    FOOD = "FOOD"
    BUSINESS = "BUSINESS"
    IT = "IT"
    ART = "ART"
    NIGHT_CITY = "NIGHT_CITY"
    TRAVEL = "TRAVEL"
    ADULT_18 = "ADULT_18"
    QUICK_MEETUPS = "QUICK_MEETUPS"
    VOICE_CHAT = "VOICE_CHAT"
