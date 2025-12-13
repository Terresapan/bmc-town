"""
Business security and file isolation module.

This module provides enhanced security features for ensuring proper isolation
between different businesses in the file processing workflow.
"""

import uuid
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
from bmc.domain.business_user import BusinessUser
from bmc.domain.business_user_factory import (
    BusinessUserFactory,
    DatabaseConnectionError,
    DatabaseOperationError,
)
import logging

logger = logging.getLogger(__name__)


class ValidationResult(Enum):
    """Enumeration for validation results."""
    VALID = "valid"
    INVALID_TOKEN = "invalid_token"
    TOKEN_MISSING = "token_missing"
    VALIDATION_FAILED = "validation_failed"
    DATABASE_ERROR = "database_error"


@dataclass
class BusinessContext:
    """Represents validated business context for file processing."""
    token: str
    business_name: str
    owner_name: str
    sector: str
    validated_at: float
    validation_id: str
    
    def to_metadata(self) -> Dict[str, Any]:
        """Convert business context to metadata dictionary."""
        return {
            "business_token": self.token,
            "business_name": self.business_name,
            "owner_name": self.owner_name,
            "sector": self.sector,
            "validated_at": self.validated_at,
            "validation_id": self.validation_id,
        }


@dataclass
class FileProcessingAudit:
    """Audit trail for file processing operations."""
    operation_id: str
    business_context: BusinessContext
    file_type: str
    file_name: Optional[str]
    file_size: int
    timestamp: float
    success: bool
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert audit record to dictionary."""
        return {
            "operation_id": self.operation_id,
            "business_context": self.business_context.to_metadata(),
            "file_type": self.file_type,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "timestamp": self.timestamp,
            "success": self.success,
            "error_message": self.error_message,
        }


class BusinessValidator:
    """Validates business context and provides security features."""
    
    def __init__(self):
        self.user_factory = BusinessUserFactory()
        self._audit_logs: List[FileProcessingAudit] = []
    
    async def validate_business_context(
        self, 
        user_token: Optional[str],
        operation_context: str = "file_processing"
    ) -> tuple[ValidationResult, Optional[BusinessContext]]:
        """
        Validate business context for file processing operations.
        
        Args:
            user_token: The business user token to validate
            operation_context: Context of the operation for logging
            
        Returns:
            Tuple of (ValidationResult, BusinessContext)
        """
        if not user_token:
            logger.warning(f"No user token provided for {operation_context}")
            return ValidationResult.TOKEN_MISSING, None
        
        try:
            # Get user by token
            user = await self.user_factory.get_user_by_token(user_token)
            
            if not user:
                logger.warning(f"Invalid token provided for {operation_context}: {user_token}")
                return ValidationResult.INVALID_TOKEN, None
            
            # Create validated business context
            business_context = BusinessContext(
                token=user_token,
                business_name=user.business_name,
                owner_name=user.owner_name,
                sector=user.sector,
                validated_at=time.time(),
                validation_id=str(uuid.uuid4())
            )
            
            logger.info(f"Validated business context for {operation_context}: "
                       f"{user.business_name} (token: {user_token})")
            
            return ValidationResult.VALID, business_context
            
        except DatabaseConnectionError as e:
            logger.error(f"Database connection error during validation: {e}")
            return ValidationResult.DATABASE_ERROR, None
        except DatabaseOperationError as e:
            logger.error(f"Database operation error during validation: {e}")
            return ValidationResult.VALIDATION_FAILED, None
        except Exception as e:
            logger.error(f"Unexpected error during business validation: {e}")
            return ValidationResult.VALIDATION_FAILED, None
    
    async def validate_file_upload(
        self,
        user_token: Optional[str],
        file_data: Optional[str],
        file_name: Optional[str],
        operation_context: str = "file_upload"
    ) -> tuple[ValidationResult, Optional[BusinessContext]]:
        """
        Validate file upload with business context.
        
        Args:
            user_token: The business user token
            file_data: Base64 encoded file data
            file_name: Name of the file
            operation_context: Context for logging
            
        Returns:
            Tuple of (ValidationResult, BusinessContext)
        """
        # First validate business context
        validation_result, business_context = await self.validate_business_context(
            user_token, operation_context
        )
        
        if validation_result != ValidationResult.VALID:
            return validation_result, None
        
        # Additional file upload validations
        if not file_data:
            logger.warning(f"No file data provided for {operation_context}")
            return ValidationResult.VALIDATION_FAILED, None
        
        if not file_name:
            logger.warning(f"No file name provided for {operation_context}")
            return ValidationResult.VALIDATION_FAILED, None
        
        # Sanitize file name
        sanitized_name = self._sanitize_filename(file_name)
        if sanitized_name != file_name:
            logger.warning(f"File name sanitized: {file_name} -> {sanitized_name}")
            file_name = sanitized_name
        
        return ValidationResult.VALID, business_context
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename to prevent security issues.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        # Remove potentially dangerous characters
        dangerous_chars = ['/', '\\', '..', '<', '>', ':', '"', '|', '?', '*']
        sanitized = filename
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '_')
        
        # Limit length
        if len(sanitized) > 255:
            name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
            max_name_length = 255 - len(ext) - 1 if ext else 255
            sanitized = name[:max_name_length] + ('.' + ext if ext else '')
        
        return sanitized
    
    def log_file_processing_audit(
        self,
        business_context: BusinessContext,
        file_type: str,
        file_name: Optional[str],
        file_size: int,
        success: bool,
        error_message: Optional[str] = None
    ) -> str:
        """
        Log file processing operation for audit trail.
        
        Args:
            business_context: Validated business context
            file_type: Type of file (pdf, image, etc.)
            file_name: Name of the file
            file_size: Size of the file in bytes
            success: Whether the operation was successful
            error_message: Optional error message
            
        Returns:
            Operation ID for tracking
        """
        operation_id = str(uuid.uuid4())
        
        audit_record = FileProcessingAudit(
            operation_id=operation_id,
            business_context=business_context,
            file_type=file_type,
            file_name=file_name,
            file_size=file_size,
            timestamp=time.time(),
            success=success,
            error_message=error_message
        )
        
        self._audit_logs.append(audit_record)
        
        # Keep only last 1000 audit logs to prevent memory issues
        if len(self._audit_logs) > 1000:
            self._audit_logs = self._audit_logs[-1000:]
        
        logger.info(f"File processing audit logged: {operation_id} - "
                   f"{business_context.business_name} - {file_type} - "
                   f"Success: {success}")
        
        return operation_id
    
    def get_audit_logs_for_business(self, business_token: str) -> List[Dict[str, Any]]:
        """
        Get audit logs for a specific business.
        
        Args:
            business_token: Business token to filter logs
            
        Returns:
            List of audit log dictionaries
        """
        business_logs = [
            log.to_dict() for log in self._audit_logs 
            if log.business_context.token == business_token
        ]
        return business_logs
    
    def get_audit_summary(self) -> Dict[str, Any]:
        """
        Get summary of all audit logs.
        
        Returns:
            Dictionary with audit summary
        """
        total_operations = len(self._audit_logs)
        successful_operations = sum(1 for log in self._audit_logs if log.success)
        failed_operations = total_operations - successful_operations
        
        # Group by business
        business_stats = {}
        for log in self._audit_logs:
            business_name = log.business_context.business_name
            if business_name not in business_stats:
                business_stats[business_name] = {
                    "total_operations": 0,
                    "successful_operations": 0,
                    "failed_operations": 0,
                    "file_types": set()
                }
            
            stats = business_stats[business_name]
            stats["total_operations"] += 1
            stats["file_types"].add(log.file_type)
            if log.success:
                stats["successful_operations"] += 1
            else:
                stats["failed_operations"] += 1
        
        # Convert sets to lists for JSON serialization
        for business_name in business_stats:
            business_stats[business_name]["file_types"] = list(
                business_stats[business_name]["file_types"]
            )
        
        return {
            "total_operations": total_operations,
            "successful_operations": successful_operations,
            "failed_operations": failed_operations,
            "success_rate": successful_operations / total_operations if total_operations > 0 else 0,
            "business_stats": business_stats,
            "timestamp": time.time()
        }


# Global validator instance
business_validator = BusinessValidator()