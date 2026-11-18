from enum import Enum
class Role(str,Enum):
    admin='admin'; analyst='analyst'; viewer='viewer'
class RunState(str,Enum):
    queued='queued'; running='running'; completed='completed'; failed='failed'
class PrivacyStudyState(str,Enum):
    queued='queued'; running='running'; completed='completed'; failed='failed'; cancelled='cancelled'
class LedgerState(str,Enum):
    held='held'; confirmed='confirmed'; refunded='refunded'
class ReviewState(str,Enum):
    draft='draft'; approved='approved'
