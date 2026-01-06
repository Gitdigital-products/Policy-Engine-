"""
Domain-Specific Language for policy rules
"""
from typing import Any, Dict, List, Optional, Union
from enum import Enum
import json
import yaml

from ..models.rule import Rule, RuleSet, Condition, Operator, ConditionType, RuleType
from ..models.policy import Policy


class PolicyDSL:
    """Domain-Specific Language for defining policies"""
    
    def __init__(self):
        self._current_policy: Optional[Policy] = None
        self._current_rule_set: Optional[RuleSet] = None
        
    def create_policy(self, id: str, name: str, version: str = "1.0.0") -> 'PolicyDSL':
        """Create a new policy"""
        from ..models.policy import Policy, PolicyVersion
        
        self._current_policy = Policy(
            id=id,
            name=name,
            version=version,
            rule_sets={}
        )
        return self
        
    def add_rule_set(self, id: str, name: str, **kwargs) -> 'PolicyDSL':
        """Add a rule set to current policy"""
        
        if not self._current_policy:
            raise ValueError("No current policy. Call create_policy() first.")
            
        rule_set = RuleSet(id=id, name=name, **kwargs)
        self._current_policy.rule_sets[id] = rule_set
        self._current_rule_set = rule_set
        
        return self
        
    def rule(self, id: str, name: str, **kwargs) -> 'RuleBuilder':
        """Add a rule to current rule set"""
        
        if not self._current_rule_set:
            raise ValueError("No current rule set. Call add_rule_set() first.")
            
        return RuleBuilder(self, id, name, **kwargs)
        
    def when(self, condition_def: Dict) -> 'ConditionBuilder':
        """Start building a condition"""
        return ConditionBuilder(condition_def)
        
    def threshold(self, field: str, **limits) -> Dict:
        """Define thresholds for a field"""
        
        thresholds = {}
        for limit_name, limit_value in limits.items():
            if limit_name in ["min", "max", "target", "warning_min", "warning_max"]:
                thresholds[limit_name] = limit_value
                
        return {field: thresholds}
        
    def get_policy(self) -> Policy:
        """Get the built policy"""
        
        if not self._current_policy:
            raise ValueError("No policy has been built")
            
        return self._current_policy
        
    def export_json(self, indent: int = 2) -> str:
        """Export policy as JSON"""
        
        policy = self.get_policy()
        return policy.model_dump_json(indent=indent)
        
    def export_yaml(self) -> str:
        """Export policy as YAML"""
        
        policy = self.get_policy()
        return yaml.dump(policy.model_dump(), default_flow_style=False)
        

class RuleBuilder:
    """Builder pattern for rules"""
    
    def __init__(self, dsl: PolicyDSL, id: str, name: str, **kwargs):
        self.dsl = dsl
        self.rule = Rule(id=id, name=name, **kwargs)
        
    def condition(self, condition: Condition) -> 'RuleBuilder':
        """Set rule condition"""
        self.rule.condition = condition
        return self
        
    def action(self, action_type: str, target: str, **kwargs) -> 'RuleBuilder':
        """Add an action to the rule"""
        from ..models.rule import Action, ActionType
        
        action = Action(
            type=ActionType(action_type),
            target=target,
            **kwargs
        )
        self.rule.actions.append(action)
        return self
        
    def required(self, is_required: bool = True) -> 'RuleBuilder':
        """Set if rule is required"""
        self.rule.required = is_required
        return self
        
    def priority(self, priority: int) -> 'RuleBuilder':
        """Set rule priority"""
        self.rule.priority = priority
        return self
        
    def depends_on(self, *rule_ids: str) -> 'RuleBuilder':
        """Set rule dependencies"""
        self.rule.depends_on.extend(rule_ids)
        return self
        
    def tag(self, *tags: str) -> 'RuleBuilder':
        """Add tags to rule"""
        self.rule.tags.extend(tags)
        return self
        
    def end(self) -> PolicyDSL:
        """Finish building rule and add to rule set"""
        
        self.dsl._current_rule_set.add_rule(self.rule)
        return self.dsl
        

