"""
Schema Validators and Manifest Validation Utilities

This module provides validation for manifests, configurations, and
request/response payloads to ensure services are properly configured
for the AOL mesh.
"""
import os
import yaml
import logging
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Validation issue severity"""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """Represents a validation issue"""
    path: str
    message: str
    severity: ValidationSeverity
    value: Any = None
    suggestion: Optional[str] = None
    
    def __str__(self):
        prefix = {
            ValidationSeverity.ERROR: "❌",
            ValidationSeverity.WARNING: "⚠️",
            ValidationSeverity.INFO: "ℹ️"
        }[self.severity]
        return f"{prefix} [{self.path}] {self.message}"


@dataclass
class ValidationResult:
    """Result of validation"""
    valid: bool
    issues: List[ValidationIssue]
    
    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]
    
    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]
    
    def __str__(self):
        if self.valid:
            return f"✅ Valid ({len(self.warnings)} warnings)"
        return f"❌ Invalid ({len(self.errors)} errors, {len(self.warnings)} warnings)"


# ==================== Manifest Schema Definition ====================

MANIFEST_SCHEMA = {
    'kind': {
        'required': True,
        'type': str,
        'values': ['AOLAgent', 'AOLTool', 'AOLPlugin', 'AOLService']
    },
    'apiVersion': {
        'required': True,
        'type': str,
        'values': ['v1']
    },
    'metadata': {
        'required': True,
        'type': dict,
        'schema': {
            'name': {'required': True, 'type': str},
            'version': {'required': True, 'type': str, 'pattern': r'^\d+\.\d+\.\d+$'},
            'labels': {'required': False, 'type': dict}
        }
    },
    'spec': {
        'required': True,
        'type': dict,
        'schema': {
            'endpoints': {
                'required': True,
                'type': dict,
                'schema': {
                    'grpc': {'required': True, 'type': str},
                    'health': {'required': True, 'type': str},
                    'metrics': {'required': False, 'type': str},
                    'sidecar': {'required': False, 'type': str}
                }
            },
            'dependencies': {
                'required': False,
                'type': list,
                'item_schema': {
                    'service': {'required': True, 'type': str},
                    'optional': {'required': False, 'type': bool}
                }
            },
            'dataRequirements': {
                'required': False,
                'type': dict,
                'schema': {
                    'enabled': {'required': True, 'type': bool},
                    'collections': {'required': False, 'type': list},
                    'accessRequests': {'required': False, 'type': list}
                }
            },
            'configSchema': {
                'required': False,
                'type': list
            },
            'communication': {
                'required': False,
                'type': dict
            },
            'integrations': {
                'required': False,
                'type': dict
            },
            'resilience': {
                'required': False,
                'type': dict
            },
            'health': {
                'required': False,
                'type': dict
            },
            'monitoring': {
                'required': False,
                'type': dict
            },
            'resources': {
                'required': False,
                'type': dict
            }
        }
    }
}


# ==================== Manifest Validator ====================

class ManifestValidator:
    """
    Validates AOL service manifests against the schema.
    
    Ensures all required fields are present and have valid values,
    and provides helpful suggestions for fixing issues.
    """
    
    def __init__(self, strict_mode: bool = False):
        """
        Initialize validator.
        
        Args:
            strict_mode: If True, unknown fields are flagged as errors
        """
        self.strict_mode = strict_mode
        self.logger = logging.getLogger(__name__)
    
    def validate_file(self, manifest_path: str) -> ValidationResult:
        """
        Validate a manifest file.
        
        Args:
            manifest_path: Path to manifest.yaml
            
        Returns:
            ValidationResult with issues found
        """
        issues = []
        
        # Check file exists
        if not os.path.exists(manifest_path):
            issues.append(ValidationIssue(
                path="file",
                message=f"Manifest file not found: {manifest_path}",
                severity=ValidationSeverity.ERROR
            ))
            return ValidationResult(valid=False, issues=issues)
        
        # Load and parse YAML
        try:
            with open(manifest_path, 'r') as f:
                manifest = yaml.safe_load(f)
        except yaml.YAMLError as e:
            issues.append(ValidationIssue(
                path="file",
                message=f"Invalid YAML: {e}",
                severity=ValidationSeverity.ERROR
            ))
            return ValidationResult(valid=False, issues=issues)
        
        return self.validate(manifest)
    
    def validate(self, manifest: Dict[str, Any]) -> ValidationResult:
        """
        Validate a manifest dictionary.
        
        Args:
            manifest: Parsed manifest dictionary
            
        Returns:
            ValidationResult with issues found
        """
        issues = []
        
        # Validate against schema
        self._validate_schema(
            data=manifest,
            schema=MANIFEST_SCHEMA,
            path="",
            issues=issues
        )
        
        # Additional semantic validations
        self._validate_semantics(manifest, issues)
        
        # Determine if valid (no errors)
        has_errors = any(i.severity == ValidationSeverity.ERROR for i in issues)
        
        return ValidationResult(valid=not has_errors, issues=issues)
    
    def _validate_schema(
        self,
        data: Any,
        schema: Dict[str, Any],
        path: str,
        issues: List[ValidationIssue]
    ):
        """Recursively validate data against schema"""
        if not isinstance(data, dict):
            return
        
        # Check required fields
        for field, spec in schema.items():
            field_path = f"{path}.{field}" if path else field
            
            if spec.get('required') and field not in data:
                issues.append(ValidationIssue(
                    path=field_path,
                    message=f"Required field '{field}' is missing",
                    severity=ValidationSeverity.ERROR,
                    suggestion=f"Add '{field}' to the manifest"
                ))
                continue
            
            if field not in data:
                continue
            
            value = data[field]
            
            # Type check
            expected_type = spec.get('type')
            if expected_type and not isinstance(value, expected_type):
                issues.append(ValidationIssue(
                    path=field_path,
                    message=f"Expected {expected_type.__name__}, got {type(value).__name__}",
                    severity=ValidationSeverity.ERROR,
                    value=value
                ))
                continue
            
            # Value check
            allowed_values = spec.get('values')
            if allowed_values and value not in allowed_values:
                issues.append(ValidationIssue(
                    path=field_path,
                    message=f"Invalid value '{value}'. Allowed: {allowed_values}",
                    severity=ValidationSeverity.ERROR,
                    value=value,
                    suggestion=f"Use one of: {', '.join(allowed_values)}"
                ))
            
            # Pattern check
            import re
            pattern = spec.get('pattern')
            if pattern and isinstance(value, str):
                if not re.match(pattern, value):
                    issues.append(ValidationIssue(
                        path=field_path,
                        message=f"Value '{value}' does not match pattern {pattern}",
                        severity=ValidationSeverity.WARNING,
                        value=value
                    ))
            
            # Nested schema
            nested_schema = spec.get('schema')
            if nested_schema and isinstance(value, dict):
                self._validate_schema(value, nested_schema, field_path, issues)
            
            # List item schema
            item_schema = spec.get('item_schema')
            if item_schema and isinstance(value, list):
                for i, item in enumerate(value):
                    item_path = f"{field_path}[{i}]"
                    if isinstance(item, dict):
                        self._validate_schema(item, item_schema, item_path, issues)
        
        # Check for unknown fields in strict mode
        if self.strict_mode:
            known_fields = set(schema.keys())
            actual_fields = set(data.keys())
            unknown = actual_fields - known_fields
            
            for field in unknown:
                issues.append(ValidationIssue(
                    path=f"{path}.{field}" if path else field,
                    message=f"Unknown field '{field}'",
                    severity=ValidationSeverity.WARNING
                ))
    
    def _validate_semantics(
        self,
        manifest: Dict[str, Any],
        issues: List[ValidationIssue]
    ):
        """Perform semantic validations beyond schema"""
        spec = manifest.get('spec', {})
        
        # Validate port ranges
        endpoints = spec.get('endpoints', {})
        for name, port_str in endpoints.items():
            try:
                port = int(port_str)
                if port < 1 or port > 65535:
                    issues.append(ValidationIssue(
                        path=f"spec.endpoints.{name}",
                        message=f"Port {port} is out of valid range (1-65535)",
                        severity=ValidationSeverity.ERROR,
                        value=port
                    ))
            except (ValueError, TypeError):
                issues.append(ValidationIssue(
                    path=f"spec.endpoints.{name}",
                    message=f"Invalid port value: {port_str}",
                    severity=ValidationSeverity.ERROR,
                    value=port_str
                ))
        
        # Check data requirements consistency
        data_reqs = spec.get('dataRequirements', {})
        if data_reqs.get('enabled'):
            # Should have aol-core dependency
            deps = spec.get('dependencies', [])
            has_aol_core = any(d.get('service') == 'aol-core' for d in deps)
            
            if not has_aol_core:
                issues.append(ValidationIssue(
                    path="spec.dependencies",
                    message="Data requirements enabled but no aol-core dependency declared",
                    severity=ValidationSeverity.WARNING,
                    suggestion="Add aol-core to dependencies when using data storage"
                ))
        
        # Check for aol-core dependency (required)
        deps = spec.get('dependencies', [])
        has_aol_core = any(d.get('service') == 'aol-core' for d in deps)
        
        if not has_aol_core and deps:
            issues.append(ValidationIssue(
                path="spec.dependencies",
                message="aol-core dependency is recommended for AOL services",
                severity=ValidationSeverity.INFO,
                suggestion="Add aol-core as a required dependency"
            ))


# ==================== Config Validator ====================

class ConfigValidator:
    """
    Validates service configuration files.
    """
    
    def validate_file(self, config_path: str) -> ValidationResult:
        """Validate a config file"""
        issues = []
        
        if not os.path.exists(config_path):
            issues.append(ValidationIssue(
                path="file",
                message=f"Config file not found: {config_path}",
                severity=ValidationSeverity.ERROR
            ))
            return ValidationResult(valid=False, issues=issues)
        
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            issues.append(ValidationIssue(
                path="file",
                message=f"Invalid YAML: {e}",
                severity=ValidationSeverity.ERROR
            ))
            return ValidationResult(valid=False, issues=issues)
        
        return self.validate(config)
    
    def validate(self, config: Dict[str, Any]) -> ValidationResult:
        """Validate config dictionary"""
        issues = []
        
        # Check data client config
        data_client = config.get('dataClient', {})
        if data_client.get('enabled'):
            if not data_client.get('aolCoreEndpoint'):
                issues.append(ValidationIssue(
                    path="dataClient.aolCoreEndpoint",
                    message="Data client enabled but no aolCoreEndpoint specified",
                    severity=ValidationSeverity.WARNING
                ))
        
        # Check resilience config
        resilience = config.get('resilience', {})
        circuit_breaker = resilience.get('circuitBreaker', {})
        
        if circuit_breaker.get('enabled'):
            threshold = circuit_breaker.get('failureThreshold', 0)
            if threshold < 1:
                issues.append(ValidationIssue(
                    path="resilience.circuitBreaker.failureThreshold",
                    message="Failure threshold should be at least 1",
                    severity=ValidationSeverity.WARNING,
                    value=threshold
                ))
        
        has_errors = any(i.severity == ValidationSeverity.ERROR for i in issues)
        return ValidationResult(valid=not has_errors, issues=issues)


# ==================== Request/Response Validators ====================

class PayloadValidator:
    """
    Validates request and response payloads against JSON schemas.
    """
    
    def __init__(self, schemas: Dict[str, Dict] = None):
        """
        Initialize with schemas.
        
        Args:
            schemas: Dictionary of schema_name -> JSON schema
        """
        self.schemas = schemas or {}
    
    def register_schema(self, name: str, schema: Dict[str, Any]):
        """Register a JSON schema"""
        self.schemas[name] = schema
    
    def validate(
        self,
        data: Dict[str, Any],
        schema_name: str
    ) -> ValidationResult:
        """
        Validate data against a registered schema.
        
        Args:
            data: Data to validate
            schema_name: Name of schema to validate against
            
        Returns:
            ValidationResult
        """
        issues = []
        
        if schema_name not in self.schemas:
            issues.append(ValidationIssue(
                path="schema",
                message=f"Schema '{schema_name}' not found",
                severity=ValidationSeverity.ERROR
            ))
            return ValidationResult(valid=False, issues=issues)
        
        schema = self.schemas[schema_name]
        
        # Validate required fields
        required = schema.get('required', [])
        for field in required:
            if field not in data:
                issues.append(ValidationIssue(
                    path=field,
                    message=f"Required field '{field}' is missing",
                    severity=ValidationSeverity.ERROR
                ))
        
        # Validate properties
        properties = schema.get('properties', {})
        for field, prop_schema in properties.items():
            if field not in data:
                continue
            
            value = data[field]
            expected_type = prop_schema.get('type')
            
            # Type mapping
            type_map = {
                'string': str,
                'integer': int,
                'number': (int, float),
                'boolean': bool,
                'array': list,
                'object': dict
            }
            
            if expected_type and expected_type in type_map:
                if not isinstance(value, type_map[expected_type]):
                    issues.append(ValidationIssue(
                        path=field,
                        message=f"Expected {expected_type}, got {type(value).__name__}",
                        severity=ValidationSeverity.ERROR,
                        value=value
                    ))
        
        has_errors = any(i.severity == ValidationSeverity.ERROR for i in issues)
        return ValidationResult(valid=not has_errors, issues=issues)


# ==================== Utility Functions ====================

def validate_manifest(manifest_path: str, strict: bool = False) -> ValidationResult:
    """
    Convenience function to validate a manifest file.
    
    Args:
        manifest_path: Path to manifest.yaml
        strict: Enable strict mode
        
    Returns:
        ValidationResult
    """
    validator = ManifestValidator(strict_mode=strict)
    return validator.validate_file(manifest_path)


def validate_config(config_path: str) -> ValidationResult:
    """
    Convenience function to validate a config file.
    
    Args:
        config_path: Path to config.yaml
        
    Returns:
        ValidationResult
    """
    validator = ConfigValidator()
    return validator.validate_file(config_path)


def print_validation_result(result: ValidationResult):
    """Print validation result in a formatted way"""
    print(str(result))
    print()
    
    for issue in result.issues:
        print(str(issue))
        if issue.suggestion:
            print(f"   💡 Suggestion: {issue.suggestion}")

