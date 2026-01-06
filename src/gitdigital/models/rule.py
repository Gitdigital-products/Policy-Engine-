"""
Rule models and definitions
"""
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field, validator
from .fact import Fact


class ConditionType(Enum):
    """Types of conditions"""
    BOOLEAN = "boolean"
    COMPARISON = "comparison"
    LOGICAL = "logical"
    TEMPORAL = "temporal"
    SET_MEMBERSHIP = "set_membership"
    CUSTOM = "custom"


class Operator(Enum):
    """Logical and comparison operators"""
    # Comparison operators
    EQ = "eq"          # Equal
    NEQ = "neq"        # Not equal
    GT = "gt"          # Greater than
    GTE = "gte"        # Greater than or equal
    LT = "lt"          # Less than
    LTE = "lte"        # Less than or equal
    
    # Logical operators
    AND = "and"
    OR = "or"
    NOT = "not"
    XOR = "xor"
    
    # Set operators
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    
    # String operators
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    MATCHES = "matches"  # Regex match
    CONTAINS_TEXT = "contains_text"
    
    # Temporal operators
    BEFORE = "before"
    AFTER = "after"
    BETWEEN = "between"
    
    # Numerical operators
    BETWEEN_RANGE = "between_range"
    DIVISIBLE_BY = "divisible_by"
    
    # Custom operators
    CUSTOM = "custom"


class Condition(BaseModel):
    """Condition model"""
    
    type: ConditionType = ConditionType.BOOLEAN
    operator: Operator
    left_operand: Union[str, 'Condition', Any]
    right_operand: Optional[Union[str, 'Condition', Any]] = None
    
    # Metadata
    description: Optional[str] = None
    severity: str = "error"  # error, warning, info
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    
    # For temporal conditions
    date_format: Optional[str] = "%Y-%m-%d"
    
    class Config:
        use_enum_values = True


class ActionType(Enum):
    """Types of actions"""
    SET_FACT = "set_fact"
    CALCULATE = "calculate"
    VALIDATE = "validate"
    TRANSFORM = "transform"
    NOTIFY = "notify"
    LOG = "log"
    CUSTOM = "custom"


class Action(BaseModel):
    """Action model"""
    
    type: ActionType
    target: str  # Fact name or field to act upon
    value: Optional[Any] = None
    expression: Optional[str] = None  # For calculated values
    
    # For transformations
    transform_type: Optional[str] = None  # map, filter, reduce, etc.
    
    # Metadata
    description: Optional[str] = None
    priority: int = 0
    
    class Config:
        use_enum_values = True


class RuleType(Enum):
    """Rule types"""
    ELIGIBILITY = "eligibility"
    COMPLIANCE = "compliance"
    VALIDATION = "validation"
    CALCULATION = "calculation"
    DERIVATION = "derivation"
    TRANSFORMATION = "transformation"


class Rule(BaseModel):
    """Rule model"""
    
    id: str
    name: str
    description: Optional[str] = None
    
    type: RuleType = RuleType.ELIGIBILITY
    priority: int = 0
    required: bool = True
    enabled: bool = True
    
    condition: Condition
    actions: List[Action] = []
    
    # Dependencies
    depends_on: List[str] = []  # Other rule IDs this rule depends on
    prerequisites: List[str] = []  # Fact names required
    
    # Thresholds (for numeric rules)
    thresholds: Optional[Dict[str, float]] = None
    
    # Metadata
    tags: List[str] = []
    category: Optional[str] = None
    version: str = "1.0.0"
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    
    # Performance tracking
    execution_count: int = 0
    last_executed: Optional[datetime] = None
    average_execution_time: float = 0.0
    
    class Config:
        use_enum_values = True


class RuleSet(BaseModel):
    """Collection of related rules"""
    
    id: str
    name: str
    description: Optional[str] = None
    
    rules: List[Rule] = []
    
    # Configuration
    execution_order: str = "priority"  # priority, sequential, parallel
    stop_on_failure: bool = False
    max_execution_time: int = 5000  # ms
    
    # Threshold configuration
    global_thresholds: Optional[Dict[str, Dict[str, float]]] = None
    
    # Scoring
    weight: float = 1.0  # For weighted scoring
    pass_threshold: float = 1.0  # Minimum score to pass
    
    # Metadata
    tags: List[str] = []
    category: Optional[str] = None
    version: str = "1.0.0"
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    
    enabled: bool = True
    
    class Config:
        use_enum_values = True
        
    def add_rule(self, rule: Rule):
        """Add a rule to the rule set"""
        self.rules.append(rule)
        
    def remove_rule(self, rule_id: str):
        """Remove a rule by ID"""
        self.rules = [r for r in self.rules if r.id != rule_id]
        
    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """Get a rule by ID"""
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        return None
        
    def validate(self) -> List[str]:
        """Validate rule set consistency"""
        errors = []
        
        # Check for duplicate rule IDs
        rule_ids = [r.id for r in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            errors.append("Duplicate rule IDs found")
            
        # Check dependencies
        for rule in self.rules:
            for dep in rule.depends_on:
                if dep not in rule_ids:
                    errors.append(f"Rule {rule.id} depends on non-existent rule: {dep}")
                    
        return errors
