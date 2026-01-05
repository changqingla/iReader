"""Business rules validation utilities."""

import re
from typing import Optional
from models.user import User
from models.organization import Organization
from config.quotas import get_user_quota, can_create_organization, can_join_organization
from exceptions import (
    InvalidUsername,
    OrganizationLimitExceeded,
    JoinOrganizationLimitExceeded,
    OrganizationMemberLimitExceeded,
    OrgCodeExpired,
    MembershipRequired,
    AdminPermissionRequired,
    InvalidVisibility,
)


# Username validation pattern: 字母、数字、中文、下划线
USERNAME_PATTERN = re.compile(r'^[\w\u4e00-\u9fa5]{3,50}$')


def validate_username(username: str) -> bool:
    """
    验证用户名格式。
    
    规则：
    - 长度：3-50字符
    - 字符：字母、数字、中文、下划线
    
    Args:
        username: 用户名
    
    Returns:
        是否有效
    
    Raises:
        InvalidUsername: 用户名格式无效
    """
    if not username or len(username) < 3 or len(username) > 50:
        raise InvalidUsername("用户名长度必须在3-50个字符之间")
    
    if not USERNAME_PATTERN.match(username):
        raise InvalidUsername("用户名只能包含字母、数字、中文和下划线")
    
    return True


def validate_org_creation(user: User, current_org_count: int) -> bool:
    """
    验证用户是否可以创建组织。
    
    检查：
    - 用户等级
    - 创建数量限制
    
    Args:
        user: 用户对象
        current_org_count: 当前已创建的组织数量
    
    Returns:
        是否可以创建
    
    Raises:
        OrganizationLimitExceeded: 组织数量超限
    """
    user_level = user.user_level or 'basic'
    quota = get_user_quota(user_level)
    max_create = quota['create_org']
    
    # 检查是否可以创建
    if not can_create_organization(user_level, current_org_count):
        if max_create == 0:
            raise OrganizationLimitExceeded(
                max_count=0,
                message="您当前的等级不支持创建组织，请升级会员"
            )
        else:
            raise OrganizationLimitExceeded(
                max_count=max_create,
                message=f"您已达到创建组织的上限（{max_create}个）"
            )
    
    return True


def validate_org_join(user: User, organization: Organization, current_joined_count: int, current_member_count: int) -> bool:
    """
    验证用户是否可以加入组织。
    
    检查：
    - 用户加入数量限制
    - 组织成员上限
    - 组织码有效期
    
    Args:
        user: 用户对象
        organization: 组织对象
        current_joined_count: 用户当前已加入的组织数量
        current_member_count: 组织当前成员数量
    
    Returns:
        是否可以加入
    
    Raises:
        JoinOrganizationLimitExceeded: 加入数量超限
        OrganizationMemberLimitExceeded: 组织成员超限
        OrgCodeExpired: 组织码过期
    """
    user_level = user.user_level or 'basic'
    
    # 检查用户加入数量限制
    if not can_join_organization(user_level, current_joined_count):
        quota = get_user_quota(user_level)
        max_join = quota['join_org']
        raise JoinOrganizationLimitExceeded(
            max_count=max_join,
            message=f"您已达到加入组织的上限（{max_join}个）"
        )
    
    # 检查组织成员上限
    if not organization.can_add_member(current_member_count):
        raise OrganizationMemberLimitExceeded(
            max_members=organization.max_members,
            message=f"组织成员已达上限（{organization.max_members}人）"
        )
    
    # 检查组织码有效期
    if organization.is_code_expired():
        raise OrgCodeExpired(message="组织邀请码已过期")
    
    return True


def validate_kb_visibility(user: User, visibility: str, org_ids: Optional[list] = None) -> bool:
    """
    验证知识库可见性设置。
    
    规则：
    - public: 仅管理员可以设置
    - organization: 需要至少加入一个组织（且提供org_ids）
    - private: 所有用户都可以
    
    Args:
        user: 用户对象
        visibility: 可见性 (private/organization/public)
        org_ids: 要共享的组织ID列表（当visibility=organization时必需）
    
    Returns:
        是否有效
    
    Raises:
        AdminPermissionRequired: 需要管理员权限
        InvalidVisibility: 无效的可见性设置
    """
    if visibility not in ['private', 'organization', 'public']:
        raise InvalidVisibility(f"可见性必须是 private、organization 或 public")
    
    # public 仅管理员可设置
    if visibility == 'public':
        if not user.is_admin:
            raise AdminPermissionRequired("只有管理员可以将知识库设置为全局公开")
    
    # organization 需要提供组织ID列表
    if visibility == 'organization':
        if not org_ids or len(org_ids) == 0:
            raise InvalidVisibility("共享到组织时必须指定至少一个组织")
    
    return True


def validate_org_name(name: str) -> bool:
    """
    验证组织名称。
    
    规则：
    - 长度：3-100字符
    - 非空
    
    Args:
        name: 组织名称
    
    Returns:
        是否有效
    
    Raises:
        ValidationError: 验证错误
    """
    from exceptions import ValidationError
    
    if not name or not name.strip():
        raise ValidationError("name", "组织名称不能为空")
    
    if len(name) < 3:
        raise ValidationError("name", "组织名称至少3个字符")
    
    if len(name) > 100:
        raise ValidationError("name", "组织名称不能超过100个字符")
    
    return True


def validate_file_size(file_size_bytes: int, max_size_mb: int = 10) -> bool:
    """
    验证文件大小。
    
    Args:
        file_size_bytes: 文件大小（字节）
        max_size_mb: 最大大小（MB）
    
    Returns:
        是否有效
    
    Raises:
        FileSizeExceeded: 文件大小超限
    """
    from exceptions import FileSizeExceeded
    
    max_size_bytes = max_size_mb * 1024 * 1024
    
    if file_size_bytes > max_size_bytes:
        raise FileSizeExceeded(max_size_mb=max_size_mb)
    
    return True


def validate_image_type(content_type: str) -> bool:
    """
    验证图片文件类型。
    
    Args:
        content_type: 文件MIME类型
    
    Returns:
        是否有效
    
    Raises:
        InvalidFileType: 文件类型无效
    """
    from exceptions import InvalidFileType
    
    allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/gif']
    
    if content_type not in allowed_types:
        raise InvalidFileType(
            allowed_types=['jpg', 'png', 'webp', 'gif'],
            message="头像仅支持 JPG、PNG、WEBP、GIF 格式"
        )
    
    return True


def check_membership_required(user: User, feature_name: str = "此功能") -> bool:
    """
    检查用户是否需要会员权限。
    
    Args:
        user: 用户对象
        feature_name: 功能名称
    
    Returns:
        是否有会员权限
    
    Raises:
        MembershipRequired: 需要会员权限
    """
    if not user.is_member():
        raise MembershipRequired(f"{feature_name}仅对会员开放")
    
    return True


def check_admin_required(user: User) -> bool:
    """
    检查用户是否有管理员权限。
    
    Args:
        user: 用户对象
    
    Returns:
        是否有管理员权限
    
    Raises:
        AdminPermissionRequired: 需要管理员权限
    """
    if not user.is_admin:
        raise AdminPermissionRequired()
    
    return True

