"""
Rule evaluator
"""
import re
import operator
from typing import Any, Dict, List, Optional, Tuple, Callable
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
import logging

from ..models.rule import Rule, RuleSet, Condition, Operator, ConditionType
from ..models.fact import Fact
from ..models.decision import DecisionResult, RuleEvaluation
from ..utils.logger import get_logger

logger = get_logger(__name__)


class RuleEvaluator:
    """Evaluates rules against facts"""
    
    def __init__(self, mode: str = "strict"):
        self.mode = mode
        self.custom_operators: Dict[str, Callable] = {}
        
        # Register built-in operators
        self._register_builtin_operators()
        
    def _register_builtin_operators(self):
        """Register built-in operators"""
        
        # Comparison operators
        self.custom_operators["eq"] = lambda a, b: a == b
        self.custom_operators["neq"] = lambda a, b: a != b
        self.custom_operators["gt"] = lambda a, b: a > b
        self.custom_operators["gte"] = lambda a, b: a >= b
        self.custom_operators["lt"] = lambda a, b: a < b
        self.custom_operators["lte"] = lambda a, b: a <= b
        
        # String operators
        self.custom_operators["starts_with"] = lambda a, b: str(a).startswith(str(b))
        self.custom_operators["ends_with"] = lambda a, b: str(a).endswith(str(b))
        self.custom_operators["contains_text"] = lambda a, b: str(b) in str(a)
        self.custom_operators["matches"] = lambda a, b: bool(re.match(str(b), str(a)))
        
        # Set operators
        self.custom_operators["in"] = lambda a, b: a in b if isinstance(b, (list, tuple, set)) else False
        self.custom_operators["not_in"] = lambda a, b: a not in b if isinstance(b, (list, tuple, set)) else True
        self.custom_operators["contains"] = lambda a, b: b in a if isinstance(a, (list, tuple, set)) else False
        
        # Temporal operators
        self.custom_operators["before"] = lambda a, b: self._parse_date(a) < self._parse_date(b)
        self.custom_operators["after"] = lambda a, b: self._parse_date(a) > self._parse_date(b)
        self.custom_operators["between"] = lambda a, b, c: self._parse_date(b) <= self._parse_date(a) <= self._parse_date(c)
        
        # Numerical operators
        self.custom_operators["between_range"] = lambda a, b, c: b <= a <= c
        self.custom_operators["divisible_by"] = lambda a, b: a % b == 0 if isinstance(a, int) and isinstance(b, int) else False
        
    def _parse_date(self, value: Any, fmt: str = "%Y-%m-%d") -> datetime:
        """Parse date from various formats"""
        if isinstance(value, (datetime, date)):
            return value if isinstance(value, datetime) else datetime.combine(value, datetime.min.time())
        elif isinstance(value, str):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                # Try ISO format
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
        else:
            raise ValueError(f"Cannot parse date from: {value}")
            
    def evaluate_rule_set(
        self,
        rule_set: RuleSet,
        facts: Dict[str, Fact],
        context: Optional[Dict[str, Any]] = None
    ) -> DecisionResult:
        """Evaluate a complete rule set"""
        
        context = context or {}
        results = []
        passed_count = 0
        failed_count = 0
        
        # Sort rules by priority
        rules = sorted(rule_set.rules, key=lambda r: r.priority, reverse=True)
        
        for rule in rules:
            if not rule.enabled:
                continue
                
            try:
                rule_evaluation = self.evaluate_rule(rule, facts, context)
                results.append(rule_evaluation)
                
                if rule_evaluation.passed:
                    passed_count += 1
                else:
                    failed_count += 1
                    
                    # Stop on failure if configured
                    if rule_set.stop_on_failure and rule.required:
                        break
                        
            except Exception as e:
                logger.error(f"Error evaluating rule {rule.id}: {e}")
                
                if self.mode == "strict":
                    raise
                    
                # Create failed evaluation
                rule_evaluation = RuleEvaluation(
                    rule_id=rule.id,
                    passed=False,
                    error=str(e),
                    error_type=type(e).__name__,
                    facts_used=[],
                    result=None
                )
                results.append(rule_evaluation)
                failed_count += 1
                
        # Calculate score
        total_rules = len(rules)
        score = passed_count / total_rules if total_rules > 0 else 0
        
        # Determine if rule set passed
        passed = score >= rule_set.pass_threshold
        
        return DecisionResult(
            rule_set_id=rule_set.id,
            rule_set_name=rule_set.name,
            results=results,
            passed=passed,
            score=score,
            passed_rules_count=passed_count,
            failed_rules_count=failed_count,
            total_rules_count=total_rules,
            metadata={
                "execution_order": rule_set.execution_order,
                "weight": rule_set.weight,
                "threshold": rule_set.pass_threshold
            }
        )
        
    def evaluate_rule(
        self,
        rule: Rule,
        facts: Dict[str, Fact],
        context: Optional[Dict[str, Any]] = None
    ) -> RuleEvaluation:
        """Evaluate a single rule"""
        
        context = context or {}
        start_time = datetime.utcnow()
        
        try:
            # Check prerequisites
            missing_prereqs = []
            for prereq in rule.prerequisites:
                if prereq not in facts:
                    missing_prereqs.append(prereq)
                    
            if missing_prereqs:
                return RuleEvaluation(
                    rule_id=rule.id,
                    passed=False,
                    error=f"Missing prerequisites: {missing_prereqs}",
                    error_type="PrerequisiteError",
                    facts_used=[],
                    result=None
                )
                
            # Evaluate condition
            condition_result, facts_used = self.evaluate_condition(
                rule.condition, facts, context
            )
            
            # Execute actions if condition passed
            actions_result = None
            if condition_result and rule.actions:
                actions_result = self.execute_actions(rule.actions, facts, context)
                
            # Update rule execution stats
            rule.execution_count += 1
            rule.last_executed = datetime.utcnow()
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            rule.average_execution_time = (
                (rule.average_execution_time * (rule.execution_count - 1) + execution_time)
                / rule.execution_count
            )
            
            return RuleEvaluation(
                rule_id=rule.id,
                passed=condition_result,
                error=None,
                error_type=None,
                facts_used=facts_used,
                result=actions_result,
                execution_time_ms=execution_time,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error in rule {rule.id}: {e}")
            
            return RuleEvaluation(
                rule_id=rule.id,
                passed=False,
                error=str(e),
                error_type=type(e).__name__,
                facts_used=[],
                result=None,
                execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                timestamp=datetime.utcnow()
            )
            
    def evaluate_condition(
        self,
        condition: Condition,
        facts: Dict[str, Fact],
        context: Dict[str, Any],
        facts_used: Optional[List[str]] = None
    ) -> Tuple[bool, List[str]]:
        """Evaluate a condition"""
        
        if facts_used is None:
            facts_used = []
            
        try:
            # Get left operand value
            left_value, left_facts = self._get_operand_value(
                condition.left_operand, facts, context
            )
            facts_used.extend(left_facts)
            
            # Handle unary operators
            if condition.operator in ["not"]:
                result = not bool(left_value)
                return result, facts_used
                
            # Get right operand value for binary operators
            if condition.right_operand is not None:
                right_value, right_facts = self._get_operand_value(
                    condition.right_operand, facts, context
                )
                facts_used.extend(right_facts)
                
                # Handle different operator types
                if condition.operator in self.custom_operators:
                    operator_func = self.custom_operators[condition.operator.value]
                    
                    # Handle ternary operators
                    if condition.operator in ["between", "between_range"]:
                        # For between operators, right operand should be a tuple/list
                        if isinstance(condition.right_operand, (list, tuple)) and len(condition.right_operand) == 2:
                            right_value2, right_facts2 = self._get_operand_value(
                                condition.right_operand[1], facts, context
                            )
                            facts_used.extend(right_facts2)
                            result = operator_func(left_value, right_value, right_value2)
                        else:
                            raise ValueError(f"Between operator requires two values, got: {condition.right_operand}")
                    else:
                        result = operator_func(left_value, right_value)
                else:
                    # Use Python's operator module
                    op_map = {
                        "and": operator.and_,
                        "or": operator.or_,
                        "eq": operator.eq,
                        "neq": operator.ne,
                        "gt": operator.gt,
                        "gte": operator.ge,
                        "lt": operator.lt,
                        "lte": operator.le,
                    }
                    
                    if condition.operator.value in op_map:
                        result = op_map[condition.operator.value](left_value, right_value)
                    else:
                        raise ValueError(f"Unknown operator: {condition.operator}")
            else:
                # No right operand - just check truthiness of left
                result = bool(left_value)
                
            return result, facts_used
            
        except Exception as e:
            logger.error(f"Error evaluating condition: {e}")
            
            if self.mode == "strict":
                raise
                
            # Return False for failed evaluations in lenient mode
            return False, facts_used
            
    def _get_operand_value(
        self,
        operand: Any,
        facts: Dict[str, Fact],
        context: Dict[str, Any]
    ) -> Tuple[Any, List[str]]:
        """Get value from operand, which could be a fact reference, literal, or condition"""
        
        facts_used = []
        
        if isinstance(operand, str):
            # Check if it's a fact reference (starts with $ or @)
            if operand.startswith("$"):
                fact_name = operand[1:]
                if fact_name in facts:
                    facts_used.append(fact_name)
                    return facts[fact_name].value, facts_used
                elif fact_name in context:
                    return context[fact_name], facts_used
                else:
                    raise ValueError(f"Fact not found: {fact_name}")
                    
            # Check if it's a context reference
            elif operand.startswith("@"):
                context_name = operand[1:]
                if context_name in context:
                    return context[context_name], facts_used
                else:
                    raise ValueError(f"Context variable not found: {context_name}")
                    
            # Check if it's a literal string with quotes
            elif operand.startswith('"') and operand.endswith('"'):
                return operand[1:-1], facts_used
            elif operand.startswith("'") and operand.endswith("'"):
                return operand[1:-1], facts_used
                
            # Try to parse as number
            else:
                try:
                    # Check for boolean
                    if operand.lower() == "true":
                        return True, facts_used
                    elif operand.lower() == "false":
                        return False, facts_used
                    elif operand.lower() == "null" or operand.lower() == "none":
                        return None, facts_used
                        
                    # Try integer
                    if "." in operand:
                        return float(operand), facts_used
                    else:
                        return int(operand), facts_used
                except ValueError:
                    # Return as string
                    return operand, facts_used
                    
        elif isinstance(operand, Condition):
            # Recursively evaluate condition
            result, sub_facts = self.evaluate_condition(operand, facts, context)
            facts_used.extend(sub_facts)
            return result, facts_used
            
        elif isinstance(operand, (list, tuple)):
            # Handle list/tuple of values
            result_list = []
            for item in operand:
                item_value, item_facts = self._get_operand_value(item, facts, context)
                facts_used.extend(item_facts)
                result_list.append(item_value)
            return result_list, facts_used
            
        else:
            # Literal value
            return operand, facts_used
            
    def execute_actions(
        self,
        actions: List[Any],
        facts: Dict[str, Fact],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute rule actions"""
        
        results = {}
        
        for action in actions:
            try:
                if action.type == "set_fact":
                    # Evaluate expression or use literal value
                    if action.expression:
                        # This would need an expression evaluator
                        value = self._evaluate_expression(action.expression, facts, context)
                    else:
                        value = action.value
                        
                    # Create or update fact
                    facts[action.target] = Fact(
                        name=action.target,
                        value=value,
                        source="rule_action",
                        timestamp=datetime.utcnow()
                    )
                    results[action.target] = value
                    
                elif action.type == "calculate":
                    # This would need a more sophisticated expression evaluator
                    # For now, placeholder
                    pass
                    
                elif action.type == "log":
                    logger.info(f"Rule log: {action.value}")
                    
            except Exception as e:
                logger.error(f"Error executing action: {e}")
                
                if self.mode == "strict":
                    raise
                    
        return results
        
    def _evaluate_expression(
        self,
        expression: str,
        facts: Dict[str, Fact],
        context: Dict[str, Any]
    ) -> Any:
        """Evaluate a mathematical or logical expression"""
        # This would be implemented with a proper expression parser
        # For now, simple placeholder
        return expression
        
    def register_custom_operator(self, name: str, func: Callable):
        """Register a custom operator"""
        self.custom_operators[name] = func
        logger.info(f"Registered custom operator: {name}")
        
    def check_threshold(
        self,
        value: float,
        thresholds: Dict[str, float],
        tolerance: float = 0.0
    ) -> Dict[str, bool]:
        """Check value against thresholds"""
        
        results = {}
        
        for threshold_name, threshold_value in thresholds.items():
            if threshold_name == "min":
                results["meets_minimum"] = value >= (threshold_value - tolerance)
            elif threshold_name == "max":
                results["exceeds_maximum"] = value > (threshold_value + tolerance)
            elif threshold_name == "target":
                results["at_target"] = abs(value - threshold_value) <= tolerance
            elif threshold_name == "warning_min":
                results["below_warning"] = value < threshold_value
            elif threshold_name == "warning_max":
                results["above_warning"] = value > threshold_value
                
        return results