class ConditionBuilder:
    """Builder pattern for conditions"""
    
    def __init__(self, condition_def: Dict):
        self.condition_def = condition_def
        
    def build(self) -> Condition:
        """Build condition from definition"""
        
        if "operator" not in self.condition_def:
            raise ValueError("Condition must have an operator")
            
        operator = Operator(self.condition_def["operator"])
        
        # Determine condition type based on operator
        if operator in [Operator.AND, Operator.OR, Operator.NOT, Operator.XOR]:
            condition_type = ConditionType.LOGICAL
        elif operator in [Operator.EQ, Operator.NEQ, Operator.GT, Operator.GTE,
                         Operator.LT, Operator.LTE]:
            condition_type = ConditionType.COMPARISON
        elif operator in [Operator.IN, Operator.NOT_IN, Operator.CONTAINS]:
            condition_type = ConditionType.SET_MEMBERSHIP
        elif operator in [Operator.BEFORE, Operator.AFTER, Operator.BETWEEN]:
            condition_type = ConditionType.TEMPORAL
        else:
            condition_type = ConditionType.CUSTOM
            
        return Condition(
            type=condition_type,
            operator=operator,
            left_operand=self.condition_def.get("left"),
            right_operand=self.condition_def.get("right"),
            description=self.condition_def.get("description"),
            severity=self.condition_def.get("severity", "error"),
            error_message=self.condition_def.get("error_message"),
            error_code=self.condition_def.get("error_code")
        )


# Helper functions for common patterns
class DSLHelpers:
    """Helper functions for common DSL patterns"""
    
    @staticmethod
    def age_at_least(age: int) -> Condition:
        """Age at least X years"""
        return Condition(
            type=ConditionType.COMPARISON,
            operator=Operator.GTE,
            left_operand="$age",
            right_operand=age,
            description=f"Age must be at least {age} years"
        )
        
    @staticmethod
    def income_between(min_income: float, max_income: float) -> Condition:
        """Income between min and max"""
        return Condition(
            type=ConditionType.COMPARISON,
            operator=Operator.BETWEEN_RANGE,
            left_operand="$annual_income",
            right_operand=[min_income, max_income],
            description=f"Income must be between {min_income} and {max_income}"
        )
        
    @staticmethod
    def residency_in(countries: List[str]) -> Condition:
        """Residency in specific countries"""
        return Condition(
            type=ConditionType.SET_MEMBERSHIP,
            operator=Operator.IN,
            left_operand="$country",
            right_operand=countries,
            description=f"Must be resident in: {', '.join(countries)}"
        )
        
    @staticmethod
    def date_after(field: str, date_str: str) -> Condition:
        """Date after specific date"""
        return Condition(
            type=ConditionType.TEMPORAL,
            operator=Operator.AFTER,
            left_operand=f"${field}",
            right_operand=date_str,
            description=f"{field} must be after {date_str}"
        )
        
    @staticmethod
    def all_of(*conditions: Dict) -> Condition:
        """All conditions must be true"""
        return Condition(
            type=ConditionType.LOGICAL,
            operator=Operator.AND,
            left_operand=[ConditionBuilder(c).build() for c in conditions],
            description="All conditions must be satisfied"
        )
        
    @staticmethod
    def any_of(*conditions: Dict) -> Condition:
        """Any condition must be true"""
        return Condition(
            type=ConditionType.LOGICAL,
            operator=Operator.OR,
            left_operand=[ConditionBuilder(c).build() for c in conditions],
            description="At least one condition must be satisfied"
        )


# Example usage
def create_eligibility_policy() -> Policy:
    """Example: Create an eligibility policy using DSL"""
    
    dsl = PolicyDSL()
    
    policy = (dsl
        .create_policy("student-loan-eligibility", "Student Loan Eligibility", "1.0.0")
        .add_rule_set("basic-eligibility", "Basic Eligibility Criteria")
        .rule("age-requirement", "Age Requirement")
            .condition(DSLHelpers.age_at_least(18))
            .required(True)
            .tag("age", "requirement")
            .end()
        .rule("citizenship", "Citizenship Requirement")
            .condition(DSLHelpers.residency_in(["US", "Canada", "UK", "Australia"]))
            .required(True)
            .tag("citizenship", "requirement")
            .end()
        .rule("income-limit", "Income Limit")
            .condition(DSLHelpers.income_between(0, 100000))
            .required(False)
            .tag("income", "limit")
            .end()
        .get_policy()
    )
    
    return policy
