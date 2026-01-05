"""Pydantic schemas for request/response validation."""
from pydantic import BaseModel, EmailStr, Field, constr
from typing import Optional, List
from datetime import datetime
from enum import Enum


# === Common ===
class ErrorCode(str, Enum):
    """Standard error codes."""
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: dict = Field(..., example={
        "code": "VALIDATION_ERROR",
        "message": "参数不合法",
        "details": {}
    })


class PaginationMeta(BaseModel):
    """Pagination metadata."""
    total: int
    page: int
    pageSize: int


# === Auth ===
class LoginRequest(BaseModel):
    """Login request body."""
    email: EmailStr
    password: constr(min_length=6)


class RegisterRequest(BaseModel):
    """Register request body."""
    email: EmailStr
    password: constr(min_length=6)
    name: constr(min_length=1, max_length=50)
    code: constr(min_length=6, max_length=6)


class ResetPasswordRequest(BaseModel):
    """Reset password request body."""
    email: EmailStr
    password: constr(min_length=6)
    code: constr(min_length=6, max_length=6)


class SendVerificationCodeRequest(BaseModel):
    """Send verification code request body."""
    email: EmailStr
    type: constr(pattern="^(register|reset)$") = "register"


class AuthResponse(BaseModel):
    """Auth response with token."""
    token: str
    user: dict


class UserProfile(BaseModel):
    """User profile."""
    id: str
    name: str
    email: str
    avatar: Optional[str] = None
    user_level: Optional[str] = None
    is_member: Optional[bool] = None
    is_advanced_member: Optional[bool] = None
    is_admin: Optional[bool] = None
    member_expires_at: Optional[str] = None
    organizations: Optional[List[dict]] = None


class CheckUsernameRequest(BaseModel):
    """Check username availability request."""
    username: constr(min_length=2, max_length=20)


class CheckUsernameResponse(BaseModel):
    """Check username availability response."""
    available: bool


class UpdateProfileRequest(BaseModel):
    """Update profile request."""
    name: Optional[constr(min_length=2, max_length=20)] = None
    avatar: Optional[str] = None


class UploadAvatarResponse(BaseModel):
    """Upload avatar response."""
    avatar_url: str


class ActivateMembershipRequest(BaseModel):
    """Activate membership request."""
    code: constr(min_length=1, max_length=50)


# === Favorites ===
class FavoriteType(str, Enum):
    """Favorite item type."""
    PAPER = "paper"
    KNOWLEDGE = "knowledge"


class CreateFavoriteRequest(BaseModel):
    """Create favorite request."""
    type: FavoriteType
    targetId: str
    tags: List[str] = []


class FavoriteItem(BaseModel):
    """Favorite item response."""
    id: str
    type: FavoriteType
    title: str
    description: Optional[str] = None
    author: Optional[str] = None
    date: str
    source: Optional[str] = None
    tags: List[str] = []


class FavoritesResponse(BaseModel):
    """Favorites list response."""
    total: int
    page: int
    pageSize: int
    items: List[FavoriteItem]


# === Notes ===
class CreateNoteRequest(BaseModel):
    """Create note request."""
    title: str
    content: Optional[str] = ""
    folder: Optional[str] = None
    tags: List[str] = []


class UpdateNoteRequest(BaseModel):
    """Update note request."""
    title: Optional[str] = None
    content: Optional[str] = None
    folder: Optional[str] = None
    folderId: Optional[str] = None  # 支持前端使用 folderId
    tags: Optional[List[str]] = None


class NoteItem(BaseModel):
    """Note item response."""
    id: str
    title: str
    content: str
    folder: str
    tags: List[str]
    updatedAt: datetime
    createdAt: datetime


class NoteFolderItem(BaseModel):
    """Note folder item."""
    id: str
    name: str
    count: int


# === Knowledge Base (TODO) ===
class CreateKnowledgeBaseRequest(BaseModel):
    """Create knowledge base request."""
    name: str
    description: Optional[str] = ""
    tags: List[str] = []


# === Hub (TODO) ===
class HubItem(BaseModel):
    """Hub item for knowledge plaza."""
    id: str
    title: str
    desc: str
    icon: str
    subs: int
    contents: int


# === Organization ===
class CreateOrganizationRequest(BaseModel):
    """Create organization request."""
    name: constr(min_length=3, max_length=100)
    description: Optional[str] = None
    avatar: Optional[str] = None


class UpdateOrganizationRequest(BaseModel):
    """Update organization request."""
    name: Optional[constr(min_length=3, max_length=100)] = None
    description: Optional[str] = None
    avatar: Optional[str] = None


class JoinOrganizationRequest(BaseModel):
    """Join organization request."""
    org_code: constr(min_length=1, max_length=20)


class OrganizationResponse(BaseModel):
    """Organization response."""
    id: str
    name: str
    description: Optional[str] = None
    avatar: Optional[str] = None
    org_code: str
    code_expires_at: Optional[str] = None
    owner_id: str
    owner_name: Optional[str] = None
    max_members: int
    member_count: int
    created_at: str
    updated_at: str
    role: Optional[str] = None
    is_owner: Optional[bool] = None


class OrganizationListResponse(BaseModel):
    """Organization list response with created and joined groups."""
    created: List[OrganizationResponse]
    joined: List[OrganizationResponse]


class OrganizationMemberResponse(BaseModel):
    """Organization member response."""
    id: str
    user_id: str
    user_name: str
    user_email: str
    user_avatar: Optional[str] = None
    role: str
    joined_at: str


class OrganizationDetailResponse(OrganizationResponse):
    """Organization detail response including members."""
    members: List[OrganizationMemberResponse]


class RegenerateCodeResponse(BaseModel):
    """Regenerate organization code response."""
    org_code: str


class SetCodeExpiryRequest(BaseModel):
    """Set organization code expiry request."""
    expires_at: Optional[datetime] = None


# === Activation Code (Admin) ===
class GenerateActivationCodeRequest(BaseModel):
    """Generate activation code request."""
    type: constr(pattern="^(member|premium)$")  # member or premium
    duration_days: Optional[int] = None  # None for permanent
    max_usage: int = Field(default=1, ge=1, le=1000)
    code_expires_in_days: Optional[int] = None  # Code expiry


class ActivationCodeResponse(BaseModel):
    """Activation code response."""
    id: str
    code: str
    type: str
    duration_days: Optional[int] = None
    max_usage: int
    used_count: int
    created_by: Optional[str] = None
    created_at: str
    expires_at: Optional[str] = None
    is_active: bool
    is_valid: bool


class ValidateCodeResponse(BaseModel):
    """Validate activation code response."""
    valid: bool
    type: Optional[str] = None
    duration_days: Optional[int] = None
    remaining_usage: Optional[int] = None
    reason: Optional[str] = None


# === Knowledge Base Visibility ===
class UpdateKBVisibilityRequest(BaseModel):
    """Update knowledge base visibility request."""
    visibility: constr(pattern="^(private|organization|public)$")
    shared_to_orgs: Optional[List[str]] = None  # Organization IDs when visibility is 'organization'


class ShareToOrgsRequest(BaseModel):
    """Share knowledge base to organizations request."""
    org_ids: List[str]
